"""Risk gate skeleton for AlphaPilot proposals."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alphapilot.core.locks import explain_active_locks, is_execution_allowed


@dataclass
class RiskGateResult:
    approved: bool
    decision: str
    reasons: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)


def evaluate_proposal(proposal: Any, context: dict | None = None) -> RiskGateResult:
    """Evaluate a proposal without allowing live execution in V13.2."""
    context = context or {}
    requested_mode = context.get("requested_mode", "research")

    active_locks = explain_active_locks()
    if requested_mode in {"live", "dry_run_execution"} and not is_execution_allowed():
        return RiskGateResult(
            approved=False,
            decision="rejected",
            reasons=["V13.2 default locks reject execution requests."],
            blocked_by=active_locks,
        )

    checks = [
        "system_locks_checked",
        "single_trade_risk_placeholder",
        "max_position_placeholder",
        "btc_crash_placeholder",
        "news_risk_placeholder",
        "signal_expiry_placeholder",
        "market_latency_placeholder",
        "slippage_placeholder",
        "protective_order_placeholder",
    ]
    return RiskGateResult(
        approved=True,
        decision="approved_for_research",
        reasons=checks,
        blocked_by=active_locks,
    )
