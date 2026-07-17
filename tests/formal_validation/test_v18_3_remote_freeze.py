from __future__ import annotations

from alphapilot.formal_validation.v18_3_remote_freeze import (
    V18_1_TAG,
    V18_1_TAG_COMMIT,
    V18_2_TAG,
    V18_2_TAG_COMMIT,
    V18_TAG,
    V18_TAG_COMMIT,
    evaluate_v18_3_code_freeze,
    evaluate_v18_3_preregistration_freeze,
)


def test_v18_3_code_freeze_requires_clean_published_commit() -> None:
    passed = evaluate_v18_3_code_freeze(
        {
            "branch": "feature/v18-3",
            "localCommit": "a" * 40,
            "remoteCommit": "a" * 40,
            "upstreamContainsImplementationCommit": True,
            "worktreeClean": True,
        }
    )
    blocked = evaluate_v18_3_code_freeze(
        {
            "localCommit": "a" * 40,
            "remoteCommit": "b" * 40,
            "upstreamContainsImplementationCommit": False,
            "worktreeClean": False,
        }
    )

    assert passed["status"] == "passed"
    assert passed["route"] == "code_frozen_remotely"
    assert blocked["status"] == "blocked"
    assert "implementation_commit_not_published" in blocked["blockers"]
    assert "implementation_commit_remote_mismatch" in blocked["blockers"]
    assert "worktree_not_clean" in blocked["blockers"]


def test_v18_3_preregistration_freeze_preserves_predecessor_tags() -> None:
    snapshot = {
        "headCommit": "f" * 40,
        "upstreamCommit": "f" * 40,
        "implementationCommit": "a" * 40,
        "preregistrationHash": "prereg-hash",
        "upstreamContainsImplementationCommit": True,
        "preregistrationTracked": True,
        "preregistrationClean": True,
        "preregistrationOnUpstream": True,
        "localPreregistrationSha256": "b" * 64,
        "remotePreregistrationSha256": "b" * 64,
        "remoteTags": {
            V18_TAG: V18_TAG_COMMIT,
            V18_1_TAG: V18_1_TAG_COMMIT,
            V18_2_TAG: V18_2_TAG_COMMIT,
        },
        "v18_2TagIsAncestorOfHead": True,
    }
    passed = evaluate_v18_3_preregistration_freeze(snapshot)
    changed = {
        **snapshot,
        "remoteTags": {**snapshot["remoteTags"], V18_2_TAG: "0" * 40},
        "v18_2TagIsAncestorOfHead": False,
    }

    assert passed["status"] == "passed"
    assert passed["route"] == "ready_for_authorization"
    assert passed["predecessorV18_2TagUnchanged"] is True
    assert passed["formalResultRunCount"] == 0
    assert passed["lockedOosAccessCount"] == 0
    assert evaluate_v18_3_preregistration_freeze(changed)["status"] == "blocked"
