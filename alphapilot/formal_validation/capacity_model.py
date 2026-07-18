"""Frozen, point-in-time liquidity capacity and position sizing for V18."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from statistics import median
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


CAPACITY_POLICY_V1: dict[str, Any] = {
    "schemaVersion": "s01_capacity_model_v1",
    "method": "median_prior_completed_utc_daily_quote_turnover",
    "inputs": [
        "currentEquity",
        "entryPrice",
        "stopPrice",
        "priorDailyLiquidity",
        "instrumentMetadataOnlyWhenVolumeConversionRequiresIt",
    ],
    "sourcePriority": [
        "quote_volume",
        "base_volume_times_close",
        "verified_contract_volume_times_contract_value_multiplier_and_close",
    ],
    "lookbackCompletedUtcDays": 30,
    "minimumCompletedUtcDays": 24,
    "riskBudgetFraction": 0.01,
    "turnoverParticipationFraction": 0.0005,
    "minimumRiskUtilization": 0.50,
    "thresholds": {
        "minimumRiskUtilization": 0.50,
        "maximumTurnoverParticipation": 0.0005,
    },
    "missingDataPolicy": "reject_without_verified_quote_turnover_semantics",
    "positionQuantization": "continuous_research_notional_without_historical_exchange_lot_assumption",
    "invalidInputPolicy": "reject_nonpositive_equity_price_or_stop_distance",
    "pointInTimePolicy": "strictly_prior_completed_utc_days_only",
}
CAPACITY_POLICY_V1["definitionHash"] = stable_hash(
    CAPACITY_POLICY_V1, prefix="s01_capacity_model_v1"
)


def _utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _positive(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) and number > 0.0 else None


def _daily_quote_turnover(
    row: Mapping[str, Any], instrument_meta: Mapping[str, Any]
) -> tuple[float | None, str | None]:
    quote_volume = _positive(row.get("quoteVolume"))
    if quote_volume is not None:
        return quote_volume, "quote_volume"

    close = _positive(row.get("close"))
    base_volume = _positive(row.get("baseVolume"))
    if close is not None and base_volume is not None:
        return close * base_volume, "base_volume_derived_quote"

    contract_volume = _positive(row.get("contractVolume"))
    contract_value = _positive(instrument_meta.get("contractValue"))
    multiplier = _positive(instrument_meta.get("contractMultiplier"))
    verified = instrument_meta.get("contractVolumeSemanticsVerified") is True
    if (
        close is not None
        and contract_volume is not None
        and contract_value is not None
        and multiplier is not None
        and verified
    ):
        return (
            close * contract_volume * contract_value * multiplier,
            "contract_volume_derived_quote",
        )
    return None, None


def _rejected(reason: str, **evidence: Any) -> dict[str, Any]:
    return {
        "schemaVersion": CAPACITY_POLICY_V1["schemaVersion"],
        "capacityPassed": False,
        "reason": reason,
        "lookaheadReadCount": 0,
        "capacityPolicyHash": CAPACITY_POLICY_V1["definitionHash"],
        **evidence,
    }


def evaluate_capacity_v1(
    *,
    current_equity: float,
    entry_price: float,
    stop_price: float,
    entry_timestamp: str,
    daily_liquidity: Sequence[Mapping[str, Any]],
    instrument_meta: Mapping[str, Any],
) -> dict[str, Any]:
    """Size one candidate without reading its entry day or future liquidity."""

    equity = _positive(current_equity)
    entry = _positive(entry_price)
    stop = _positive(stop_price)
    if equity is None:
        return _rejected("invalid_current_equity")
    if entry is None or stop is None or entry == stop:
        return _rejected("invalid_entry_or_stop_price")

    entry_time = _utc(entry_timestamp)
    by_day: dict[object, tuple[float, str]] = {}
    saw_unverified = False
    for row in daily_liquidity:
        try:
            timestamp = _utc(row.get("timestamp"))
        except (TypeError, ValueError):
            continue
        if timestamp.date() >= entry_time.date():
            continue
        turnover, source = _daily_quote_turnover(row, instrument_meta)
        if turnover is None or source is None:
            saw_unverified = True
            continue
        by_day[timestamp.date()] = (turnover, source)

    observations = [by_day[day] for day in sorted(by_day)[-30:]]
    if len(observations) < int(CAPACITY_POLICY_V1["minimumCompletedUtcDays"]):
        reason = (
            "liquidity_semantics_unverified"
            if saw_unverified and not observations
            else "insufficient_completed_liquidity_days"
        )
        return _rejected(reason, observationCount=len(observations))

    turnover_values = [row[0] for row in observations]
    sources = {row[1] for row in observations}
    liquidity_source = next(iter(sources)) if len(sources) == 1 else "mixed_verified_quote"
    median_turnover = float(median(turnover_values))
    stop_distance_pct = abs(entry - stop) / entry
    risk_budget = equity * float(CAPACITY_POLICY_V1["riskBudgetFraction"])
    risk_based_notional = risk_budget / stop_distance_pct
    capacity_notional = median_turnover * float(
        CAPACITY_POLICY_V1["turnoverParticipationFraction"]
    )
    actual_notional = min(risk_based_notional, capacity_notional)
    quantity = actual_notional / entry
    risk_utilization = actual_notional / risk_based_notional

    evidence = {
        "liquiditySource": liquidity_source,
        "observationCount": len(observations),
        "medianDailyQuoteTurnover30d": median_turnover,
        "riskBudget": risk_budget,
        "stopDistancePct": stop_distance_pct,
        "riskBasedNotional": risk_based_notional,
        "capacityNotional": capacity_notional,
        "quantity": quantity,
        "actualNotional": actual_notional,
        "positionSizingMode": "continuous_research_notional",
        "riskAmount": actual_notional * stop_distance_pct,
        "riskUtilization": risk_utilization,
    }
    if quantity <= 0.0 or actual_notional <= 0.0:
        return _rejected("nonpositive_research_position", **evidence)
    if risk_utilization + 1e-12 < float(CAPACITY_POLICY_V1["minimumRiskUtilization"]):
        return _rejected("risk_utilization_below_minimum", **evidence)
    return {
        "schemaVersion": CAPACITY_POLICY_V1["schemaVersion"],
        "capacityPassed": True,
        "reason": None,
        "lookaheadReadCount": 0,
        "capacityPolicyHash": CAPACITY_POLICY_V1["definitionHash"],
        **evidence,
    }
