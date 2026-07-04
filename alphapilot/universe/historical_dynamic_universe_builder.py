"""Historical Dynamic Universe builder.

The builder reads local public OHLCV files and creates point-in-time universe
snapshots. Each snapshot uses only candles closed before the snapshot date.
It does not download data, run backtests, enter Dry-run, call exchange APIs,
read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import json
import math
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from alphapilot.universe.dynamic_universe_schema import (
    DynamicUniverseBuildReport,
    DynamicUniverseConfig,
    DynamicUniversePairScore,
    DynamicUniverseSnapshot,
)
from alphapilot.universe.top30_usdt_swap import get_top30_usdt_swap_pairs

REPORT_ID = "v13_4_13_dynamic_universe_build_report"
REPORT_VERSION = "V13.4.13"


@dataclass
class BuildOutputs:
    snapshots: list[DynamicUniverseSnapshot]
    report: DynamicUniverseBuildReport


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def pair_to_freqtrade_file_stem(pair: str) -> str:
    return pair.replace("/", "_").replace(":", "_")


def parse_timerange(timerange: str) -> tuple[datetime | None, datetime | None]:
    start_raw, _, end_raw = timerange.partition("-")
    start = datetime.strptime(start_raw, "%Y%m%d").replace(tzinfo=UTC) if start_raw else None
    end = datetime.strptime(end_raw, "%Y%m%d").replace(tzinfo=UTC) if end_raw else None
    return start, end


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _round(value: Any, digits: int = 8) -> float | None:
    number = _safe_float(value)
    return round(number, digits) if number is not None else None


def _read_ohlcv_file(path: Path) -> pd.DataFrame:
    suffixes = "".join(path.suffixes)
    if path.suffix == ".feather":
        return pd.read_feather(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if suffixes.endswith(".json.gz") or path.suffix == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported OHLCV file format: {path}")


def load_pair_data(pair: str, config: DynamicUniverseConfig) -> tuple[pd.DataFrame | None, str | None]:
    data_dir = Path(config.dataPath)
    stem = pair_to_freqtrade_file_stem(pair)
    candidates = [
        data_dir / f"{stem}-{config.timeframeForRanking}-futures.feather",
        data_dir / f"{stem}-{config.timeframeForRanking}-futures.parquet",
        data_dir / f"{stem}-{config.timeframeForRanking}-futures.json",
        data_dir / f"{stem}-{config.timeframeForRanking}-futures.json.gz",
    ]
    existing = next((path for path in candidates if path.exists()), None)
    if existing is None:
        return None, "missing_ohlcv_file"
    try:
        frame = _read_ohlcv_file(existing)
    except ImportError as exc:
        return None, f"missing_dependency: {exc}"
    except Exception as exc:  # noqa: BLE001 - report data read failures without hiding pair context.
        return None, f"read_failed: {exc}"

    required = {"date", "open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        return None, f"missing_columns: {','.join(missing)}"

    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["date", "close", "volume"]).sort_values("date")
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["close", "volume"])
    frame["quoteVolume"] = frame["close"] * frame["volume"]
    if frame.empty:
        return None, "empty_ohlcv_after_cleaning"
    return frame, None


def _window(frame: pd.DataFrame, snapshot_ts: datetime, hours: int) -> pd.DataFrame:
    start_ts = pd.Timestamp(snapshot_ts - timedelta(hours=hours))
    end_ts = pd.Timestamp(snapshot_ts)
    return frame[(frame["date"] >= start_ts) & (frame["date"] < end_ts)]


def _previous_window(frame: pd.DataFrame, snapshot_ts: datetime, start_days: int, end_days: int) -> pd.DataFrame:
    start_ts = pd.Timestamp(snapshot_ts - timedelta(days=start_days))
    end_ts = pd.Timestamp(snapshot_ts - timedelta(days=end_days))
    return frame[(frame["date"] >= start_ts) & (frame["date"] < end_ts)]


def _pct_return(window: pd.DataFrame) -> float | None:
    if len(window) < 2:
        return None
    first = _safe_float(window.iloc[0]["close"])
    last = _safe_float(window.iloc[-1]["close"])
    if first is None or first <= 0 or last is None:
        return None
    return last / first - 1


def _volatility(window: pd.DataFrame) -> float | None:
    if len(window) < 3:
        return None
    returns = window["close"].pct_change().dropna()
    if returns.empty:
        return None
    return float(returns.std(ddof=0))


def _volume_stability(window_3d: pd.DataFrame) -> float | None:
    if len(window_3d) < 24:
        return None
    grouped = window_3d.set_index("date")["quoteVolume"].resample("1D").sum()
    grouped = grouped[grouped > 0]
    if len(grouped) < 2:
        return None
    mean = float(grouped.mean())
    if mean <= 0:
        return None
    coeff_var = float(grouped.std(ddof=0) / mean)
    return max(0.0, 1.0 - coeff_var)


def calculate_pair_factors(pair: str, frame: pd.DataFrame, snapshot_ts: datetime, config: DynamicUniverseConfig) -> DynamicUniversePairScore:
    warnings: list[str] = []
    history = frame[frame["date"] < pd.Timestamp(snapshot_ts)]
    if history.empty:
        return DynamicUniversePairScore(
            pair=pair,
            universeScore=None,
            rank=None,
            quoteVolume24h=None,
            quoteVolume3d=None,
            volumeStability3d=None,
            missingCandleRate=None,
            absReturn24h=None,
            absReturn3d=None,
            volatility24h=None,
            volatility3d=None,
            volumeExpansion24h=None,
            volumeExpansion3d=None,
            excluded=True,
            excludeReason="no_history_before_snapshot",
            warnings=["no closed candles available before snapshotDate"],
        )

    first_ts = history.iloc[0]["date"].to_pydatetime()
    history_days = (snapshot_ts - first_ts).total_seconds() / 86400
    window_24h = _window(frame, snapshot_ts, 24)
    window_3d = _window(frame, snapshot_ts, 72)
    previous_7d = _previous_window(frame, snapshot_ts, 8, 1)

    expected_3d = 72
    missing_rate = max(0.0, 1.0 - (len(window_3d) / expected_3d))
    quote_24h = float(window_24h["quoteVolume"].sum()) if not window_24h.empty else None
    quote_3d = float(window_3d["quoteVolume"].sum()) if not window_3d.empty else None
    avg_daily_quote_7d = float(previous_7d["quoteVolume"].sum() / 7) if not previous_7d.empty else None

    return_24h = _pct_return(window_24h)
    return_3d = _pct_return(window_3d)
    volatility_24h = _volatility(window_24h)
    volatility_3d = _volatility(window_3d)
    volume_expansion_24h = quote_24h / avg_daily_quote_7d if quote_24h and avg_daily_quote_7d and avg_daily_quote_7d > 0 else None
    volume_expansion_3d = quote_3d / (avg_daily_quote_7d * 3) if quote_3d and avg_daily_quote_7d and avg_daily_quote_7d > 0 else None

    exclude_reason: str | None = None
    if history_days < config.minimumHistoryDays:
        exclude_reason = "insufficient_history"
    elif missing_rate > config.missingCandleRateLimit:
        exclude_reason = "high_missing_candle_rate"
    elif quote_24h is None or quote_24h <= 0:
        exclude_reason = "quoteVolume24h_unavailable_or_zero"
    elif quote_3d is None or quote_3d <= 0:
        exclude_reason = "quoteVolume3d_unavailable_or_zero"

    if history_days < config.idealHistoryDays:
        warnings.append("history_less_than_ideal_90d")
    if volume_expansion_24h is None:
        warnings.append("volumeExpansion24h_unavailable")

    return DynamicUniversePairScore(
        pair=pair,
        universeScore=None,
        rank=None,
        quoteVolume24h=_round(quote_24h, 4),
        quoteVolume3d=_round(quote_3d, 4),
        volumeStability3d=_round(_volume_stability(window_3d), 6),
        missingCandleRate=_round(missing_rate, 6),
        absReturn24h=_round(abs(return_24h) if return_24h is not None else None, 8),
        absReturn3d=_round(abs(return_3d) if return_3d is not None else None, 8),
        volatility24h=_round(volatility_24h, 8),
        volatility3d=_round(volatility_3d, 8),
        volumeExpansion24h=_round(volume_expansion_24h, 8),
        volumeExpansion3d=_round(volume_expansion_3d, 8),
        excluded=exclude_reason is not None,
        excludeReason=exclude_reason,
        warnings=warnings,
    )


def _rank_scores(scores: list[DynamicUniversePairScore], field_name: str) -> dict[str, float | None]:
    available = [
        (score.pair, _safe_float(getattr(score, field_name)))
        for score in scores
        if not score.excluded and _safe_float(getattr(score, field_name)) is not None
    ]
    if not available:
        return {score.pair: None for score in scores}
    if len(available) == 1:
        return {pair: 100.0 for pair, _ in available}

    ordered = sorted(available, key=lambda item: item[1] or 0.0)
    denominator = len(ordered) - 1
    rank_map: dict[str, float] = {}
    for idx, (pair, _) in enumerate(ordered):
        rank_map[pair] = round((idx / denominator) * 100, 6)
    return {score.pair: rank_map.get(score.pair) for score in scores}


def apply_universe_scores(scores: list[DynamicUniversePairScore]) -> list[DynamicUniversePairScore]:
    weights = {
        "quoteVolume24h": 0.35,
        "quoteVolume3d": 0.25,
        "absReturn24h": 0.15,
        "absReturn3d": 0.10,
        "volatility3d": 0.10,
        "volumeExpansion24h": 0.05,
    }
    rank_factor_maps = {field_name: _rank_scores(scores, field_name) for field_name in weights}
    for score in scores:
        if score.excluded:
            score.universeScore = None
            score.rank = None
            score.rankFactors = {field_name: rank_factor_maps[field_name].get(score.pair) for field_name in weights}
            continue
        total = 0.0
        weight_sum = 0.0
        factors: dict[str, float | None] = {}
        for field_name, weight in weights.items():
            rank_value = rank_factor_maps[field_name].get(score.pair)
            factors[field_name] = rank_value
            if rank_value is not None:
                total += rank_value * weight
                weight_sum += weight
        if weight_sum == 0:
            score.excluded = True
            score.excludeReason = "all_rank_factors_unavailable"
            score.universeScore = None
        else:
            score.universeScore = round(total / weight_sum, 6)
        score.rankFactors = factors

    ranked = sorted(
        [score for score in scores if not score.excluded and score.universeScore is not None],
        key=lambda item: item.universeScore or 0,
        reverse=True,
    )
    for idx, score in enumerate(ranked, start=1):
        score.rank = idx
    return scores


def _snapshot_dates(pair_frames: dict[str, pd.DataFrame], config: DynamicUniverseConfig) -> list[datetime]:
    start, end = parse_timerange(config.timerange)
    min_start_candidates = []
    max_end_candidates = []
    for frame in pair_frames.values():
        min_start_candidates.append(frame["date"].min().to_pydatetime())
        max_end_candidates.append(frame["date"].max().to_pydatetime())
    if not min_start_candidates or not max_end_candidates:
        return []

    data_start = max(min_start_candidates)
    data_end = min(max_end_candidates)
    first_snapshot = (start or data_start).replace(hour=0, minute=0, second=0, microsecond=0)
    first_snapshot = max(first_snapshot, data_start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=config.warmupDays))
    last_snapshot = (end or data_end).replace(hour=0, minute=0, second=0, microsecond=0)
    last_snapshot = min(last_snapshot, data_end.replace(hour=0, minute=0, second=0, microsecond=0))
    step_days = 1 if config.refreshFrequency == "daily" else 3

    dates: list[datetime] = []
    current = first_snapshot
    while current <= last_snapshot:
        dates.append(current)
        current += timedelta(days=step_days)
    return dates


def _candidate_pairs(config: DynamicUniverseConfig) -> list[str]:
    if config.candidateMode != "top30":
        raise ValueError(f"Unsupported candidateMode: {config.candidateMode}")
    return get_top30_usdt_swap_pairs()


def build_historical_dynamic_universe(config: DynamicUniverseConfig) -> BuildOutputs:
    generated_at = utc_now()
    warnings: list[str] = []
    candidate_pairs = _candidate_pairs(config)
    pair_frames: dict[str, pd.DataFrame] = {}
    missing_data: list[str] = []
    load_errors: dict[str, str] = {}

    for pair in candidate_pairs:
        frame, error = load_pair_data(pair, config)
        if frame is None:
            missing_data.append(pair)
            load_errors[pair] = error or "unknown_load_error"
        else:
            pair_frames[pair] = frame

    if not pair_frames:
        report = DynamicUniverseBuildReport(
            reportId=REPORT_ID,
            version=REPORT_VERSION,
            status="blocked_no_usable_ohlcv",
            config=config,
            timerange=config.timerange,
            refreshFrequency=config.refreshFrequency,
            maxPairs=config.maxPairs,
            candidateMode=config.candidateMode,
            snapshotCount=0,
            candidatePairsCount=len(candidate_pairs),
            supportedPairs=[],
            excludedPairs=[],
            insufficientDataPairs=[],
            missingDataPairs=missing_data,
            pairsWithEstimatedQuoteVolume=[],
            pairsWithHighMissingRate=[],
            averageSelectedPairs=0,
            topMostSelectedPairs=[],
            mostExcludedPairs=[],
            lookaheadBiasProtection=lookahead_bias_protection_notes(),
            outputSnapshotsPath="",
            outputSampleSnapshotsPath="",
            outputSummaryPath="",
            warnings=[f"{pair}: {reason}" for pair, reason in load_errors.items()],
            generatedAt=generated_at,
        )
        return BuildOutputs(snapshots=[], report=report)

    snapshot_dates = _snapshot_dates(pair_frames, config)
    if not snapshot_dates:
        report = DynamicUniverseBuildReport(
            reportId=REPORT_ID,
            version=REPORT_VERSION,
            status="blocked_no_snapshot_dates",
            config=config,
            timerange=config.timerange,
            refreshFrequency=config.refreshFrequency,
            maxPairs=config.maxPairs,
            candidateMode=config.candidateMode,
            snapshotCount=0,
            candidatePairsCount=len(candidate_pairs),
            supportedPairs=sorted(pair_frames),
            excludedPairs=[],
            insufficientDataPairs=[],
            missingDataPairs=missing_data,
            pairsWithEstimatedQuoteVolume=sorted(pair_frames),
            pairsWithHighMissingRate=[],
            averageSelectedPairs=0,
            topMostSelectedPairs=[],
            mostExcludedPairs=[],
            lookaheadBiasProtection=lookahead_bias_protection_notes(),
            outputSnapshotsPath="",
            outputSampleSnapshotsPath="",
            outputSummaryPath="",
            warnings=warnings + ["No snapshot dates available after warmup and timerange filters."],
            generatedAt=generated_at,
        )
        return BuildOutputs(snapshots=[], report=report)

    snapshots: list[DynamicUniverseSnapshot] = []
    selected_counter: Counter[str] = Counter()
    excluded_counter: Counter[str] = Counter()
    insufficient_data: set[str] = set()
    high_missing_rate: set[str] = set()

    for snapshot_ts in snapshot_dates:
        pair_scores: list[DynamicUniversePairScore] = []
        for pair in candidate_pairs:
            frame = pair_frames.get(pair)
            if frame is None:
                score = DynamicUniversePairScore(
                    pair=pair,
                    universeScore=None,
                    rank=None,
                    quoteVolume24h=None,
                    quoteVolume3d=None,
                    volumeStability3d=None,
                    missingCandleRate=None,
                    absReturn24h=None,
                    absReturn3d=None,
                    volatility24h=None,
                    volatility3d=None,
                    volumeExpansion24h=None,
                    volumeExpansion3d=None,
                    excluded=True,
                    excludeReason=load_errors.get(pair, "missing_ohlcv_file"),
                    warnings=["No local OHLCV data loaded for this pair."],
                )
            else:
                score = calculate_pair_factors(pair, frame, snapshot_ts, config)
            if score.excludeReason == "insufficient_history":
                insufficient_data.add(pair)
            if score.excludeReason == "high_missing_candle_rate":
                high_missing_rate.add(pair)
            pair_scores.append(score)

        pair_scores = apply_universe_scores(pair_scores)
        eligible = sorted(
            [score for score in pair_scores if not score.excluded and score.universeScore is not None],
            key=lambda item: item.universeScore or 0,
        )[-config.maxPairs :]
        eligible = sorted(eligible, key=lambda item: item.universeScore or 0, reverse=True)
        selected_pairs = [score.pair for score in eligible]
        selected_counter.update(selected_pairs)
        excluded_pairs = [score.pair for score in pair_scores if score.excluded]
        excluded_counter.update(excluded_pairs)
        snapshots.append(
            DynamicUniverseSnapshot(
                snapshotDate=snapshot_ts.date().isoformat(),
                generatedAt=generated_at,
                market=config.market,
                refreshFrequency=config.refreshFrequency,
                maxPairs=config.maxPairs,
                selectedPairs=selected_pairs,
                pairScores=sorted(pair_scores, key=lambda item: (item.excluded, -(item.universeScore or -1), item.pair)),
                excludedPairs=excluded_pairs,
                insufficientDataPairs=sorted(pair for pair in excluded_pairs if pair in insufficient_data),
                warnings=[] if selected_pairs else ["No pairs selected for this snapshot."],
            )
        )

    average_selected = round(sum(len(snapshot.selectedPairs) for snapshot in snapshots) / len(snapshots), 4) if snapshots else 0
    report = DynamicUniverseBuildReport(
        reportId=REPORT_ID,
        version=REPORT_VERSION,
        status="success" if snapshots else "blocked_no_snapshots",
        config=config,
        timerange=config.timerange,
        refreshFrequency=config.refreshFrequency,
        maxPairs=config.maxPairs,
        candidateMode=config.candidateMode,
        snapshotCount=len(snapshots),
        candidatePairsCount=len(candidate_pairs),
        supportedPairs=sorted(pair_frames),
        excludedPairs=sorted(excluded_counter),
        insufficientDataPairs=sorted(insufficient_data),
        missingDataPairs=missing_data,
        pairsWithEstimatedQuoteVolume=sorted(pair_frames) if config.quoteVolumeEstimated else [],
        pairsWithHighMissingRate=sorted(high_missing_rate),
        averageSelectedPairs=average_selected,
        topMostSelectedPairs=[{"pair": pair, "selectedCount": count} for pair, count in selected_counter.most_common(15)],
        mostExcludedPairs=[{"pair": pair, "excludedCount": count} for pair, count in excluded_counter.most_common(15)],
        lookaheadBiasProtection=lookahead_bias_protection_notes(),
        outputSnapshotsPath="reports/v13_4_13_dynamic_universe_snapshots.json",
        outputSampleSnapshotsPath="reports/v13_4_13_dynamic_universe_sample_snapshots.json",
        outputSummaryPath="reports/v13_4_13_dynamic_universe_summary.md",
        warnings=warnings + [f"{pair}: {reason}" for pair, reason in load_errors.items()],
        generatedAt=generated_at,
    )
    return BuildOutputs(snapshots=snapshots, report=report)


def lookahead_bias_protection_notes() -> list[str]:
    return [
        "Each snapshot uses only candles with date < snapshotDate 00:00 UTC.",
        "Ranking factors are recalculated per snapshot and never use future candles.",
        "Rolling windows are sliced before snapshotDate and cannot cross into future dates.",
        "Pairs with insufficient history or missing data are excluded instead of filled with fake values.",
        "The builder starts after warmupDays to avoid ranking from shallow history.",
    ]


def snapshots_to_dicts(snapshots: list[DynamicUniverseSnapshot]) -> list[dict[str, Any]]:
    return [snapshot.to_dict() for snapshot in snapshots]


def write_outputs(
    outputs: BuildOutputs,
    output_path: Path,
    sample_output_path: Path,
    build_report_path: Path,
    summary_path: Path,
    sample_size: int = 5,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    snapshots_payload = snapshots_to_dicts(outputs.snapshots)
    output_path.write_text(json.dumps(snapshots_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    sample_output_path.write_text(json.dumps(snapshots_payload[:sample_size], ensure_ascii=False, indent=2), encoding="utf-8")

    report_payload = outputs.report.to_dict()
    report_payload["outputSnapshotsPath"] = str(output_path)
    report_payload["outputSampleSnapshotsPath"] = str(sample_output_path)
    report_payload["outputSummaryPath"] = str(summary_path)
    build_report_path.write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(report_payload, summary_path)


def write_summary(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# V13.4.13 Historical Dynamic Universe Summary",
        "",
        "## Build Status",
        "",
        f"- status: {report['status']}",
        f"- timerange: {report['timerange']}",
        f"- refreshFrequency: {report['refreshFrequency']}",
        f"- maxPairs: {report['maxPairs']}",
        f"- candidateMode: {report['candidateMode']}",
        f"- snapshotCount: {report['snapshotCount']}",
        f"- candidatePairsCount: {report['candidatePairsCount']}",
        f"- averageSelectedPairs: {report['averageSelectedPairs']}",
        "",
        "## Data Availability",
        "",
        f"- supportedPairs: {len(report['supportedPairs'])}",
        f"- missingDataPairs: {', '.join(report['missingDataPairs']) if report['missingDataPairs'] else 'none'}",
        f"- insufficientDataPairs: {', '.join(report['insufficientDataPairs']) if report['insufficientDataPairs'] else 'none'}",
        f"- pairsWithEstimatedQuoteVolume: {len(report['pairsWithEstimatedQuoteVolume'])}",
        f"- pairsWithHighMissingRate: {', '.join(report['pairsWithHighMissingRate']) if report['pairsWithHighMissingRate'] else 'none'}",
        "",
        "## Top Most Selected Pairs",
        "",
    ]
    if report["topMostSelectedPairs"]:
        lines.extend(f"- {row['pair']}: {row['selectedCount']}" for row in report["topMostSelectedPairs"])
    else:
        lines.append("- none")
    lines.extend(["", "## Most Excluded Pairs", ""])
    if report["mostExcludedPairs"]:
        lines.extend(f"- {row['pair']}: {row['excludedCount']}" for row in report["mostExcludedPairs"])
    else:
        lines.append("- none")
    lines.extend(["", "## Lookahead Bias Protection", ""])
    lines.extend(f"- {item}" for item in report["lookaheadBiasProtection"])
    lines.extend(
        [
            "",
            "## Output Files",
            "",
            f"- snapshots: {report['outputSnapshotsPath']}",
            f"- sampleSnapshots: {report['outputSampleSnapshotsPath']}",
            f"- buildReport: reports/v13_4_13_dynamic_universe_build_report.json",
            "",
            "## Warnings",
            "",
        ]
    )
    if report["warnings"]:
        lines.extend(f"- {warning}" for warning in report["warnings"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This builder reads local public OHLCV files only. It does not run a strategy backtest, enter Dry-run, use API keys, call Trade API or Withdraw API, read accounts, read positions, create orders, or auto trade.",
            "",
            f"Next step: {report['nextStepRecommendation']}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")

