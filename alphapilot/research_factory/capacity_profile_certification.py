"""Real-signal capacity certification without economic-result reads."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pandas as pd

from alphapilot.data_provenance.turnover_derivation import derive_quote_turnover
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.formal_validation.capacity_model import evaluate_capacity_v1


def _normalized_frame(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    if "date" not in frame:
        frame["date"] = frame.index
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _atr(frame: pd.DataFrame, period: int) -> pd.Series:
    prior_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - prior_close).abs(),
            (frame["low"] - prior_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(period, min_periods=period).mean()


def _daily_liquidity(
    frame: pd.DataFrame,
    *,
    semantic_type: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for _, candle in frame.iterrows():
        result = derive_quote_turnover(
            volume=float(candle["volume"]),
            low=float(candle["low"]),
            close=float(candle["close"]),
            semantic_type=semantic_type,
        )
        if result["status"] != "ready":
            continue
        rows.append(
            {
                "timestamp": candle["date"],
                "quoteVolume": float(result["value"]),
            }
        )
    if not rows:
        return []
    table = pd.DataFrame(rows)
    table["day"] = pd.to_datetime(table["timestamp"], utc=True).dt.floor("D")
    daily = table.groupby("day", as_index=False)["quoteVolume"].sum()
    return [
        {"timestamp": row.day.isoformat(), "quoteVolume": float(row.quoteVolume)}
        for row in daily.itertuples(index=False)
    ]


def certify_real_signal_capacity(
    *,
    adapter: Any,
    candidate: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    capacity_profile: Mapping[str, Any],
    current_equity: float,
    signal_start: str | None = None,
    signal_end_exclusive: str | None = None,
) -> dict[str, Any]:
    """Exercise capacity on real structural signals and read no outcomes."""

    timeframe = str(candidate.get("timeframe") or "")
    eligible = set(str(value) for value in capacity_profile.get("eligibleInstruments") or [])
    normalized = {
        symbol: _normalized_frame(frame)
        for symbol, frame in frames.items()
        if symbol in eligible
    }
    if capacity_profile.get("status") != "ready" or not normalized:
        return {
            "schemaVersion": "real_signal_capacity_certification_v1",
            "certificationStatus": "blocked",
            "reason": "capacity_profile_or_frames_not_ready",
            "rawSignalCount": 0,
            "assignedEventCount": 0,
            "capacityInputAvailableCount": 0,
            "capacityInputUnavailableCount": 0,
            "capacityCalculationCount": 0,
            "capacityPassCount": 0,
            "capacityRejectCount": 0,
            "economicResultReadCount": 0,
            "exitResultReadCount": 0,
            "statisticalResultReadCount": 0,
        }

    loaded_signals = [
        dict(row) for row in adapter.load_signals(candidate=candidate, frames=normalized)
    ]
    start = pd.Timestamp(signal_start) if signal_start else None
    end = pd.Timestamp(signal_end_exclusive) if signal_end_exclusive else None
    signals: list[dict[str, Any]] = []
    for signal in loaded_signals:
        timestamp = pd.Timestamp(signal.get("signalTimestamp"))
        if timestamp.tzinfo is None:
            timestamp = timestamp.tz_localize("UTC")
        else:
            timestamp = timestamp.tz_convert("UTC")
        if start is not None and timestamp < start:
            continue
        if end is not None and timestamp >= end:
            continue
        signals.append(signal)
    atr_period = int(candidate["initialStop"]["atrPeriod"])
    atr_multiple = float(candidate["initialStop"]["atrMultiple"])
    atr_by_symbol = {symbol: _atr(frame, atr_period) for symbol, frame in normalized.items()}
    liquidity: dict[str, list[dict[str, Any]]] = {}
    for symbol, frame in normalized.items():
        semantic = (
            capacity_profile.get("turnoverSemanticsByInstrument", {})
            .get(symbol, {})
            .get(timeframe, {})
        )
        semantic_type = str(semantic.get("semanticType") or "")
        liquidity[symbol] = _daily_liquidity(frame, semantic_type=semantic_type)

    available = calculations = passed = rejected = 0
    evidence: list[dict[str, Any]] = []
    for signal in signals:
        symbol = str(signal.get("symbol") or signal.get("instrumentId") or "")
        index = int(signal.get("signalBarIndex") or -1)
        frame = normalized.get(symbol)
        atr_series = atr_by_symbol.get(symbol)
        if frame is None or atr_series is None or index < 0 or index >= len(frame):
            rejected += 1
            continue
        atr_value = float(atr_series.iloc[index])
        entry_price = float(signal["entryPrice"])
        if not np.isfinite(atr_value) or atr_value <= 0.0 or not liquidity.get(symbol):
            rejected += 1
            continue
        available += 1
        stop_distance = atr_value * atr_multiple
        direction = str(signal.get("direction") or candidate.get("direction") or "")
        stop_price = (
            entry_price - stop_distance if direction == "long" else entry_price + stop_distance
        )
        result = evaluate_capacity_v1(
            current_equity=float(current_equity),
            entry_price=entry_price,
            stop_price=stop_price,
            entry_timestamp=str(signal["entryTimestamp"]),
            daily_liquidity=liquidity[symbol],
            instrument_meta={},
        )
        calculations += 1
        if result["capacityPassed"]:
            passed += 1
        else:
            rejected += 1
        evidence.append(
            {
                "signalId": str(signal.get("signalId") or ""),
                "instrumentId": symbol,
                "signalTimestamp": str(signal.get("signalTimestamp") or ""),
                "entryTimestamp": str(signal.get("entryTimestamp") or ""),
                "capacityPassed": bool(result["capacityPassed"]),
                "reason": result.get("reason"),
                "observationCount": int(result.get("observationCount") or 0),
                "riskUtilization": result.get("riskUtilization"),
                "capacityPolicyHash": result.get("capacityPolicyHash"),
            }
        )

    status = (
        "passed"
        if signals and available > 0 and calculations > 0 and passed > 0
        else "blocked"
    )
    report: dict[str, Any] = {
        "schemaVersion": "real_signal_capacity_certification_v1",
        "candidateId": str(candidate.get("candidateId") or ""),
        "dataProfileId": str(capacity_profile.get("profileId") or ""),
        "dataProfileHash": str(capacity_profile.get("profileHash") or ""),
        "signalWindow": {
            "start": signal_start,
            "endExclusive": signal_end_exclusive,
        },
        "certificationStatus": status,
        "reason": None if status == "passed" else "positive_capacity_evidence_missing",
        "unfilteredSignalCount": len(loaded_signals),
        "rawSignalCount": len(signals),
        "assignedEventCount": len(signals),
        "capacityInputAvailableCount": available,
        "capacityInputUnavailableCount": len(signals) - available,
        "capacityCalculationCount": calculations,
        "capacityPassCount": passed,
        "capacityRejectCount": rejected,
        "economicResultReadCount": 0,
        "exitResultReadCount": 0,
        "statisticalResultReadCount": 0,
        "lockedOosReadCount": 0,
        "evidence": evidence,
    }
    report["certificationHash"] = stable_hash(
        report, prefix="real_signal_capacity_certification"
    )
    return report
