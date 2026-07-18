"""Frozen candidate contracts for the V28-V32 research renewal program."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


_ALLOWED_DIRECTIONAL_TIMEFRAMES = {"4h", "1d"}
_PROHIBITED_LEGACY_FAMILY_TOKENS = (
    "opening_range",
    "range_expansion",
    "ema_pullback",
    "bollinger",
    "volume_rebound",
    "short_rejection",
)
_TYPE_BUDGETS = {
    "directional_event_v2": {"families": 2, "candidates": 4},
    "pair_relative_value_v1": {"families": 2, "candidates": 4},
    "cross_sectional_portfolio_v1": {"families": 2, "candidates": 4},
}


def _required_mapping(value: Mapping[str, Any], field: str) -> dict[str, Any]:
    if not isinstance(value, Mapping) or not value:
        raise ValueError(f"candidate_contract_missing:{field}")
    return dict(value)


def _base_candidate(
    *,
    strategy_type: str,
    family_id: str,
    candidate_id: str,
    mechanism_signature: str,
    data_contract: Mapping[str, Any],
    benchmark_contract: Mapping[str, Any],
    falsification: str,
) -> dict[str, Any]:
    if not all((family_id, candidate_id, mechanism_signature, falsification)):
        raise ValueError("candidate_identity_incomplete")
    frozen_data_contract = _required_mapping(data_contract, "data_contract")
    frozen_benchmark_contract = _required_mapping(
        benchmark_contract, "benchmark_contract"
    )
    if frozen_data_contract.get("formalReady") is not True:
        raise ValueError("candidate_data_contract_not_formal_ready")
    if frozen_benchmark_contract.get("formalGateEligible") is not True:
        raise ValueError("candidate_benchmark_not_formally_comparable")
    return {
        "schemaVersion": "research_renewal_candidate_v1",
        "strategyType": strategy_type,
        "familyId": family_id,
        "candidateId": candidate_id,
        "mechanismSignature": mechanism_signature,
        "dataContract": frozen_data_contract,
        "benchmarkContract": frozen_benchmark_contract,
        "falsification": falsification,
        "resultIndependentDefinition": True,
        "approved": False,
    }


def _freeze_candidate(payload: dict[str, Any]) -> dict[str, Any]:
    payload["candidateHash"] = stable_hash(payload, prefix="v29_candidate")
    return payload


def build_directional_event_candidate(
    *,
    family_id: str,
    candidate_id: str,
    side: str,
    timeframe: str,
    mechanism_signature: str,
    signal_definition: Mapping[str, Any],
    ranking_definition: Mapping[str, Any],
    capacity_definition: Mapping[str, Any],
    risk_definition: Mapping[str, Any],
    exit_definition: Mapping[str, Any],
    data_contract: Mapping[str, Any],
    benchmark_contract: Mapping[str, Any],
    falsification: str,
) -> dict[str, Any]:
    """Build a low-frequency directional event candidate."""

    normalized_timeframe = timeframe.lower()
    if normalized_timeframe not in _ALLOWED_DIRECTIONAL_TIMEFRAMES:
        raise ValueError("directional_event_timeframe")
    if side not in {"long", "short", "long_short"}:
        raise ValueError("directional_event_side")
    payload = _base_candidate(
        strategy_type="directional_event_v2",
        family_id=family_id,
        candidate_id=candidate_id,
        mechanism_signature=mechanism_signature,
        data_contract=data_contract,
        benchmark_contract=benchmark_contract,
        falsification=falsification,
    )
    payload.update(
        {
            "side": side,
            "timeframe": normalized_timeframe,
            "signalDefinition": _required_mapping(
                signal_definition, "signal_definition"
            ),
            "rankingDefinition": _required_mapping(
                ranking_definition, "ranking_definition"
            ),
            "capacityDefinition": _required_mapping(
                capacity_definition, "capacity_definition"
            ),
            "riskDefinition": _required_mapping(risk_definition, "risk_definition"),
            "exitDefinition": _required_mapping(exit_definition, "exit_definition"),
            "singleTradeRGateApplicable": True,
        }
    )
    return _freeze_candidate(payload)


def build_pair_relative_value_candidate(
    *,
    family_id: str,
    candidate_id: str,
    timeframe: str,
    mechanism_signature: str,
    legs: Sequence[Mapping[str, Any]],
    pair_identity: str,
    hedge_ratio_definition: Mapping[str, Any],
    exposure_definition: Mapping[str, Any],
    synchronization_policy: Mapping[str, Any],
    two_leg_capacity_definition: Mapping[str, Any],
    two_leg_cost_definition: Mapping[str, Any],
    fill_failure_policy: Mapping[str, Any],
    exit_definition: Mapping[str, Any],
    data_contract: Mapping[str, Any],
    benchmark_contract: Mapping[str, Any],
    falsification: str,
) -> dict[str, Any]:
    """Build a true two-leg relative-value candidate."""

    if len(legs) != 2:
        raise ValueError("pair_requires_exactly_two_legs")
    frozen_legs = [dict(leg) for leg in legs]
    instrument_ids = [str(leg.get("instrumentId", "")) for leg in frozen_legs]
    sides = {str(leg.get("side", "")) for leg in frozen_legs}
    if len(set(instrument_ids)) != 2 or "" in instrument_ids:
        raise ValueError("pair_requires_distinct_instruments")
    if sides != {"long", "short"}:
        raise ValueError("pair_requires_opposite_legs")
    frozen_sync = _required_mapping(synchronization_policy, "synchronization_policy")
    if frozen_sync.get("maximumEntryLagBars") != 0:
        raise ValueError("pair_requires_synchronized_execution")

    payload = _base_candidate(
        strategy_type="pair_relative_value_v1",
        family_id=family_id,
        candidate_id=candidate_id,
        mechanism_signature=mechanism_signature,
        data_contract=data_contract,
        benchmark_contract=benchmark_contract,
        falsification=falsification,
    )
    payload.update(
        {
            "timeframe": timeframe.lower(),
            "legs": frozen_legs,
            "pairIdentity": pair_identity,
            "pairUniverseFrozenBeforeResults": True,
            "hedgeRatioDefinition": _required_mapping(
                hedge_ratio_definition, "hedge_ratio_definition"
            ),
            "exposureDefinition": _required_mapping(
                exposure_definition, "exposure_definition"
            ),
            "synchronizationPolicy": frozen_sync,
            "twoLegCapacityDefinition": _required_mapping(
                two_leg_capacity_definition, "two_leg_capacity_definition"
            ),
            "twoLegCostDefinition": _required_mapping(
                two_leg_cost_definition, "two_leg_cost_definition"
            ),
            "fillFailurePolicy": _required_mapping(
                fill_failure_policy, "fill_failure_policy"
            ),
            "exitDefinition": _required_mapping(exit_definition, "exit_definition"),
            "singleTradeRGateApplicable": False,
        }
    )
    return _freeze_candidate(payload)


def build_cross_sectional_portfolio_candidate(
    *,
    family_id: str,
    candidate_id: str,
    rebalance_timeframe: str,
    mechanism_signature: str,
    universe_policy: Mapping[str, Any],
    ranking_definition: Mapping[str, Any],
    quantile_policy: Mapping[str, Any],
    exposure_policy: Mapping[str, Any],
    turnover_policy: Mapping[str, Any],
    capacity_definition: Mapping[str, Any],
    cluster_neutrality_policy: Mapping[str, Any],
    btc_beta_policy: Mapping[str, Any],
    data_contract: Mapping[str, Any],
    benchmark_contract: Mapping[str, Any],
    falsification: str,
) -> dict[str, Any]:
    """Build a point-in-time cross-sectional portfolio candidate."""

    frozen_universe = _required_mapping(universe_policy, "universe_policy")
    if frozen_universe.get("pointInTime") is not True:
        raise ValueError("portfolio_requires_pit_universe")
    frozen_ranking = _required_mapping(ranking_definition, "ranking_definition")
    if not frozen_ranking.get("deterministicTieBreak"):
        raise ValueError("portfolio_requires_deterministic_ranking")
    payload = _base_candidate(
        strategy_type="cross_sectional_portfolio_v1",
        family_id=family_id,
        candidate_id=candidate_id,
        mechanism_signature=mechanism_signature,
        data_contract=data_contract,
        benchmark_contract=benchmark_contract,
        falsification=falsification,
    )
    payload.update(
        {
            "rebalanceTimeframe": rebalance_timeframe.lower(),
            "universePolicy": frozen_universe,
            "rankingDefinition": frozen_ranking,
            "quantilePolicy": _required_mapping(quantile_policy, "quantile_policy"),
            "exposurePolicy": _required_mapping(exposure_policy, "exposure_policy"),
            "turnoverPolicy": _required_mapping(turnover_policy, "turnover_policy"),
            "capacityDefinition": _required_mapping(
                capacity_definition, "capacity_definition"
            ),
            "clusterNeutralityPolicy": _required_mapping(
                cluster_neutrality_policy, "cluster_neutrality_policy"
            ),
            "btcBetaPolicy": _required_mapping(btc_beta_policy, "btc_beta_policy"),
            "singleTradeRGateApplicable": False,
        }
    )
    return _freeze_candidate(payload)


def validate_candidate_novelty(
    *,
    candidate: Mapping[str, Any],
    prior_candidate_ids: set[str],
    prior_family_ids: set[str],
    failed_mechanism_signatures: set[str],
) -> dict[str, Any]:
    """Reject reused identities and mechanisms before any result is read."""

    reasons: list[str] = []
    candidate_id = str(candidate.get("candidateId", ""))
    family_id = str(candidate.get("familyId", ""))
    mechanism = str(candidate.get("mechanismSignature", ""))
    if candidate_id in prior_candidate_ids:
        reasons.append("candidate_identity_reused")
    if mechanism in failed_mechanism_signatures:
        reasons.append("failed_mechanism_reused")
    if any(token in family_id.lower() for token in _PROHIBITED_LEGACY_FAMILY_TOKENS):
        reasons.append("prohibited_legacy_family")
    elif family_id in prior_family_ids:
        reasons.append("prior_family_reused")
    return {
        "candidateId": candidate_id,
        "familyId": family_id,
        "novel": not reasons,
        "rejectionReasons": reasons,
        "checkedBeforeResults": True,
    }


def validate_candidate_batch(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Enforce the pre-registered campaign type and family budgets."""

    if len(candidates) > 12:
        raise ValueError("campaign_candidate_budget_exceeded")
    by_type: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        strategy_type = str(candidate.get("strategyType", ""))
        if strategy_type not in _TYPE_BUDGETS:
            raise ValueError("unsupported_candidate_type")
        by_type[strategy_type].append(candidate)

    summary: dict[str, Any] = {}
    for strategy_type, rows in by_type.items():
        budget = _TYPE_BUDGETS[strategy_type]
        family_counts = Counter(str(row.get("familyId", "")) for row in rows)
        if len(rows) > budget["candidates"]:
            raise ValueError("candidate_type_budget_exceeded")
        if len(family_counts) > budget["families"]:
            raise ValueError("candidate_family_budget_exceeded")
        summary[strategy_type] = {
            "candidateCount": len(rows),
            "familyCount": len(family_counts),
        }
    return {
        "valid": True,
        "candidateCount": len(candidates),
        "typeSummary": summary,
        "budgetHash": stable_hash(_TYPE_BUDGETS, prefix="v29_candidate_budget"),
    }
