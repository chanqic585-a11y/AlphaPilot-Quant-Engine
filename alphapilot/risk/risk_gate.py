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
    required_checks: list[str] = field(default_factory=list)


def evaluate_proposal(proposal: Any, context: dict | None = None) -> RiskGateResult:
    """Evaluate a proposal without allowing live execution in V13.2."""
    context = context or {}
    requested_mode = context.get("requested_mode", "research")
    required_checks = [
        "liquidity_gate_required_before_dry_run",
        "execution_reality_required_before_dry_run",
        "shadow_trading_required_before_dry_run",
    ]

    active_locks = explain_active_locks()
    if requested_mode in {"live", "dry_run_execution"} and not is_execution_allowed():
        return RiskGateResult(
            approved=False,
            decision="rejected",
            reasons=["V13.2 default locks reject execution requests."],
            blocked_by=active_locks,
            required_checks=required_checks,
        )

    if requested_mode in {"dry_run_candidate", "dry_run_execution", "live"}:
        missing_checks = []
        if not context.get("liquidity_gate_result"):
            missing_checks.append("missing_liquidity_gate_result")
        if not context.get("execution_reality_result"):
            missing_checks.append("missing_execution_reality_result")
        if not context.get("shadow_trading_result"):
            missing_checks.append("missing_shadow_trading_result")
        if missing_checks:
            return RiskGateResult(
                approved=False,
                decision="rejected_before_dry_run_candidate",
                reasons=[
                    "Execution reality checks are required before Dry-run candidate review.",
                    "No real execution is allowed from this risk gate.",
                    *missing_checks,
                ],
                blocked_by=active_locks,
                required_checks=required_checks,
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
        "execution_reality_placeholder",
        "liquidity_gate_placeholder",
        "shadow_trading_placeholder",
        "protective_order_placeholder",
    ]
    return RiskGateResult(
        approved=True,
        decision="approved_for_research",
        reasons=checks,
        blocked_by=active_locks,
        required_checks=required_checks,
    )
