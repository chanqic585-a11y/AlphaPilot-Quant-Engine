"""Build pre-entry factor rows for transparent event-window attribution."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash

from .event_window_factor_search import discover_robust_factor_guards
from .event_window_research import EventWindowPrescreenConfig, _load_frames, _pair, _utc
from .parameter_search import build_signal, simulate_trades
from .workflow_candidates import ShortCycleWorkflowCandidate


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if np.isfinite(number) else None


def enrich_trade_rows_with_factors(
    frame: pd.DataFrame,
    trades: Sequence[Mapping[str, Any]],
    *,
    direction: str,
    lookback: int = 12,
) -> list[dict[str, Any]]:
    """Attach factors known on the closed signal bar immediately before entry."""

    if direction not in {"long", "short"}:
        raise ValueError(f"event_window_factor_direction_invalid:{direction}")
    if lookback < 1:
        raise ValueError("event_window_factor_lookback_invalid")
    if frame.empty:
        return []

    data = frame.reset_index(drop=True).copy()
    data["date"] = pd.to_datetime(data["date"], utc=True, errors="coerce")
    row_by_date = {
        timestamp: index
        for index, timestamp in enumerate(data["date"])
        if not pd.isna(timestamp)
    }
    sign = 1.0 if direction == "long" else -1.0
    enriched: list[dict[str, Any]] = []
    for trade in trades:
        entry = pd.Timestamp(str(trade["entryDate"]))
        if entry.tzinfo is None:
            entry = entry.tz_localize("UTC")
        else:
            entry = entry.tz_convert("UTC")
        entry_index = row_by_date.get(entry)
        if entry_index is None:
            continue
        signal_index = entry_index - 1
        comparison_index = signal_index - lookback
        if comparison_index < 0:
            continue
        signal_row = data.iloc[signal_index]
        comparison_row = data.iloc[comparison_index]
        close = _finite(signal_row.get("close"))
        prior_close = _finite(comparison_row.get("close"))
        ema20 = _finite(signal_row.get("ema20"))
        prior_ema20 = _finite(comparison_row.get("ema20"))
        ema50 = _finite(signal_row.get("ema50"))
        ema200 = _finite(signal_row.get("ema200"))
        atr14 = _finite(signal_row.get("atr14"))
        required = (close, prior_close, ema20, prior_ema20, ema50, ema200, atr14)
        if any(value is None or value == 0 for value in required):
            continue
        row = dict(trade)
        row.update(
            {
                "factorTimestamp": pd.Timestamp(signal_row["date"]).isoformat(),
                "aligned_return": sign * (close / prior_close - 1),
                "aligned_slope20": sign * (ema20 / prior_ema20 - 1),
                "aligned_trend20_50": sign * (ema20 / ema50 - 1),
                "aligned_trend50_200": sign * (ema50 / ema200 - 1),
                "btc_aligned": sign * float(signal_row.get("btc_ret_3", np.nan)),
                "btc_trend20_50": sign
                * float(signal_row.get("btc_trend20_50", np.nan)),
                "btc_trend50_200": sign
                * float(signal_row.get("btc_trend50_200", np.nan)),
                "btc_slope20_12": sign
                * float(signal_row.get("btc_slope20_12", np.nan)),
                "atr_pct": atr14 / close,
            }
        )
        enriched.append(row)
    return enriched


def segment_factor_rows(
    rows: Sequence[Mapping[str, Any]],
    *,
    pairs: Sequence[str],
    start: pd.Timestamp,
    end: pd.Timestamp,
) -> list[dict[str, Any]]:
    allowed = set(str(pair) for pair in pairs)
    selected: list[dict[str, Any]] = []
    for row in rows:
        entry = pd.Timestamp(str(row["entryDate"]))
        exit_time = pd.Timestamp(str(row["exitDate"]))
        if str(row["pair"]) in allowed and start <= entry < end and exit_time < end:
            selected.append(dict(row))
    return selected


def _candidate_rows(
    candidate: ShortCycleWorkflowCandidate,
    frames: Mapping[str, pd.DataFrame],
    config: EventWindowPrescreenConfig,
) -> dict[str, list[dict[str, Any]]]:
    enriched: list[dict[str, Any]] = []
    for frame in frames.values():
        signal, direction = build_signal(
            frame,
            candidate.signalFamily,
            candidate.parameters,
        )
        trades = simulate_trades(
            frame,
            signal,
            direction,
            stop_atr=float(candidate.parameters["stop_atr"]),
            max_hold=int(candidate.parameters["max_hold"]),
            target_r=config.targetR,
            fee_rate=config.feeRate,
            slippage_rate=config.slippageRate,
        )
        enriched.extend(
            enrich_trade_rows_with_factors(
                frame,
                trades,
                direction=direction,
                lookback=int(candidate.parameters.get("factor_lookback") or 12),
            )
        )

    train_start = _utc(config.trainStart)
    train_end = _utc(config.trainEnd)
    validation_end = _utc(config.validationEnd)
    derivation_pairs = tuple(_pair(symbol) for symbol in config.derivationSymbols)
    holdback_pairs = tuple(_pair(symbol) for symbol in config.holdbackSymbols)
    return {
        "derivationTrain": segment_factor_rows(
            enriched,
            pairs=derivation_pairs,
            start=train_start,
            end=train_end,
        ),
        "derivationValidation": segment_factor_rows(
            enriched,
            pairs=derivation_pairs,
            start=train_end,
            end=validation_end,
        ),
        "symbolHoldback": segment_factor_rows(
            enriched,
            pairs=holdback_pairs,
            start=train_start,
            end=validation_end,
        ),
    }


def run_event_window_factor_discovery(
    candidates: Sequence[ShortCycleWorkflowCandidate],
    config: EventWindowPrescreenConfig,
    *,
    max_results_per_candidate: int = 5,
    output_path: Path | None = None,
) -> dict[str, Any]:
    if config.targetR < 2:
        raise ValueError("event_window_factor_discovery_target_r_below_two")
    results: list[dict[str, Any]] = []
    sources: dict[str, dict[str, str]] = {}
    for timeframe in sorted({candidate.timeframe for candidate in candidates}):
        frames, timeframe_sources = _load_frames(config, timeframe)
        sources[timeframe] = timeframe_sources
        for candidate in candidates:
            if candidate.timeframe != timeframe:
                continue
            rows_by_segment = _candidate_rows(candidate, frames, config)
            guards = discover_robust_factor_guards(
                rows_by_segment,
                max_results=max_results_per_candidate,
            )
            results.append(
                {
                    "candidateKey": candidate.familyKey,
                    "displayName": candidate.displayName,
                    "timeframe": candidate.timeframe,
                    "signalFamily": candidate.signalFamily,
                    "direction": candidate.direction,
                    "baseTradeCountBySegment": {
                        name: len(rows) for name, rows in rows_by_segment.items()
                    },
                    "robustGuardCount": len(guards),
                    "robustGuards": list(guards),
                }
            )
    report: dict[str, Any] = {
        "schemaVersion": "event_window_factor_discovery_report_v1",
        "status": "completed",
        "generatedAt": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        "selectionBoundary": "development_temporal_validation_and_symbol_holdback_only",
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
        "results": results,
        "candidateWithRobustGuardCount": sum(
            bool(item["robustGuardCount"]) for item in results
        ),
    }
    report["reportHash"] = stable_hash(report, prefix="event-window-factor-discovery")
    if output_path is not None:
        write_json_atomic(output_path, report)
    return report
