"""Point-in-time correlation clusters for V18 portfolio competition."""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


SHARED_UNKNOWN_CLUSTER = "shared_unknown_cluster"
CLUSTER_POLICY_V1: dict[str, Any] = {
    "schemaVersion": "s01_correlation_cluster_policy_v1",
    "method": "positive_pearson_connected_components_union_find",
    "returnDefinition": "utc_daily_log_return",
    "lookbackBars": 90,
    "minimumAlignedBars": 60,
    "threshold": 0.75,
    "thresholdSign": "positive_only",
    "recomputeSchedule": "utc_00_00_daily_using_strictly_prior_data",
    "clusterIdMethod": "sha256_of_sorted_component_members",
    "missingDataPolicy": SHARED_UNKNOWN_CLUSTER,
    "zeroVariancePolicy": SHARED_UNKNOWN_CLUSTER,
}
CLUSTER_POLICY_V1["definitionHash"] = stable_hash(
    CLUSTER_POLICY_V1, prefix="s01_correlation_cluster_policy_v1"
)


def _utc(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _series(
    rows: Sequence[Mapping[str, Any]], as_of: datetime
) -> dict[object, float]:
    values: dict[object, float] = {}
    for row in rows:
        try:
            timestamp = _utc(row.get("timestamp"))
            value = float(row.get("return"))
        except (TypeError, ValueError):
            continue
        if timestamp.date() >= as_of.date() or not math.isfinite(value):
            continue
        values[timestamp.date()] = value
    return {day: values[day] for day in sorted(values)[-90:]}


def _pearson(left: list[float], right: list[float]) -> float | None:
    count = len(left)
    if count == 0 or count != len(right):
        return None
    left_mean = sum(left) / count
    right_mean = sum(right) / count
    covariance = sum(
        (left[index] - left_mean) * (right[index] - right_mean)
        for index in range(count)
    )
    left_ss = sum((value - left_mean) ** 2 for value in left)
    right_ss = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_ss * right_ss)
    if denominator <= 1e-18:
        return None
    return covariance / denominator


def build_correlation_clusters_v1(
    return_panel: Mapping[str, Sequence[Mapping[str, Any]]],
    *,
    as_of_timestamp: str,
) -> dict[str, Any]:
    as_of = _utc(as_of_timestamp)
    symbols = sorted(str(symbol) for symbol in return_panel)
    panel = {symbol: _series(return_panel[symbol], as_of) for symbol in symbols}
    eligible = {
        symbol
        for symbol in symbols
        if len(panel[symbol]) >= int(CLUSTER_POLICY_V1["minimumAlignedBars"])
    }
    parent = {symbol: symbol for symbol in eligible}

    def find(symbol: str) -> str:
        while parent[symbol] != symbol:
            parent[symbol] = parent[parent[symbol]]
            symbol = parent[symbol]
        return symbol

    def union(left: str, right: str) -> None:
        left_root, right_root = find(left), find(right)
        if left_root == right_root:
            return
        first, second = sorted((left_root, right_root))
        parent[second] = first

    pair_evidence: list[dict[str, Any]] = []
    eligible_sorted = sorted(eligible)
    for left_index, left in enumerate(eligible_sorted):
        for right in eligible_sorted[left_index + 1 :]:
            overlap = sorted(set(panel[left]) & set(panel[right]))
            if len(overlap) < int(CLUSTER_POLICY_V1["minimumAlignedBars"]):
                correlation = None
            else:
                correlation = _pearson(
                    [panel[left][day] for day in overlap],
                    [panel[right][day] for day in overlap],
                )
            linked = correlation is not None and correlation >= float(
                CLUSTER_POLICY_V1["threshold"]
            )
            if linked:
                union(left, right)
            pair_evidence.append(
                {
                    "left": left,
                    "right": right,
                    "alignedBars": len(overlap),
                    "pearson": correlation,
                    "linked": linked,
                }
            )

    components: dict[str, list[str]] = {}
    for symbol in eligible_sorted:
        components.setdefault(find(symbol), []).append(symbol)
    assignments: dict[str, str] = {}
    for members in components.values():
        ordered = sorted(members)
        cluster_id = stable_hash(ordered, prefix="corr_cluster")
        for symbol in ordered:
            assignments[symbol] = cluster_id
    for symbol in symbols:
        assignments.setdefault(symbol, SHARED_UNKNOWN_CLUSTER)
    return {
        "schemaVersion": CLUSTER_POLICY_V1["schemaVersion"],
        "assignments": dict(sorted(assignments.items())),
        "pairEvidence": pair_evidence,
        "unknownSymbols": sorted(symbol for symbol in symbols if symbol not in eligible),
        "frozenUntil": as_of.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "lookaheadReadCount": 0,
        "clusterPolicyHash": CLUSTER_POLICY_V1["definitionHash"],
    }
