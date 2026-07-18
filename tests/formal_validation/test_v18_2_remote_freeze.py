from __future__ import annotations

from alphapilot.formal_validation.v18_2_contracts import V18_2_TAG
from alphapilot.formal_validation.v18_2_remote_freeze import (
    evaluate_v18_2_code_freeze,
    evaluate_v18_2_preregistration_freeze,
)


IMPLEMENTATION = "a" * 40
PREREGISTRATION = "b" * 40
V18_TAG_COMMIT = "aa2df4b5e8fc4e9c447edd3c5fef0a03de26ec01"
V18_1_TAG_COMMIT = "b60d0e191431a353e79f9c954c31d4de0be25c92"


def test_v18_2_code_freeze_requires_clean_published_commit() -> None:
    passed = evaluate_v18_2_code_freeze(
        {
            "branch": "feature/v18-2",
            "localCommit": IMPLEMENTATION,
            "remoteCommit": IMPLEMENTATION,
            "upstreamContainsImplementationCommit": True,
            "worktreeClean": True,
        }
    )
    blocked = evaluate_v18_2_code_freeze(
        {
            "localCommit": IMPLEMENTATION,
            "remoteCommit": "c" * 40,
            "upstreamContainsImplementationCommit": False,
            "worktreeClean": False,
        }
    )

    assert passed["status"] == "passed"
    assert passed["route"] == "code_frozen_remotely"
    assert blocked["status"] == "blocked"
    assert "implementation_commit_not_published" in blocked["blockers"]
    assert "worktree_not_clean" in blocked["blockers"]


def test_v18_2_preregistration_freeze_binds_remote_bytes_and_tags() -> None:
    assert V18_2_TAG == "v13.27.1.18.2-r2"
    snapshot = {
        "headCommit": PREREGISTRATION,
        "upstreamCommit": PREREGISTRATION,
        "implementationCommit": IMPLEMENTATION,
        "upstreamContainsImplementationCommit": True,
        "preregistrationTracked": True,
        "preregistrationClean": True,
        "preregistrationOnUpstream": True,
        "localPreregistrationSha256": "hash-a",
        "remotePreregistrationSha256": "hash-a",
        "preregistrationHash": "logical-hash",
        "remoteTags": {
            "v13.27.1.18": V18_TAG_COMMIT,
            "v13.27.1.18.1": V18_1_TAG_COMMIT,
            V18_2_TAG: PREREGISTRATION,
        },
    }
    passed = evaluate_v18_2_preregistration_freeze(snapshot)
    blocked = evaluate_v18_2_preregistration_freeze(
        {
            **snapshot,
            "remotePreregistrationSha256": "hash-b",
            "remoteTags": {**snapshot["remoteTags"], V18_2_TAG: None},
        }
    )

    assert passed["status"] == "passed"
    assert passed["preregistrationHash"] == "logical-hash"
    assert passed["headCommit"] == PREREGISTRATION
    assert passed["predecessorV18TagUnchanged"] is True
    assert passed["predecessorV18_1TagUnchanged"] is True
    assert passed["v18_2FreezeTagValid"] is True
    assert blocked["status"] == "blocked"
    assert "preregistration_remote_hash_mismatch" in blocked["blockers"]
    assert "remote_v18_2_tag_not_at_head" in blocked["blockers"]
