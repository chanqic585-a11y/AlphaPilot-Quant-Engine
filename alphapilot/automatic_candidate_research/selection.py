"""Development-only projections and stable-neighborhood selection."""

from __future__ import annotations

from statistics import median
from typing import Any, Mapping, Sequence

from .contracts import V36ContractError


_REQUIRED_METRICS: dict[str, tuple[str, ...]] = {
    "directional": (
        "eventCount",
        "profitFactor",
        "averageNetR",
        "totalNetR",
        "mfe",
        "mae",
        "totalCostR",
        "benchmarkIncrementNetR",
        "maxDrawdownR",
        "concentration",
    ),
    "pair": (
        "spreadReturn",
        "dualLegCostR",
        "residualStability",
        "halfLife",
        "structuralBreakDetected",
        "grossExposure",
        "netExposure",
        "dualLegCapacity",
        "pairBenchmarkIncrement",
        "maxDrawdownR",
    ),
    "portfolio": (
        "portfolioNetReturn",
        "maxDrawdownR",
        "turnover",
        "totalCostR",
        "beta",
        "grossExposure",
        "netExposure",
        "capacity",
        "positivePeriodRatio",
        "benchmarkIncrement",
    ),
    "event": (
        "abnormalReturn",
        "matchedBenchmarkReturn",
        "eventClusterCount",
        "causalTimingValid",
        "eventCount",
        "maxDrawdownR",
    ),
}


def _required_text(value: object, *, name: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise V36ContractError(f"{name}_missing")
    return normalized


def _number(value: object, *, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise V36ContractError(f"invalid_metric:{name}")
    return float(value)


def project_development_evidence(evidence: Mapping[str, object]) -> dict[str, Any]:
    """Map type-specific Development evidence onto a common selection surface."""

    split = _required_text(evidence.get("split"), name="split")
    if split != "development":
        raise V36ContractError("development_only_selection")
    strategy_type = _required_text(evidence.get("strategyType"), name="strategy_type")
    if strategy_type not in _REQUIRED_METRICS:
        raise V36ContractError(f"unsupported_strategy_type:{strategy_type}")
    metrics = evidence.get("metrics")
    if not isinstance(metrics, Mapping):
        raise V36ContractError("metrics_missing")
    for field in _REQUIRED_METRICS[strategy_type]:
        if field not in metrics:
            raise V36ContractError(f"missing_metric:{field}")

    if strategy_type == "directional":
        selection_net_r = _number(metrics["averageNetR"], name="averageNetR")
        profit_factor = _number(metrics["profitFactor"], name="profitFactor")
    elif strategy_type == "pair":
        selection_net_r = _number(metrics["spreadReturn"], name="spreadReturn") - _number(
            metrics["dualLegCostR"], name="dualLegCostR"
        )
        profit_factor = 1.0 + selection_net_r
    elif strategy_type == "portfolio":
        selection_net_r = _number(
            metrics["portfolioNetReturn"], name="portfolioNetReturn"
        )
        profit_factor = 1.0 + selection_net_r
    else:
        selection_net_r = _number(metrics["abnormalReturn"], name="abnormalReturn") - _number(
            metrics["matchedBenchmarkReturn"], name="matchedBenchmarkReturn"
        )
        profit_factor = 1.0 + selection_net_r

    return {
        "schemaVersion": "v36_development_projection_v1",
        "candidateId": _required_text(evidence.get("candidateId"), name="candidate_id"),
        "trialId": _required_text(evidence.get("trialId"), name="trial_id"),
        "trialIndex": int(evidence.get("trialIndex", 0)),
        "strategyType": strategy_type,
        "split": split,
        "selectionNetR": selection_net_r,
        "profitFactor": profit_factor,
        "maxDrawdownR": _number(metrics["maxDrawdownR"], name="maxDrawdownR"),
        "typeSpecificMetrics": dict(metrics),
        "lockedOosReadCount": 0,
        "prefilterPassed": bool(evidence.get("prefilterPassed", True)),
    }


def select_stable_neighborhood(
    *,
    candidate_id: str,
    projections: Sequence[Mapping[str, object]],
) -> dict[str, Any]:
    """Select a stable preregistered platform without chasing the best point."""

    if not 3 <= len(projections) <= 8:
        raise V36ContractError("neighborhood_size_out_of_bounds")
    normalized_candidate_id = _required_text(candidate_id, name="candidate_id")
    rows = sorted(projections, key=lambda row: int(row.get("trialIndex", 0)))
    if any(row.get("split") != "development" for row in rows):
        raise V36ContractError("development_only_selection")
    if any(row.get("candidateId") != normalized_candidate_id for row in rows):
        raise V36ContractError("candidate_identity_mismatch")
    if any(int(row.get("lockedOosReadCount", 0)) != 0 for row in rows):
        raise V36ContractError("locked_oos_read_before_formal")

    scores = [_number(row.get("selectionNetR"), name="selectionNetR") for row in rows]
    profit_factors = [_number(row.get("profitFactor"), name="profitFactor") for row in rows]
    drawdowns = [_number(row.get("maxDrawdownR"), name="maxDrawdownR") for row in rows]
    positive_count = sum(score > 0 for score in scores)
    same_direction_majority = positive_count > len(scores) / 2
    score_baseline = max(median(abs(score) for score in scores), 1e-12)
    pf_baseline = max(median(abs(value - 1.0) for value in profit_factors), 1e-12)
    isolated_spike = (
        max(abs(score) for score in scores) > score_baseline * 2.0
        or max(abs(value - 1.0) for value in profit_factors) > pf_baseline * 2.0
    )
    drawdown_baseline = max(median(drawdowns), 1e-12)
    drawdown_uncontrolled = max(drawdowns) > drawdown_baseline * 2.0
    prefilter_positive_count = sum(bool(row.get("prefilterPassed", True)) for row in rows)
    prefilter_majority = prefilter_positive_count > len(rows) / 2
    eligible = (
        prefilter_majority
        and same_direction_majority
        and not isolated_spike
        and not drawdown_uncontrolled
    )
    selected = rows[len(rows) // 2] if eligible else None

    return {
        "schemaVersion": "v36_stable_neighborhood_v1",
        "candidateId": normalized_candidate_id,
        "eligible": eligible,
        "selectedTrialId": str(selected["trialId"]) if selected is not None else None,
        "reason": (
            "stable_parameter_neighborhood"
            if eligible
            else (
                "cheap_prefilter_failed"
                if not prefilter_majority
                else "unstable_parameter_neighborhood"
            )
        ),
        "gate": {
            "sameDirectionMajority": same_direction_majority,
            "isolatedSpike": isolated_spike,
            "drawdownUncontrolled": drawdown_uncontrolled,
            "positiveTrialCount": positive_count,
            "trialCount": len(rows),
            "prefilterMajority": prefilter_majority,
            "prefilterPositiveCount": prefilter_positive_count,
        },
        "lockedOosReadCount": 0,
    }
