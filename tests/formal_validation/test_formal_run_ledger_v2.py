from __future__ import annotations

from pathlib import Path

import pytest

from alphapilot.formal_validation.formal_run_ledger import (
    FormalRunClaimError,
    claim_formal_run,
    complete_formal_run,
    fail_formal_run,
)


IDENTITY = {
    "codeCommit": "commit-a",
    "preregistrationHash": "prereg-a",
    "inputSnapshotHash": "snapshot-a",
}


def test_run_ledger_is_an_atomic_single_claim(tmp_path: Path) -> None:
    path = tmp_path / "formal_run_ledger.json"

    first = claim_formal_run(path, run_id="formal-001", identity=IDENTITY)

    assert first["state"] == "running"
    assert first["attemptCount"] == 1
    assert first["resumed"] is False
    with pytest.raises(FormalRunClaimError, match="deterministic checkpoint"):
        claim_formal_run(path, run_id="formal-001", identity=IDENTITY)


def test_matching_running_claim_can_resume_but_completed_run_is_terminal(
    tmp_path: Path,
) -> None:
    path = tmp_path / "formal_run_ledger.json"
    checkpoint = {"checkpointId": "loaded-input", "deterministic": True}
    claim_formal_run(
        path,
        run_id="formal-001",
        identity=IDENTITY,
        checkpoint=checkpoint,
    )

    resumed = claim_formal_run(
        path,
        run_id="formal-001",
        identity=IDENTITY,
        resume_checkpoint=checkpoint,
    )
    assert resumed["attemptCount"] == 1
    assert resumed["resumed"] is True

    complete_formal_run(
        path,
        run_id="formal-001",
        identity=IDENTITY,
        result_manifest_hash="result-a",
    )
    with pytest.raises(FormalRunClaimError, match="terminal"):
        claim_formal_run(
            path,
            run_id="formal-001",
            identity=IDENTITY,
            resume_checkpoint=checkpoint,
        )


def test_failed_run_is_terminal_and_records_a_bounded_reason(tmp_path: Path) -> None:
    path = tmp_path / "formal_run_ledger.json"
    checkpoint = {"checkpointId": "before-input", "deterministic": True}
    claim_formal_run(
        path,
        run_id="formal-001",
        identity=IDENTITY,
        checkpoint=checkpoint,
    )

    failed = fail_formal_run(
        path,
        run_id="formal-001",
        identity=IDENTITY,
        reason="executor_failed",
    )

    assert failed["state"] == "failed"
    assert failed["failureReason"] == "executor_failed"
    with pytest.raises(FormalRunClaimError, match="terminal"):
        claim_formal_run(
            path,
            run_id="formal-001",
            identity=IDENTITY,
            resume_checkpoint=checkpoint,
        )
