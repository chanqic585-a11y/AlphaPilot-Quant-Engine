"""Deterministic fixed-core data profiling without strategy-result leakage."""

from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash


_PERFORMANCE_FIELD_MARKERS = (
    "profitfactor",
    "strategyreturn",
    "backtestreturn",
    "winrate",
    "sharpe",
    "sortino",
    "pnl",
)


def _timestamp_series(frame: pd.DataFrame) -> pd.Series:
    if "date" in frame.columns:
        return pd.to_datetime(frame["date"], utc=True, errors="coerce")
    if "timestamp_ms" in frame.columns:
        return pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True, errors="coerce")
    raise ValueError("OHLCV frame requires date or timestamp_ms")


def _confirmed_series(frame: pd.DataFrame) -> pd.Series:
    if "confirmed" not in frame.columns:
        return pd.Series(True, index=frame.index, dtype="bool")
    values = frame["confirmed"]
    if values.dtype == bool:
        return values.fillna(False)
    return values.astype(str).str.lower().isin({"true", "1", "yes"})


def _usable_rows(frame: pd.DataFrame) -> pd.Series:
    confirmed = _confirmed_series(frame)
    volume = pd.to_numeric(frame["volume"], errors="coerce").fillna(0.0)
    high = pd.to_numeric(frame["high"], errors="coerce")
    low = pd.to_numeric(frame["low"], errors="coerce")
    open_ = pd.to_numeric(frame["open"], errors="coerce")
    close = pd.to_numeric(frame["close"], errors="coerce")
    finite = high.notna() & low.notna() & open_.notna() & close.notna()
    non_flat = (high > low) | (open_ != close)
    return confirmed & finite & (volume > 0) & non_flat


def profile_ohlcv_frame(
    frame: pd.DataFrame,
    *,
    instrument_id: str,
    timeframe: str,
    file_path: str,
    file_hash: str,
) -> dict[str, Any]:
    """Profile one authoritative OHLCV frame and exclude synthetic edges."""

    required = {"open", "high", "low", "close", "volume"}
    missing = sorted(required.difference(frame.columns))
    if missing:
        raise ValueError(f"OHLCV columns missing: {', '.join(missing)}")
    ordered = frame.copy()
    ordered["_timestamp"] = _timestamp_series(ordered)
    ordered = ordered.dropna(subset=["_timestamp"]).sort_values("_timestamp").reset_index(drop=True)
    if ordered.empty:
        raise ValueError(f"OHLCV frame is empty: {instrument_id} {timeframe}")
    usable = _usable_rows(ordered)
    usable_positions = [int(value) for value in ordered.index[usable]]
    if not usable_positions:
        raise ValueError(f"OHLCV frame has no usable confirmed rows: {instrument_id} {timeframe}")
    first_position = usable_positions[0]
    last_position = usable_positions[-1]
    bounded = ordered.iloc[first_position : last_position + 1].copy()
    bounded_usable = _usable_rows(bounded)
    usable_count = int(bounded_usable.sum())
    timestamps = bounded.loc[bounded_usable, "_timestamp"]
    effective_start = timestamps.iloc[0]
    latest_confirmed = timestamps.iloc[-1]
    intervals = timestamps.diff().dropna().dt.total_seconds()
    expected_rows = usable_count
    if not intervals.empty and float(intervals.median()) > 0:
        expected_rows = int(
            round(
                (latest_confirmed - effective_start).total_seconds()
                / float(intervals.median())
            )
        ) + 1
    expected_rows = max(expected_rows, usable_count, 1)
    coverage = min(100.0, usable_count / expected_rows * 100.0)
    close = pd.to_numeric(bounded.loc[bounded_usable, "close"], errors="coerce")
    volume = pd.to_numeric(bounded.loc[bounded_usable, "volume"], errors="coerce")
    quote_activity = (close.abs() * volume.abs()).replace([math.inf, -math.inf], pd.NA).dropna()
    liquidity = float(math.log1p(float(quote_activity.median()))) if not quote_activity.empty else 0.0
    returns = close.pct_change().dropna()
    volatility = float(returns.std(ddof=0) or 0.0)
    history_months = max(
        0.0,
        (latest_confirmed - effective_start).total_seconds() / (30.4375 * 86400),
    )
    return {
        "instrumentId": instrument_id,
        "exchange": "okx",
        "marketType": "swap",
        "timeframe": timeframe,
        "effectiveBacktestStart": effective_start.isoformat(),
        "latestConfirmed": latest_confirmed.isoformat(),
        "historyMonths": round(history_months, 4),
        "coveragePct": round(coverage, 6),
        "missingRatePct": round(100.0 - coverage, 6),
        "liquidityScore": round(liquidity, 8),
        "volatilityScore": round(volatility, 8),
        "sourceTraceable": True,
        "contractActive": True,
        "symbolMappingStable": True,
        "filePath": file_path,
        "sha256": file_hash,
        "rowCount": len(ordered),
        "usableRowCount": usable_count,
        "excludedLeadingRows": first_position,
        "excludedTailRows": len(ordered) - last_position - 1,
    }

