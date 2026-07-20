from alphapilot.formal_validation.v36_remote_freeze import (
    evaluate_v36_remote_freeze,
)


def _snapshot() -> dict[str, object]:
    return {
        "headCommit": "b" * 40,
        "implementationCommit": "a" * 40,
        "upstreamRef": "origin/feature/v36",
        "upstreamContainsHead": True,
        "upstreamContainsImplementationCommit": True,
        "headContainsImplementationCommit": True,
        "worktreeClean": True,
        "preregistrationTracked": True,
        "preregistrationClean": True,
        "preregistrationOnUpstream": True,
        "preregistrationBytesMatch": True,
        "snapshotTracked": True,
        "snapshotClean": True,
        "snapshotOnUpstream": True,
        "snapshotBytesMatch": True,
        "remoteFreezeTag": "v13.27.1.36-formal-handoff",
        "remoteTagCommit": "b" * 40,
    }


def test_v36_remote_freeze_requires_clean_exact_remote_preregistration_and_snapshot() -> None:
    passed = evaluate_v36_remote_freeze(_snapshot())
    assert passed["status"] == "passed"
    assert passed["formalInputReadCount"] == 0

    for field, blocker in (
        ("worktreeClean", "worktree_not_clean"),
        ("preregistrationBytesMatch", "preregistration_remote_bytes_mismatch"),
        ("snapshotBytesMatch", "snapshot_remote_bytes_mismatch"),
        ("upstreamContainsImplementationCommit", "implementation_commit_not_published"),
    ):
        value = _snapshot()
        value[field] = False
        audit = evaluate_v36_remote_freeze(value)
        assert audit["status"] == "blocked"
        assert blocker in audit["blockers"]


def test_v36_remote_freeze_requires_remote_tag_at_frozen_head() -> None:
    missing = _snapshot()
    missing["remoteTagCommit"] = None
    assert "remote_freeze_tag_missing" in evaluate_v36_remote_freeze(missing)["blockers"]

    wrong = _snapshot()
    wrong["remoteTagCommit"] = "c" * 40
    assert "remote_freeze_tag_not_at_head" in evaluate_v36_remote_freeze(wrong)["blockers"]
