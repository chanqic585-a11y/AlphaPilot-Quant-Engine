from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from unittest.mock import patch

import pytest

from alphapilot.formal_validation.future_locked_oos import (
    FutureLockedOosError,
    audit_future_locked_oos_metadata,
    build_future_locked_oos_identity,
    guarded_future_locked_oos_read,
    write_future_locked_oos_metadata,
)


CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"
STRATEGY_HASH = "advisory_r_strategy_" + "1" * 64
PREREG_HASH = "s01_formal_walk_forward_preregistration_" + "2" * 64
CUTOFF = "2026-05-15T04:00:00Z"
FUTURE_START = "2026-05-15T08:00:00Z"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _identity() -> dict[str, object]:
    return build_future_locked_oos_identity(
        candidate_id=CANDIDATE_ID,
        strategy_definition_hash=STRATEGY_HASH,
        formal_preregistration_hash=PREREG_HASH,
        frozen_available_end_exclusive=CUTOFF,
        future_start_inclusive=FUTURE_START,
        timeframe="4h",
    )


def test_identity_is_metadata_only_bound_and_strictly_after_cutoff() -> None:
    identity = _identity()

    assert identity["route"] == "future_data_required"
    assert identity["candidateId"] == CANDIDATE_ID
    assert identity["strategyDefinitionHash"] == STRATEGY_HASH
    assert identity["formalPreregistrationHash"] == PREREG_HASH
    assert identity["frozenAvailableEndExclusive"] == CUTOFF
    assert identity["futureStartInclusive"] == FUTURE_START
    assert identity["metadataOnly"] is True
    assert identity["contentHash"] is None
    assert identity["dataFileCount"] == 0
    assert identity["marketDataPaths"] == []
    assert len(identity["identityHash"]) == 64


@pytest.mark.parametrize("future_start", [CUTOFF, "2026-05-15T00:00:00Z"])
def test_identity_rejects_boundary_that_is_not_strictly_after_cutoff(
    future_start: str,
) -> None:
    with pytest.raises(FutureLockedOosError, match="strictly after"):
        build_future_locked_oos_identity(
            candidate_id=CANDIDATE_ID,
            strategy_definition_hash=STRATEGY_HASH,
            formal_preregistration_hash=PREREG_HASH,
            frozen_available_end_exclusive=CUTOFF,
            future_start_inclusive=future_start,
            timeframe="4h",
        )


def test_metadata_writer_is_idempotent_and_keeps_zero_access_ledger(
    tmp_path: Path,
) -> None:
    identity = _identity()
    identity_path = tmp_path / "locked" / "identity.json"
    ledger_path = tmp_path / "locked" / "access_ledger.jsonl"
    market_root = tmp_path / "future_market_data"

    first = write_future_locked_oos_metadata(
        identity,
        identity_path=identity_path,
        ledger_path=ledger_path,
        future_market_data_root=market_root,
    )
    second = write_future_locked_oos_metadata(
        identity,
        identity_path=identity_path,
        ledger_path=ledger_path,
        future_market_data_root=market_root,
    )

    assert first == second
    assert market_root.exists() is False
    audit = audit_future_locked_oos_metadata(identity_path, ledger_path)
    assert audit["status"] == "passed"
    assert audit["identityHashValid"] is True
    assert audit["hashChainValid"] is True
    assert audit["ledgerEventCount"] == 1
    assert audit["lockedOosAccessCount"] == 0
    assert audit["contentReadCount"] == 0
    assert audit["admissionStatus"] == "blocked"
    assert set(audit["blockers"]) == {
        "future_market_data_not_available",
        "formal_walk_forward_not_completed",
    }

    stored = json.loads(identity_path.read_text("utf-8"))
    assert stored["contentHash"] is None


def test_guard_records_intent_before_rejecting_unavailable_future_content(
    tmp_path: Path,
) -> None:
    identity = _identity()
    identity_path = tmp_path / "identity.json"
    ledger_path = tmp_path / "ledger.jsonl"
    write_future_locked_oos_metadata(
        identity,
        identity_path=identity_path,
        ledger_path=ledger_path,
        future_market_data_root=tmp_path / "future_market_data",
    )

    with patch.object(Path, "read_bytes", side_effect=AssertionError("must not read")):
        with pytest.raises(FutureLockedOosError, match="future data is unavailable"):
            guarded_future_locked_oos_read(
                identity_path,
                ledger_path,
                tmp_path / "future_market_data" / "BTC-4h.feather",
                purpose="locked_oos_evaluation",
            )

    events = [
        json.loads(line)
        for line in ledger_path.read_text("utf-8").splitlines()
        if line
    ]
    assert events[-1]["eventType"] == "access_intent_denied"
    assert events[-1]["contentRead"] is False
    assert events[-1]["accessCountDelta"] == 1


def test_registration_cli_runs_from_script_path_without_pythonpath(
    tmp_path: Path,
) -> None:
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    completed = subprocess.run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts" / "register_future_locked_oos_identity.py"),
            "--repo-root",
            str(REPO_ROOT),
            "--metadata-root",
            str(tmp_path / "locked_oos"),
            "--evidence-root",
            str(tmp_path / "evidence"),
        ],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    payload = json.loads(completed.stdout)
    assert payload["status"] == "passed"
    assert payload["lockedOosAccessCount"] == 0
    assert (tmp_path / "locked_oos" / "s01_future_locked_oos_identity.json").exists()
