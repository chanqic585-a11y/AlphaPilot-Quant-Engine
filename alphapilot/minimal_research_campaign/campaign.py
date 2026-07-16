"""Bounded hypothesis inventory and deterministic campaign routing."""

from __future__ import annotations

import hashlib
from typing import Any, Iterable, Mapping, Sequence


def build_hypothesis_inventory(
    *, archived_family_ids: Iterable[str]
) -> list[dict[str, Any]]:
    archived = {value.lower() for value in archived_family_ids}
    breadth_overlap = bool({"trend_pullback", "breakout"}.intersection(archived))
    return [
        {
            "strategyId": "core_idiosyncratic_selloff_recovery_long_4h",
            "familyId": "idiosyncratic_selloff_recovery",
            "timeframe": "4h",
            "direction": "long",
            "noveltyStatus": "accepted",
            "diagnosticOnly": False,
            "formalPassEligible": True,
            "releaseEligible": False,
        },
        {
            "strategyId": "core_breadth_transition_leader_continuation_4h",
            "familyId": "breadth_transition_leader_continuation",
            "timeframe": "4h",
            "direction": "long_short_family",
            "noveltyStatus": "rejected_overlap" if breadth_overlap else "accepted",
            "noveltyReason": "overlaps archived trend-pullback and breakout families" if breadth_overlap else "distinct breadth transition mechanism",
            "diagnosticOnly": False,
            "formalPassEligible": not breadth_overlap,
            "releaseEligible": False,
        },
        {
            "strategyId": "diagnostic_fixed_core_cross_sectional_momentum_1d",
            "familyId": "fixed_core_cross_sectional_momentum",
            "timeframe": "1d",
            "direction": "market_neutral_diagnostic",
            "noveltyStatus": "accepted_diagnostic",
            "diagnosticOnly": True,
            "formalPassEligible": False,
            "releaseEligible": False,
            "pitBoundary": "fixed_core_cohort_is_not_historical_pit",
        },
    ]


def _stable_rank(instrument_id: str) -> str:
    return hashlib.sha256(instrument_id.encode("utf-8")).hexdigest()


def build_representative_universe(
    members: Sequence[Mapping[str, Any]], *, count: int = 10
) -> list[dict[str, Any]]:
    if not 8 <= count <= 12:
        raise ValueError("representative count must be between 8 and 12")
    by_id = {str(row["instrumentId"]): dict(row) for row in members}
    selected: list[dict[str, Any]] = []
    for required in ("BTC-USDT-SWAP", "ETH-USDT-SWAP"):
        if required in by_id:
            selected.append(by_id.pop(required))
    remaining = sorted(
        by_id.values(),
        key=lambda row: (
            -float(row.get("historyMonths") or 0.0),
            -float(row.get("liquidityScore") or 0.0),
            -float(row.get("volatilityScore") or 0.0),
            _stable_rank(str(row["instrumentId"])),
        ),
    )
    if remaining and len(selected) < count:
        bucket_count = count - len(selected)
        step = max(1.0, len(remaining) / bucket_count)
        indices: list[int] = []
        for bucket in range(bucket_count):
            index = min(len(remaining) - 1, int(bucket * step))
            while index in indices and index + 1 < len(remaining):
                index += 1
            indices.append(index)
        selected.extend(remaining[index] for index in indices)
    return sorted(selected[:count], key=lambda row: str(row["instrumentId"]))


def route_prefilter_results(results: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    formal = sorted(
        str(row["strategyId"])
        for row in results
        if bool(row.get("passed")) and not bool(row.get("diagnosticOnly"))
    )
    archived = sorted(
        str(row["strategyId"])
        for row in results
        if not bool(row.get("passed")) and not bool(row.get("diagnosticOnly"))
    )
    diagnostics = sorted(
        str(row["strategyId"])
        for row in results
        if bool(row.get("diagnosticOnly"))
    )
    return {
        "formalStrategyIds": formal,
        "archivedStrategyIds": archived,
        "diagnosticStrategyIds": diagnostics,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
