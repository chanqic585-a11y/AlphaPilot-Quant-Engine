"""V37J routing before any one-shot Formal result is read."""

from __future__ import annotations

from typing import Any, Iterable, Mapping


def build_v37j_route(
    *, candidate_rows: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    survivors = sorted(
        str(row["candidateId"])
        for row in candidate_rows
        if bool(row.get("prefilterPassed"))
    )
    return {
        "schemaVersion": "alphapilot_v37j_formal_route_v1",
        "status": (
            "formal_freeze_required"
            if survivors
            else "completed_zero_qualified_candidates"
        ),
        "formalCandidateCount": len(survivors),
        "formalCandidateIds": survivors,
        "formalSequence": [
            "code_commit_push",
            "candidate_freeze",
            "panel_freeze",
            "preregistration_commit_push",
            "future_locked_oos_identity",
            "one_shot_authorization",
            "formal_execution",
        ],
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosReadCount": 0,
        "releaseCount": 0,
        "approved": False,
        "demoArm": False,
        "orders": 0,
        "tradeApiUsed": False,
        "withdrawApiUsed": False,
        "privateAccountReadUsed": False,
    }
