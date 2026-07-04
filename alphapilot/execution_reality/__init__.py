"""Execution reality design layer for AlphaPilot.

V13.4.11 introduces research-only liquidity, slippage, order impact, shadow
trading, and live-feasibility structures. These helpers do not call exchange
APIs, read accounts, create orders, or auto trade.
"""

from alphapilot.execution_reality.liquidity_gate import LiquidityGateInput, LiquidityGateResult, evaluate_liquidity_gate
from alphapilot.execution_reality.live_feasibility_score import (
    LiveFeasibilityInput,
    LiveFeasibilityScore,
    calculate_live_feasibility_score,
)
from alphapilot.execution_reality.order_impact import OrderImpactInput, OrderImpactResult, estimate_order_impact
from alphapilot.execution_reality.shadow_trading_schema import ShadowExecutionSnapshot, ShadowOutcome, ShadowSignal
from alphapilot.execution_reality.slippage_model import SlippageScenario, SlippageStressResult, apply_slippage_stress

__all__ = [
    "LiquidityGateInput",
    "LiquidityGateResult",
    "evaluate_liquidity_gate",
    "LiveFeasibilityInput",
    "LiveFeasibilityScore",
    "calculate_live_feasibility_score",
    "OrderImpactInput",
    "OrderImpactResult",
    "estimate_order_impact",
    "ShadowExecutionSnapshot",
    "ShadowOutcome",
    "ShadowSignal",
    "SlippageScenario",
    "SlippageStressResult",
    "apply_slippage_stress",
]

