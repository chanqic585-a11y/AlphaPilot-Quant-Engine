"""Capital Policy V2 contract and one canonical acceptance implementation."""

from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash

from .capacity_model import CAPACITY_POLICY_V1
from .correlation_cluster_policy import CLUSTER_POLICY_V1
from .portfolio_beta_policy import BETA_POLICY_V1, project_portfolio_beta_v1
from .signal_ranking_policy import RANKING_POLICY_V1, rank_signal_batch_v1


ACCEPTANCE_SEQUENCE = [
    "ranking_validation",
    "duplicate_symbol",
    "capacity_and_sizing",
    "single_symbol_risk",
    "same_direction_risk",
    "total_open_risk",
    "correlation_cluster_risk",
    "projected_portfolio_beta",
    "maximum_positions",
]


def build_capital_policy_v2() -> dict[str, Any]:
    policy: dict[str, Any] = {
        "schemaVersion": "s01_formal_capital_competition_v2",
        "source": "v18_executable_capital_policy_correction",
        "initial_capital": 10_000.0,
        "risk_per_trade": 0.01,
        "maximum_concurrent_positions": 6,
        "maximum_open_risk": 0.06,
        "maximum_same_direction_risk": 0.04,
        "maximum_correlation_cluster_risk": 0.02,
        "maximum_single_symbol_risk": 0.01,
        "maximum_portfolio_beta": 1.5,
        "duplicateSymbolPolicy": "reject_while_open",
        "capacityRequirement": "capacity_v1_passed_with_continuous_research_notional",
        "capacityModel": dict(CAPACITY_POLICY_V1),
        "correlationClusterPolicy": dict(CLUSTER_POLICY_V1),
        "portfolioBetaPolicy": dict(BETA_POLICY_V1),
        "rankingPolicy": dict(RANKING_POLICY_V1),
        "rankingFieldDefinitions": {
            "residual_z_more_extreme_first": "eventExtremeResidualZ ascending",
            "recovery_confirmation_stronger_first": "recoverySizeZ descending",
            "liquidity_higher_first": "liquidity30d descending",
            "symbol_id_ascending_tiebreak": "instrumentId ascending unique final tiebreak",
        },
        "acceptanceSequence": list(ACCEPTANCE_SEQUENCE),
        "eventOrderingPolicy": {
            "sameTimestampOrder": ["exit", "funding", "mark_and_equity", "entry"],
            "entryBatchPolicy": "rank_all_same_timestamp_candidates_then_accept_sequentially",
        },
        "positionAccountingPolicy": {
            "currentEquity": "realized_cash_plus_marked_open_position_pnl_after_same_timestamp_updates",
            "markNotional": "absolute_mark_price_times_open_quantity",
            "duplicateSymbol": "any_open_position_with_same_instrument_id",
        },
        "resultDrivenRiskReductionAllowed": False,
        "fallbackFieldPolicy": "no_result_affecting_fallback_fields",
    }
    policy["capitalCompetitionPolicyHash"] = stable_hash(
        policy, prefix="s01_formal_capital_competition_v2"
    )
    return policy


def _instrument(row: Mapping[str, Any]) -> str:
    return str(row.get("instrumentId") or row.get("symbol") or "")


def _direction(row: Mapping[str, Any]) -> str:
    normalized = str(row.get("direction") or "").lower()
    if normalized in {"long", "buy"}:
        return "long"
    if normalized in {"short", "sell"}:
        return "short"
    raise ValueError("direction must be long/buy or short/sell")


