"""Development-only event-window prescreen with temporal and symbol holdbacks."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash

from .parameter_search import (
    add_indicators,
    build_signal,
    compute_metrics,
    merge_btc_context,
    simulate_trades,
)
from .workflow_candidates import ShortCycleWorkflowCandidate


_TIMEFRAME_MINUTES = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1_440}
_SOURCE_TIMEFRAME = {
    "5m": "5m",
    "15m": "15m",
    "1h": "15m",
    "4h": "4h",
    "1d": "4h",
}


@dataclass(frozen=True)
class EventWindowPrescreenConfig:
    canonicalRoot: Path
    derivationSymbols: tuple[str, ...]
    holdbackSymbols: tuple[str, ...]
    trainStart: str = "2022-01-01"
    trainEnd: str = "2024-01-01"
    validationEnd: str = "2025-01-01"
    targetR: float = 2.0
    feeRate: float = 0.0005
    slippageRate: float = 0.0005
    outputPath: Path | None = None


def _utc(value: str) -> pd.Timestamp:
    return pd.Timestamp(value, tz="UTC")


def _partition_bounds(path: Path) -> tuple[int, int] | None:
    values = path.stem.split("-")
    if len(values) < 3:
        return None
    try:
        return int(values[0]), int(values[1])
    except ValueError:
        return None


def latest_canonical_partition(
    canonical_root: Path,
    instrument: str,
    timeframe: str,
    *,
    required_start: pd.Timestamp,
    required_end: pd.Timestamp,
) -> Path:
    directory = canonical_root / instrument / timeframe
    required_start_ms = int(required_start.timestamp() * 1000)
    required_end_ms = int(required_end.timestamp() * 1000)
    eligible: list[tuple[int, int, int, Path]] = []
    for path in directory.glob("*.parquet"):
        bounds = _partition_bounds(path)
        if bounds is None:
            continue
        start_ms, end_ms = bounds
        if start_ms <= required_start_ms and end_ms >= required_end_ms:
            eligible.append((end_ms, end_ms - start_ms, path.stat().st_mtime_ns, path))
    if not eligible:
        raise ValueError(
            f"canonical_partition_not_covering_window:{instrument}:{timeframe}"
        )
    return max(eligible, key=lambda item: item[:3])[3]


def _pair(instrument: str) -> str:
    return f"{instrument.removesuffix('-USDT-SWAP')}/USDT:USDT"


def _resample_closed_ohlcv(
    frame: pd.DataFrame,
    *,
    source_timeframe: str,
    target_timeframe: str,
) -> pd.DataFrame:
    if source_timeframe == target_timeframe:
        return frame
    source_minutes = _TIMEFRAME_MINUTES[source_timeframe]
    target_minutes = _TIMEFRAME_MINUTES[target_timeframe]
    if target_minutes % source_minutes:
        raise ValueError(
            f"unsupported_timeframe_resample:{source_timeframe}:{target_timeframe}"
        )
    required_rows = target_minutes // source_minutes
    rule = f"{target_minutes}min"
    indexed = frame.set_index("date")
    grouped = indexed.resample(rule, origin="epoch", label="left", closed="left")
    output = grouped.agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
        sourceRowCount=("close", "count"),
    )
    output = output[output["sourceRowCount"] == required_rows].drop(
        columns="sourceRowCount"
    )
    output["confirmed"] = 1
    return output.reset_index()


def _load_raw_frame(
    config: EventWindowPrescreenConfig,
    instrument: str,
    timeframe: str,
) -> tuple[pd.DataFrame, str]:
    timeframe_minutes = _TIMEFRAME_MINUTES[timeframe]
    source_timeframe = _SOURCE_TIMEFRAME[timeframe]
    source_minutes = _TIMEFRAME_MINUTES[source_timeframe]
    warmup_start = _utc(config.trainStart) - pd.Timedelta(
        minutes=timeframe_minutes * 320
    )
    validation_end = _utc(config.validationEnd)
    path = latest_canonical_partition(
        config.canonicalRoot,
        instrument,
        source_timeframe,
        required_start=warmup_start,
        required_end=validation_end - pd.Timedelta(minutes=source_minutes),
    )
    frame = pd.read_parquet(path)
    frame = frame.loc[:, ["date", "open", "high", "low", "close", "volume", "confirmed"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame[
        (frame["confirmed"] == 1)
        & (frame["date"] >= warmup_start)
        & (frame["date"] < validation_end)
    ]
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    frame = frame.sort_values("date").drop_duplicates("date", keep="last")
    frame = _resample_closed_ohlcv(
        frame,
        source_timeframe=source_timeframe,
        target_timeframe=timeframe,
    )
    frame["pair"] = _pair(instrument)
    return frame.reset_index(drop=True), path.as_posix()


def _load_frames(
    config: EventWindowPrescreenConfig,
    timeframe: str,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    symbols = tuple(dict.fromkeys((*config.derivationSymbols, *config.holdbackSymbols)))
    load_symbols = tuple(dict.fromkeys(("BTC-USDT-SWAP", *symbols)))
    raw_frames: dict[str, pd.DataFrame] = {}
    sources: dict[str, str] = {}
    for instrument in load_symbols:
        raw, source = _load_raw_frame(config, instrument, timeframe)
        raw_frames[instrument] = add_indicators(raw)
        sources[instrument] = source
    btc = raw_frames.get("BTC-USDT-SWAP")
    frames = {
        instrument: merge_btc_context(raw_frames[instrument], btc)
        for instrument in symbols
    }
    return frames, sources


def _segment_trades(
    trades: list[dict[str, Any]],
    symbols: Sequence[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[dict[str, Any]]:
    allowed = {_pair(symbol) for symbol in symbols}
    selected: list[dict[str, Any]] = []
    for trade in trades:
        entry = pd.Timestamp(str(trade["entryDate"]))
        exit_time = pd.Timestamp(str(trade["exitDate"]))
        if (
            str(trade["pair"]) in allowed
            and start <= entry < end
            and exit_time < end
        ):
            selected.append(trade)
    return selected


def _segment_metrics(
    trades: list[dict[str, Any]],
    candle_count: int,
    expected_pairs: Sequence[str],
) -> dict[str, Any]:
    metrics = compute_metrics(trades)
    pair_counts = Counter(str(item["pair"]) for item in trades)
    pair_metrics = {
        pair: compute_metrics(
            [item for item in trades if str(item["pair"]) == pair]
        )
        for pair in sorted(set(expected_pairs) | set(pair_counts))
    }
    positive_pair_count = sum(
        1 for values in pair_metrics.values() if float(values.get("expectancyR") or 0) > 0
    )
    metrics["pairMetrics"] = pair_metrics
    metrics["positivePairCount"] = positive_pair_count
    metrics["positivePairShare"] = (
        round(positive_pair_count / len(pair_metrics), 6) if pair_metrics else 0.0
    )
    metrics["largestPairShare"] = (
        round(max(pair_counts.values()) / len(trades), 6) if trades else 0.0
    )
    metrics["eventsPer1000Candles"] = (
        round(len(trades) / candle_count * 1000, 6) if candle_count else 0.0
    )
    return metrics


def prescreen_robustness_reasons(
    segment_metrics: dict[str, dict[str, Any]],
) -> tuple[str, ...]:
    reasons: list[str] = []
    requirements = {
        "derivationTrain": (30, "derivation_train"),
        "derivationValidation": (20, "derivation_validation"),
        "symbolHoldback": (20, "symbol_holdback"),
    }
    for segment, (minimum_trades, label) in requirements.items():
        metrics = segment_metrics.get(segment) or {}
        if int(metrics.get("tradeCount") or 0) < minimum_trades:
            reasons.append(f"{label}_sample_below_{minimum_trades}")
        if float(metrics.get("expectancyR") or 0) <= 0:
            reasons.append(f"{label}_expectancy_not_positive")
        if float(metrics.get("profitFactor") or 0) <= 1.0:
            reasons.append(f"{label}_profit_factor_not_above_one")
        if float(metrics.get("largestPairShare") or 0) > 0.6:
            reasons.append(f"{label}_symbol_concentration_above_60pct")
        pair_metrics = metrics.get("pairMetrics") or {}
        positive_pair_share = (
            sum(
                1
                for values in pair_metrics.values()
                if float(values.get("expectancyR") or 0) > 0
            )
            / len(pair_metrics)
            if pair_metrics
            else 0.0
        )
        if pair_metrics and positive_pair_share < 0.5:
            reasons.append(f"{label}_positive_pair_share_below_50pct")
    return tuple(reasons)


def _candidate_result(
    candidate: ShortCycleWorkflowCandidate,
    frames: dict[str, pd.DataFrame],
    config: EventWindowPrescreenConfig,
) -> dict[str, Any]:
    trades: list[dict[str, Any]] = []
    for frame in frames.values():
        signal, direction = build_signal(
            frame, candidate.signalFamily, candidate.parameters
        )
        trades.extend(
            simulate_trades(
                frame,
                signal,
                direction,
                stop_atr=float(candidate.parameters["stop_atr"]),
                max_hold=int(candidate.parameters["max_hold"]),
                target_r=config.targetR,
                fee_rate=config.feeRate,
                slippage_rate=config.slippageRate,
            )
        )
    train_start = _utc(config.trainStart)
    train_end = _utc(config.trainEnd)
    validation_end = _utc(config.validationEnd)
    segments = {
        "derivationTrain": (
            config.derivationSymbols,
            train_start,
            train_end,
        ),
        "derivationValidation": (
            config.derivationSymbols,
            train_end,
            validation_end,
        ),
        "symbolHoldback": (
            config.holdbackSymbols,
            train_start,
            validation_end,
        ),
    }
    metrics: dict[str, dict[str, Any]] = {}
    for name, (symbols, start, end) in segments.items():
        rows = _segment_trades(trades, symbols, start, end)
        candles = sum(
            int(((frame["date"] >= start) & (frame["date"] < end)).sum())
            for instrument, frame in frames.items()
            if instrument in symbols
        )
        metrics[name] = _segment_metrics(
            rows,
            candles,
            tuple(_pair(symbol) for symbol in symbols),
        )
    reasons = prescreen_robustness_reasons(metrics)
    return {
        "candidateKey": candidate.familyKey,
        "displayName": candidate.displayName,
        "timeframe": candidate.timeframe,
        "signalFamily": candidate.signalFamily,
        "direction": candidate.direction,
        "targetR": config.targetR,
        "eligible": not reasons,
        "rejectionReasons": list(reasons),
        "segmentMetrics": metrics,
    }


def run_event_window_prescreen(
    candidates: Sequence[ShortCycleWorkflowCandidate],
    config: EventWindowPrescreenConfig,
) -> dict[str, Any]:
    if config.targetR < 2:
        raise ValueError("event_window_prescreen_target_r_below_two")
    sources: dict[str, dict[str, str]] = {}
    results: list[dict[str, Any]] = []
    for timeframe in sorted({candidate.timeframe for candidate in candidates}):
        frames, timeframe_sources = _load_frames(config, timeframe)
        sources[timeframe] = timeframe_sources
        results.extend(
            _candidate_result(candidate, frames, config)
            for candidate in candidates
            if candidate.timeframe == timeframe
        )
    report: dict[str, Any] = {
        "schemaVersion": "event_window_prescreen_report_v1",
        "status": "completed",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "selectionBoundary": "development_and_symbol_holdback_only",
        "lockedOrFormalHoldoutUsedForSelection": False,
        "config": {
            "canonicalRoot": config.canonicalRoot.as_posix(),
            "derivationSymbols": list(config.derivationSymbols),
            "holdbackSymbols": list(config.holdbackSymbols),
            "trainStart": config.trainStart,
            "trainEnd": config.trainEnd,
            "validationEnd": config.validationEnd,
            "targetR": config.targetR,
            "feeRate": config.feeRate,
            "slippageRate": config.slippageRate,
        },
        "sources": sources,
        "eligibleCandidateKeys": [
            item["candidateKey"] for item in results if item["eligible"]
        ],
        "results": results,
    }
    report["reportHash"] = stable_hash(report, prefix="event-window-prescreen")
    if config.outputPath is not None:
        write_json_atomic(config.outputPath, report)
    return report
