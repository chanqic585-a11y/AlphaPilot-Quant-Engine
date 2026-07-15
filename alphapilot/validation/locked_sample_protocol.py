from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SampleRequirementResult:
    timeframe: str
    duration_days: int
    trade_count: int
    effective_trade_count: float
    minimum_duration_days: int
    minimum_trade_count: int
    status: str
    hard_evidence_eligible: bool


def sample_requirement(
    *,
    timeframe: str,
    duration_days: int,
    trade_count: int,
    effective_trade_count: float,
) -> SampleRequirementResult:
    thresholds = {
        "1d": (365, 50),
        "1h": (183, 80),
        "15m": (183, 150),
    }
    if timeframe not in thresholds:
        return SampleRequirementResult(
            timeframe=timeframe,
            duration_days=duration_days,
            trade_count=trade_count,
            effective_trade_count=effective_trade_count,
            minimum_duration_days=0,
            minimum_trade_count=0,
            status="unsupported_timeframe",
            hard_evidence_eligible=False,
        )
    minimum_days, minimum_trades = thresholds[timeframe]
    duration_ok = duration_days >= minimum_days
    effective_ok = effective_trade_count >= minimum_trades
    raw_ok = trade_count >= minimum_trades
    if timeframe == "1d" and duration_ok and 30 <= min(
        trade_count, effective_trade_count
    ) < 50:
        status = "exploratory_only"
    elif duration_ok and raw_ok and effective_ok:
        status = "sufficient"
    else:
        status = "insufficient"
    return SampleRequirementResult(
        timeframe=timeframe,
        duration_days=duration_days,
        trade_count=trade_count,
        effective_trade_count=effective_trade_count,
        minimum_duration_days=minimum_days,
        minimum_trade_count=minimum_trades,
        status=status,
        hard_evidence_eligible=status == "sufficient",
    )