def _reject_performance_fields(profiles: Iterable[Mapping[str, Any]]) -> None:
    for profile in profiles:
        for key in profile:
            normalized = str(key).replace("_", "").lower()
            if any(marker in normalized for marker in _PERFORMANCE_FIELD_MARKERS):
                raise ValueError(f"core selection cannot use strategy performance field: {key}")


def select_core_universe(
    profiles: Sequence[Mapping[str, Any]],
    *,
    target_size: int,
    required_timeframes: Sequence[str] = ("1h", "4h"),
    minimum_history_months: float = 24.0,
) -> dict[str, Any]:
    """Select a deterministic fixed cohort from provenance and coverage only."""

    if target_size < 1:
        raise ValueError("target_size must be positive")
    _reject_performance_fields(profiles)
    grouped: dict[str, dict[str, Mapping[str, Any]]] = defaultdict(dict)
    for profile in profiles:
        grouped[str(profile["instrumentId"])][str(profile["timeframe"])] = profile
    required = tuple(required_timeframes)
    candidates: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for instrument, by_timeframe in sorted(grouped.items()):
        missing = [timeframe for timeframe in required if timeframe not in by_timeframe]
        if missing:
            excluded.append({"instrumentId": instrument, "reasonZh": f"缺少周期: {', '.join(missing)}"})
            continue
        rows = [by_timeframe[timeframe] for timeframe in required]
        history = min(float(row["historyMonths"]) for row in rows)
        if history < minimum_history_months:
            excluded.append({"instrumentId": instrument, "reasonZh": "有效历史不足 24 个月"})
            continue
        if not all(
            bool(row.get("sourceTraceable"))
            and bool(row.get("contractActive"))
            and bool(row.get("symbolMappingStable"))
            for row in rows
        ):
            excluded.append({"instrumentId": instrument, "reasonZh": "来源、状态或符号映射不稳定"})
            continue
        coverage = sum(float(row["coveragePct"]) for row in rows) / len(rows)
        liquidity = sum(float(row["liquidityScore"]) for row in rows) / len(rows)
        score = history * 0.35 + coverage * 0.35 + liquidity * 0.30
        effective_start = max(str(row["effectiveBacktestStart"]) for row in rows)
        candidates.append(
            {
                "instrumentId": instrument,
                "exchange": str(rows[0].get("exchange") or "unknown"),
                "marketType": str(rows[0].get("marketType") or "swap"),
                "effectiveBacktestStart": effective_start,
                "historyMonths": round(history, 4),
                "coveragePct": round(coverage, 6),
                "missingRatePct": round(100.0 - coverage, 6),
                "liquidityScore": round(liquidity, 8),
                "volatilityScore": round(
                    sum(float(row.get("volatilityScore") or 0.0) for row in rows)
                    / len(rows),
                    8,
                ),
                "selectionScore": round(score, 8),
                "profiles": {timeframe: dict(by_timeframe[timeframe]) for timeframe in required},
            }
        )
    ranked = sorted(
        candidates,
        key=lambda row: (-float(row["selectionScore"]), str(row["instrumentId"])),
    )
    selected = ranked[: min(target_size, len(ranked))]
    selected_ids = {str(row["instrumentId"]) for row in selected}
    for row in ranked:
        row["included"] = str(row["instrumentId"]) in selected_ids
        row["reasonZh"] = "满足固定核心池的来源、历史、完整度和活跃度门槛" if row["included"] else "排名超出本轮固定核心池上限"
    common_cutoffs = {
        timeframe: min(
            str(grouped[instrument][timeframe]["latestConfirmed"])
            for instrument in selected_ids
        )
        for timeframe in required
        if selected_ids
    }
    for row in selected:
        row["commonCutoff"] = common_cutoffs
    core = {
        "schemaVersion": "minimal_fixed_core_universe_v1",
        "cohortType": "fixed_core_cohort",
        "historicalPitUniverse": False,
        "selectionUsesStrategyReturns": False,
        "requiredTimeframes": list(required),
        "targetSize": target_size,
        "memberCount": len(selected),
        "commonCutoffByTimeframe": common_cutoffs,
        "members": selected,
        "selectionRows": [*ranked, *excluded],
    }
    return {
        **core,
        "coreUniverseHash": stable_hash(core, prefix="minimal_fixed_core_universe"),
    }
