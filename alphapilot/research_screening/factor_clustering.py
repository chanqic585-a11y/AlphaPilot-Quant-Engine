"""Deterministic factor-value correlation clusters."""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


def cluster_factors(
    factors: Mapping[str, pd.DataFrame],
    *,
    threshold: float = 0.9,
    duplicate_threshold: float = 0.97,
) -> dict[str, object]:
    identifiers = sorted(factors)
    parents = {item: item for item in identifiers}

    def root(item: str) -> str:
        while parents[item] != item:
            parents[item] = parents[parents[item]]
            item = parents[item]
        return item

    def union(left: str, right: str) -> None:
        first, second = root(left), root(right)
        if first != second:
            parents[max(first, second)] = min(first, second)

    pairs: list[dict[str, object]] = []
    duplicates: list[dict[str, object]] = []
    for left_index, left in enumerate(identifiers):
        for right in identifiers[left_index + 1 :]:
            first, second = factors[left].stack().align(factors[right].stack(), join="inner")
            valid = pd.concat([first, second], axis=1).dropna()
            correlation = (
                float(valid.iloc[:, 0].rank().corr(valid.iloc[:, 1].rank()))
                if len(valid) > 1
                else 0.0
            )
            row = {"left": left, "right": right, "factorValueSpearman": correlation}
            pairs.append(row)
            if abs(correlation) >= threshold:
                union(left, right)
            if abs(correlation) >= duplicate_threshold:
                duplicates.append(row)
    grouped: dict[str, list[str]] = {}
    for identifier in identifiers:
        grouped.setdefault(root(identifier), []).append(identifier)
    clusters = [
        {
            "clusterId": f"factor_cluster_{number:03d}",
            "factorIds": members,
            "primaryRepresentative": members[0],
            "alternateRepresentative": members[1] if len(members) > 1 else None,
        }
        for number, members in enumerate(sorted(grouped.values(), key=lambda value: value[0]), start=1)
    ]
    return {
        "schemaVersion": "factor_clusters_v1",
        "correlationThreshold": threshold,
        "highlyDuplicateThreshold": duplicate_threshold,
        "pairs": pairs,
        "highlyDuplicatePairs": duplicates,
        "clusters": clusters,
    }
