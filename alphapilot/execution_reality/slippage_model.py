"""Report-layer slippage stress model.

This module applies post-processing stress assumptions to summary metrics. It is
not a Freqtrade native matching engine and does not model real order execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class SlippageScenario:
    scenarioName: str
    oneWaySlippagePct: float

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SlippageStressResult:
    scenarioName: str
    rawReturn: float
    slippageAdjustedReturn: float
    rawProfitFactor: float | None
    slippageAdjustedProfitFactor: float | None
    slippageCost: float | None
    slippageAppliedByPostProcessing: bool = True
    notes: list[str] | None = None

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_SLIPPAGE_SCENARIOS = [
    SlippageScenario("one_way_0_05pct", 0.0005),
    SlippageScenario("one_way_0_10pct", 0.0010),
    SlippageScenario("one_way_0_20pct", 0.0020),
    SlippageScenario("one_way_0_30pct", 0.0030),
]


def apply_slippage_stress(
    raw_return_pct: float,
    raw_profit_factor: float | None,
    trade_count: int,
    scenario: SlippageScenario,
    starting_balance: float = 1000.0,
    total_round_trip_notional: float | None = None,
) -> SlippageStressResult:
    """Apply a simple post-processing slippage stress scenario."""
    notes = ["post_processing_model_only", "not_freqtrade_native_matching", "no_real_order_execution"]
    if trade_count <= 0 or starting_balance <= 0:
        return SlippageStressResult(
            scenarioName=scenario.scenarioName,
            rawReturn=raw_return_pct,
            slippageAdjustedReturn=raw_return_pct,
            rawProfitFactor=raw_profit_factor,
            slippageAdjustedProfitFactor=raw_profit_factor,
            slippageCost=None,
            notes=notes + ["trade_count_or_starting_balance_unavailable"],
        )

    if total_round_trip_notional is None:
        total_round_trip_notional = starting_balance * trade_count * 2
        notes.append("total_round_trip_notional_estimated_from_starting_balance_and_trade_count")

    slippage_cost = total_round_trip_notional * scenario.oneWaySlippagePct
    adjusted_return = raw_return_pct - (slippage_cost / starting_balance * 100)
    pf_degradation = min(scenario.oneWaySlippagePct * trade_count * 0.75, 0.85)
    adjusted_pf = None if raw_profit_factor is None else max(raw_profit_factor * (1 - pf_degradation), 0.0)
    return SlippageStressResult(
        scenarioName=scenario.scenarioName,
        rawReturn=round(raw_return_pct, 4),
        slippageAdjustedReturn=round(adjusted_return, 4),
        rawProfitFactor=None if raw_profit_factor is None else round(raw_profit_factor, 4),
        slippageAdjustedProfitFactor=None if adjusted_pf is None else round(adjusted_pf, 4),
        slippageCost=round(slippage_cost, 8),
        notes=notes,
    )

