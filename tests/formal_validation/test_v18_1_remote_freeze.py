from __future__ import annotations

from alphapilot.formal_validation.v18_1_remote_freeze import (
    evaluate_v18_1_code_freeze,
    evaluate_v18_1_preregistration_freeze,
)


V18_TAG_COMMIT = "aa2df4b5e8fc4e9c447edd3c5fef0a03de26ec01"


def test_v18_1_code_freeze_requires_the_implementation_on_upstream() -> None:
    passed = evaluate_v18_1_code_freeze(
        {
            "branch": "feature/v18-1",
            "localCommit": "c" * 40,
            "remoteCommit": "c" * 40,
            "upstreamContainsImplementationCommit": True,
            "worktreeClean": True,
        }
    )
    blocked = evaluate_v18_1_code_freeze(
        {
            "branch": "feature/v18-1",
            "localCommit": "c" * 40,
            "remoteCommit": "b" * 40,
            "upstreamContainsImplementationCommit": False,
            "worktreeClean": True,
        }
    )

    assert passed["status"] == "passed"
    assert passed["hashMatch"] is True
    assert blocked["status"] == "blocked"
    assert "implementation_commit_not_published" in blocked["blockers"]


def test_v18_1_preregistration_freeze_requires_exact_remote_bytes_and_tags() -> None:
    snapshot = {
        "headCommit": "d" * 40,
        "upstreamCommit": "d" * 40,
        "implementationCommit": "c" * 40,
        "upstreamContainsImplementationCommit": True,
        "preregistrationTracked": True,
        "preregistrationClean": True,
        "preregistrationOnUpstream": True,
        "localPreregistrationSha256": "e" * 64,
        "remotePreregistrationSha256": "e" * 64,
        "remoteTags": {
            "v13.27.1.18": V18_TAG_COMMIT,
            "v13.27.1.18.1": "d" * 40,
        },
    }

    passed = evaluate_v18_1_preregistration_freeze(snapshot)
    wrong_v18 = evaluate_v18_1_preregistration_freeze(
        {
            **snapshot,
            "remoteTags": {
                **snapshot["remoteTags"],
                "v13.27.1.18": "f" * 40,
            },
        }
    )

    assert passed["status"] == "passed"
    assert passed["hashMatch"] is True
    assert passed["predecessorV18TagUnchanged"] is True
    assert wrong_v18["status"] == "blocked"
    assert "predecessor_v18_tag_changed" in wrong_v18["blockers"]


def test_preregistration_bytes_can_be_frozen_before_the_new_tag_exists() -> None:
    snapshot = {
        "headCommit": "d" * 40,
        "upstreamCommit": "d" * 40,
        "implementationCommit": "c" * 40,
        "upstreamContainsImplementationCommit": True,
        "preregistrationTracked": True,
        "preregistrationClean": True,
        "preregistrationOnUpstream": True,
        "localPreregistrationSha256": "e" * 64,
        "remotePreregistrationSha256": "e" * 64,
        "remoteTags": {
            "v13.27.1.18": V18_TAG_COMMIT,
            "v13.27.1.18.1": None,
        },
    }

    pre_tag = evaluate_v18_1_preregistration_freeze(
        snapshot,
        require_v18_1_tag=False,
    )
    strict = evaluate_v18_1_preregistration_freeze(snapshot)

    assert pre_tag["status"] == "passed"
    assert pre_tag["v18_1TagRequired"] is False
    assert strict["status"] == "blocked"
    assert "remote_v18_1_tag_not_at_head" in strict["blockers"]


def test_strict_freeze_accepts_the_published_freeze_tag_as_head_ancestor() -> None:
    snapshot = {
        "headCommit": "e" * 40,
        "upstreamCommit": "e" * 40,
        "implementationCommit": "c" * 40,
        "upstreamContainsImplementationCommit": True,
        "preregistrationTracked": True,
        "preregistrationClean": True,
        "preregistrationOnUpstream": True,
        "localPreregistrationSha256": "f" * 64,
        "remotePreregistrationSha256": "f" * 64,
        "remoteTags": {
            "v13.27.1.18": V18_TAG_COMMIT,
            "v13.27.1.18.1": "d" * 40,
        },
        "v18_1TagIsAncestorOfHead": True,
    }

    audit = evaluate_v18_1_preregistration_freeze(snapshot)

    assert audit["status"] == "passed"
    assert audit["v18_1FreezeTagValid"] is True
