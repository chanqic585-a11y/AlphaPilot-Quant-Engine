"""Deterministic portfolio allocation across simultaneous research signals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from .signal_ranking import rank_signals


@dataclass(frozen=True)
class CapitalCompetitionPolicy:
    initial_capital: float = 10_000.0
    risk_per_trade: float = 0.01
    maximum_concurrent_positions: int = 6
    maximum_open_risk: float = 0.06
    maximum_same_direction_risk: float = 0.04
    maximum_correlation_cluster_risk: float = 0.02
    maximum_single_symbol_risk: float = 0.01
    maximum_portfolio_beta: float = 1.5


def allocate_competing_signals(
    signals: Sequence[Mapping[str, Any]],
    policy: CapitalCompetitionPolicy,
) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    open_risk = 0.0
    direction_risk: dict[str, float] = {}
    cluster_risk: dict[str, float] = {}
    symbol_risk: dict[str, float] = {}
    portfolio_beta = 0.0

    for row in rank_signals(signals):
        risk = float(row.get("riskAmount") or 0.0) / policy.initial_capital
        direction = str(row.get("direction") or "unknown")
        cluster = str(row.get("correlationCluster") or "unclustered")
        symbol = str(row.get("symbol") or "unknown")
        beta = abs(float(row.get("portfolioBeta") or 0.0))
        reason: str | None = None
        if row.get("capacityPassed") is not True:
            reason = "capacity_rejected"
        elif risk <= 0 or risk > policy.risk_per_trade:
            reason = "per_trade_risk_limit"
        elif len(accepted) >= policy.maximum_concurrent_positions:
            reason = "concurrent_position_limit"
        elif open_risk + risk > policy.maximum_open_risk + 1e-12:
            reason = "open_risk_limit"
        elif direction_risk.get(direction, 0.0) + risk > policy.maximum_same_direction_risk + 1e-12:
            reason = "same_direction_risk_limit"
        elif cluster_risk.get(cluster, 0.0) + risk > policy.maximum_correlation_cluster_risk + 1e-12:
            reason = "correlation_cluster_risk_limit"
        elif symbol_risk.get(symbol, 0.0) + risk > policy.maximum_single_symbol_risk + 1e-12:
            reason = "single_symbol_risk_limit"
        elif portfolio_beta + beta > policy.maximum_portfolio_beta + 1e-12:
            reason = "portfolio_beta_limit"
        if reason:
            rejected.append({**row, "reason": reason})
            continue
        accepted.append(row)
        open_risk += risk
        direction_risk[direction] = direction_risk.get(direction, 0.0) + risk
        cluster_risk[cluster] = cluster_risk.get(cluster, 0.0) + risk
        symbol_risk[symbol] = symbol_risk.get(symbol, 0.0) + risk
        portfolio_beta += beta
    return {
        "accepted": accepted,
        "rejected": rejected,
        "openRiskFraction": open_risk,
        "portfolioBeta": portfolio_beta,
        "capitalCompetitionPassed": True,
        "rankingPolicy": "freshness_liquidity_mechanism_then_candidate_symbol",
    }