def _finite_positive(row: Mapping[str, Any], key: str) -> float | None:
    try:
        value = float(row[key])
    except (KeyError, TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0.0 else None


def _canonical_position(row: Mapping[str, Any]) -> dict[str, Any]:
    instrument = _instrument(row)
    risk = _finite_positive(row, "riskAmount")
    notional = _finite_positive(row, "markNotional")
    beta = row.get("beta")
    cluster = str(row.get("correlationCluster") or "")
    if not instrument or risk is None or notional is None or beta is None or not cluster:
        raise ValueError("Open positions must contain canonical instrument, risk, notional, beta, and cluster")
    beta_value = float(beta)
    if not math.isfinite(beta_value):
        raise ValueError("Open position beta must be finite")
    return {
        **dict(row),
        "instrumentId": instrument,
        "direction": _direction(row),
        "riskAmount": risk,
        "markNotional": notional,
        "beta": beta_value,
        "correlationCluster": cluster,
    }


def accept_signal_batch_v2(
    signals: Sequence[Mapping[str, Any]],
    *,
    open_positions: Sequence[Mapping[str, Any]],
    current_equity: float,
    policy: Mapping[str, Any],
) -> dict[str, Any]:
    equity = float(current_equity)
    if not math.isfinite(equity) or equity <= 0.0:
        raise ValueError("current_equity must be positive and finite")
    state = [_canonical_position(row) for row in open_positions]
    ranking = rank_signal_batch_v1(signals)
    accepted: list[dict[str, Any]] = []
    rejected = [dict(row) for row in ranking["rejected"]]

    for raw in ranking["ranked"]:
        row = dict(raw)
        instrument = _instrument(row)
        reason: str | None = None
        if any(position["instrumentId"] == instrument for position in state):
            reason = "duplicate_symbol_while_open"
        actual_notional = _finite_positive(row, "actualNotional")
        quantity = _finite_positive(row, "quantity")
        risk_amount = _finite_positive(row, "riskAmount")
        cluster = str(row.get("correlationCluster") or "")
        try:
            beta = float(row["beta"])
            beta_valid = math.isfinite(beta)
        except (KeyError, TypeError, ValueError):
            beta, beta_valid = 0.0, False
        if reason is None and (
            row.get("capacityPassed") is not True
            or actual_notional is None
            or quantity is None
            or risk_amount is None
            or not cluster
            or not beta_valid
        ):
            reason = "capacity_or_sizing_rejected"
        direction = _direction(row)
        symbol_risk = sum(
            position["riskAmount"]
            for position in state
            if position["instrumentId"] == instrument
        )
        direction_risk = sum(
            position["riskAmount"]
            for position in state
            if position["direction"] == direction
        )
        total_risk = sum(position["riskAmount"] for position in state)
        cluster_risk = sum(
            position["riskAmount"]
            for position in state
            if position["correlationCluster"] == cluster
        )
        if reason is None and symbol_risk + risk_amount > equity * float(
            policy["maximum_single_symbol_risk"]
        ) + 1e-12:
            reason = "single_symbol_risk_limit"
        elif reason is None and direction_risk + risk_amount > equity * float(
            policy["maximum_same_direction_risk"]
        ) + 1e-12:
            reason = "same_direction_risk_limit"
        elif reason is None and total_risk + risk_amount > equity * float(
            policy["maximum_open_risk"]
        ) + 1e-12:
            reason = "open_risk_limit"
        elif reason is None and cluster_risk + risk_amount > equity * float(
            policy["maximum_correlation_cluster_risk"]
        ) + 1e-12:
            reason = "correlation_cluster_risk_limit"

        beta_evidence: dict[str, Any] | None = None
        if reason is None:
            candidate_position = {
                "direction": direction,
                "markNotional": actual_notional,
                "beta": beta,
            }
            beta_evidence = project_portfolio_beta_v1(
                open_positions=state,
                candidate=candidate_position,
                current_equity=equity,
            )
            if abs(float(beta_evidence["projectedPortfolioBeta"])) > float(
                policy["maximum_portfolio_beta"]
            ) + 1e-12:
                reason = "portfolio_beta_limit"
        if reason is None and len(state) >= int(policy["maximum_concurrent_positions"]):
            reason = "concurrent_position_limit"
        if reason is not None:
            rejected.append({**row, "reason": reason})
            continue

        canonical = {
            **row,
            "instrumentId": instrument,
            "direction": direction,
            "riskAmount": risk_amount,
            "actualNotional": actual_notional,
            "markNotional": actual_notional,
            "quantity": quantity,
            "correlationCluster": cluster,
            "beta": beta,
            "projectedPortfolioBeta": beta_evidence["projectedPortfolioBeta"],
        }
        accepted.append(canonical)
        state.append(canonical)

    final_beta = project_portfolio_beta_v1(
        open_positions=state,
        candidate={"direction": "long", "markNotional": 0.0, "beta": 0.0},
        current_equity=equity,
    )["currentPortfolioBeta"] if state else 0.0
    return {
        "schemaVersion": "s01_formal_capital_acceptance_v2",
        "accepted": accepted,
        "rejected": rejected,
        "stateAfter": {
            "positionCount": len(state),
            "openRisk": sum(row["riskAmount"] for row in state),
            "portfolioBeta": final_beta,
        },
        "audit": {
            "acceptanceSequence": list(ACCEPTANCE_SEQUENCE),
            "rankedCandidateCount": len(ranking["ranked"]),
            "rankingRejectedCount": len(ranking["rejected"]),
            "acceptedCount": len(accepted),
            "rejectedCount": len(rejected),
            "capitalCompetitionPolicyHash": policy.get("capitalCompetitionPolicyHash"),
            "lookaheadReadCount": 0,
        },
    }
