"""Hierarchical FDR and correlated stress-reversal subfamily selection."""

from __future__ import annotations

import math
from typing import Any, Iterable, Mapping, Sequence


def _bh_adjusted(rows: Iterable[tuple[str, float]]) -> dict[str, float]:
    ordered = sorted(((key, min(max(float(value), 0.0), 1.0)) for key, value in rows), key=lambda row: (row[1], row[0]))
    count = len(ordered)
    adjusted: dict[str, float] = {}
    running = 1.0
    for rank in range(count, 0, -1):
        key, value = ordered[rank - 1]
        running = min(running, value * count / rank)
        adjusted[key] = min(1.0, running)
    return adjusted


def apply_hierarchical_fdr(
    *,
    families: Mapping[str, float],
    subfamilies: Mapping[str, Mapping[str, Any]],
    alpha: float,
) -> dict[str, Any]:
    family_adjusted = _bh_adjusted(families.items())
    global_adjusted = _bh_adjusted(
        (key, float(row["pValue"])) for key, row in subfamilies.items()
    )
    child_adjusted: dict[str, float] = {}
    for family_id in families:
        children = [
            (key, float(row["pValue"]))
            for key, row in subfamilies.items()
            if row.get("familyId") == family_id
        ]
        child_adjusted.update(_bh_adjusted(children))
    return {
        "schemaVersion": "hierarchical_fdr_v2",
        "alpha": alpha,
        "families": {
            key: {
                "rawPValue": float(value),
                "globalFdrAdjustedPValue": family_adjusted[key],
                "passed": family_adjusted[key] <= alpha,
            }
            for key, value in families.items()
        },
        "subfamilies": {
            key: {
                "familyId": str(row["familyId"]),
                "rawPValue": float(row["pValue"]),
                "familyAdjustedPValue": child_adjusted[key],
                "globalFdrAdjustedPValue": global_adjusted[key],
                "passed": (
                    family_adjusted[str(row["familyId"])] <= alpha
                    and child_adjusted[key] <= alpha
                    and global_adjusted[key] <= alpha
                ),
            }
            for key, row in subfamilies.items()
        },
    }


def _correlation(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0
    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_scale = math.sqrt(sum((value - left_mean) ** 2 for value in left))
    right_scale = math.sqrt(sum((value - right_mean) ** 2 for value in right))
    return numerator / (left_scale * right_scale) if left_scale and right_scale else 0.0


def evaluate_stress_reversal_overlap(
    *,
    event_ids_a: set[str],
    event_ids_b: set[str],
    event_returns_a: Sequence[float],
    event_returns_b: Sequence[float],
) -> dict[str, Any]:
    union = event_ids_a | event_ids_b
    jaccard = len(event_ids_a & event_ids_b) / len(union) if union else 0.0
    correlation = _correlation(event_returns_a, event_returns_b)
    shared = jaccard >= 0.50 or abs(correlation) >= 0.80
    return {
        "familyId": "stress_reversal",
        "eventJaccard": jaccard,
        "eventReturnCorrelation": correlation,
        "sharedRiskCluster": shared,
        "maximumFormalEvidenceCount": 1 if shared else 2,
    }


def select_correlated_subfamily_winner(
    candidates: Sequence[Mapping[str, Any]],
    *,
    overlap: Mapping[str, Any],
) -> dict[str, Any]:
    ordered = sorted(
        (dict(row) for row in candidates),
        key=lambda row: (
            float(row.get("adjustedPValue", 1.0)),
            -float(row.get("benchmarkIncrement", 0.0)),
            str(row.get("candidateId", "")),
        ),
    )
    maximum = int(overlap.get("maximumFormalEvidenceCount", len(ordered)))
    selected = ordered[:maximum]
    suppressed = ordered[maximum:]
    return {
        "selectedCandidateId": selected[0]["candidateId"] if selected else None,
        "selectedCandidateIds": [row["candidateId"] for row in selected],
        "suppressedCandidateIds": [row["candidateId"] for row in suppressed],
        "selector": "adjusted_p_then_benchmark_increment_then_candidate_id",
    }
