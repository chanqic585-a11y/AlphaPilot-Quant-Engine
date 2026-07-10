"""Deterministic transaction-cost, latency, gap, and loss-streak stress matrix."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean


@dataclass(frozen=True)
class CostScenarioResult:
    scenarioId: str
    evaluated: bool
    blockedReason: str | None
    returnSource: str
    costMultiplier: float
    tradeCount: int
    totalReturn: float | None
    meanReturn: float | None
    winRate: float | None
    profitFactor: float | None
    worstTrade: float | None
    worstConsecutiveLoss: float | None


@dataclass(frozen=True)
class CostStressReport:
    scenarios: dict[str, CostScenarioResult]
    baseFeeRate: float
    baseSlippageRate: float
    extremeGapShock: float
    allRequiredScenariosEvaluated: bool
    baselinePositive: bool
    cost2xPositive: bool


def _worst_consecutive_loss(returns: list[float]) -> float:
    current = 0.0
    worst = 0.0
    for value in returns:
        if value < 0:
            current += value
            worst = min(worst, current)
        else:
            current = 0.0
    return worst


def _evaluate(
    scenario_id: str,
    gross_returns: list[float],
    *,
    fee_rate: float,
    slippage_rate: float,
    cost_multiplier: float,
    return_source: str,
    gap_shock: float = 0.0,
) -> CostScenarioResult:
    round_trip_cost = 2 * (fee_rate + slippage_rate) * cost_multiplier
    net_returns = [value - round_trip_cost for value in gross_returns]
    if gap_shock:
        worst_index = min(range(len(net_returns)), key=net_returns.__getitem__)
        net_returns[worst_index] -= gap_shock
    gains = sum(value for value in net_returns if value > 0)
    losses = abs(sum(value for value in net_returns if value < 0))
    return CostScenarioResult(
        scenarioId=scenario_id,
        evaluated=True,
        blockedReason=None,
        returnSource=return_source,
        costMultiplier=cost_multiplier,
        tradeCount=len(net_returns),
        totalReturn=sum(net_returns),
        meanReturn=fmean(net_returns),
        winRate=sum(value > 0 for value in net_returns) / len(net_returns),
        profitFactor=(gains / losses) if losses > 0 else None,
        worstTrade=min(net_returns),
        worstConsecutiveLoss=_worst_consecutive_loss(net_returns),
    )


def _blocked_latency(trade_count: int) -> CostScenarioResult:
    return CostScenarioResult(
        scenarioId="one_bar_delay",
        evaluated=False,
        blockedReason="missing_delayed_returns",
        returnSource="missing",
        costMultiplier=1.0,
        tradeCount=trade_count,
        totalReturn=None,
        meanReturn=None,
        winRate=None,
        profitFactor=None,
        worstTrade=None,
        worstConsecutiveLoss=None,
    )


def evaluate_cost_stress(
    *,
    gross_returns: list[float],
    base_fee_rate: float,
    base_slippage_rate: float,
    delayed_returns: list[float] | None = None,
    extreme_gap_shock: float = 0.02,
) -> CostStressReport:
    if not gross_returns or not all(math.isfinite(value) for value in gross_returns):
        raise ValueError("gross_returns must be non-empty and finite")
    rates = [base_fee_rate, base_slippage_rate, extreme_gap_shock]
    if not all(math.isfinite(value) and value >= 0 for value in rates):
        raise ValueError("Cost and gap assumptions must be finite and non-negative")
    if delayed_returns is not None:
        if len(delayed_returns) != len(gross_returns):
            raise ValueError("delayed_returns must align with gross_returns")
        if not all(math.isfinite(value) for value in delayed_returns):
            raise ValueError("delayed_returns must be finite")

    scenarios = {
        "baseline": _evaluate(
            "baseline",
            gross_returns,
            fee_rate=base_fee_rate,
            slippage_rate=base_slippage_rate,
            cost_multiplier=1.0,
            return_source="gross_returns",
        ),
        "cost_2x": _evaluate(
            "cost_2x",
            gross_returns,
            fee_rate=base_fee_rate,
            slippage_rate=base_slippage_rate,
            cost_multiplier=2.0,
            return_source="gross_returns",
        ),
        "cost_3x": _evaluate(
            "cost_3x",
            gross_returns,
            fee_rate=base_fee_rate,
            slippage_rate=base_slippage_rate,
            cost_multiplier=3.0,
            return_source="gross_returns",
        ),
        "extreme_gap": _evaluate(
            "extreme_gap",
            gross_returns,
            fee_rate=base_fee_rate,
            slippage_rate=base_slippage_rate,
            cost_multiplier=1.0,
            return_source="gross_returns_with_single_worst_trade_gap",
            gap_shock=extreme_gap_shock,
        ),
    }
    scenarios["one_bar_delay"] = (
        _evaluate(
            "one_bar_delay",
            delayed_returns,
            fee_rate=base_fee_rate,
            slippage_rate=base_slippage_rate,
            cost_multiplier=1.0,
            return_source="delayed_returns",
        )
        if delayed_returns is not None
        else _blocked_latency(len(gross_returns))
    )
    ordered = {
        key: scenarios[key]
        for key in ("baseline", "cost_2x", "cost_3x", "one_bar_delay", "extreme_gap")
    }
    baseline_total = ordered["baseline"].totalReturn or 0.0
    cost_2x_total = ordered["cost_2x"].totalReturn or 0.0
    return CostStressReport(
        scenarios=ordered,
        baseFeeRate=base_fee_rate,
        baseSlippageRate=base_slippage_rate,
        extremeGapShock=extreme_gap_shock,
        allRequiredScenariosEvaluated=all(item.evaluated for item in ordered.values()),
        baselinePositive=baseline_total > 0,
        cost2xPositive=cost_2x_total > 0,
    )
