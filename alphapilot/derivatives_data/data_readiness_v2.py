"""Fail-closed readiness decision for the three preregistered V2 directions."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


def evaluate_v2_data_readiness(
    directions: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    required = {"A1", "A2", "B", "C"}
    missing_directions = sorted(required - directions.keys())
    if missing_directions:
        raise ValueError(f"missing direction readiness: {', '.join(missing_directions)}")

    formal_top_levels: set[str] = set()
    provisional: list[str] = []
    for direction in ("A1", "A2", "B", "C"):
        record = directions[direction]
        if bool(record.get("formalReady")):
            formal_top_levels.add("A" if direction in {"A1", "A2"} else direction)
        if bool(record.get("provisionalReady")) and not bool(record.get("formalReady")):
            provisional.append(direction)

    formal_count = len(formal_top_levels)
    campaign_may_run = formal_count >= 2
    core = {
        "schemaVersion": "v13_27_1_11_data_readiness_v2",
        "status": "ready_for_preregistration" if campaign_may_run else "data_not_ready",
        "campaignMayRun": campaign_may_run,
        "minimumFormalDirectionCount": 2,
        "formalReadyDirectionCount": formal_count,
        "formalReadyDirections": sorted(formal_top_levels),
        "provisionalReadyDirections": provisional,
        "directions": {name: dict(directions[name]) for name in sorted(directions)},
        "failClosedAction": (
            "continue_to_preregistration"
            if campaign_may_run
            else "commit_evidence_and_do_not_run_campaign"
        ),
    }
    return {**core, "readinessHash": stable_hash(core, prefix="data_readiness_v2")}
