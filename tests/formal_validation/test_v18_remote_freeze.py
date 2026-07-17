from __future__ import annotations

from alphapilot.formal_validation.v18_remote_freeze import (
    evaluate_v18_remote_freeze,
)


def _snapshot() -> dict[str, object]:
    return {
        "headCommit": "v18-commit",
        "implementationCommit": "implementation-commit",
        "upstreamContainsHead": True,
        "headContainsImplementationCommit": True,
        "upstreamContainsImplementationCommit": True,
        "preregistrationTracked": True,
        "preregistrationClean": True,
        "preregistrationOnUpstream": True,
        "remoteTags": {
            "v13.27.1.17": "v17-commit",
            "v13.27.1.18": "v18-commit",
        },
    }


def test_remote_freeze_requires_published_preregistration_and_v18_tag() -> None:
    snapshot = _snapshot()
    snapshot["preregistrationOnUpstream"] = False
    snapshot["remoteTags"] = {"v13.27.1.17": "v17-commit"}

    audit = evaluate_v18_remote_freeze(snapshot)

    assert audit["status"] == "blocked"
    assert audit["route"] == "blocked_remote_freeze"
    assert audit["formalInputReadCount"] == 0
    assert audit["blockers"] == [
        "preregistration_not_published",
        "remote_v18_tag_missing",
    ]


def test_remote_freeze_passes_only_when_v18_tag_points_to_published_head() -> None:
    audit = evaluate_v18_remote_freeze(_snapshot())

    assert audit["status"] == "passed"
    assert audit["route"] == "ready_for_single_formal_run"
    assert audit["blockers"] == []


def test_remote_freeze_requires_the_preregistered_implementation_commit() -> None:
    snapshot = _snapshot()
    snapshot["headContainsImplementationCommit"] = False
    snapshot["upstreamContainsImplementationCommit"] = False

    audit = evaluate_v18_remote_freeze(snapshot)

    assert audit["blockers"] == [
        "implementation_commit_not_in_frozen_head",
        "implementation_commit_not_published",
    ]
