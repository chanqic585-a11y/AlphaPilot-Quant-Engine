from __future__ import annotations

from pathlib import Path

import pytest

from alphapilot.research_screening.holdout_unlock_store import HoldoutUnlockStore


def _hashes() -> dict[str, str]:
    return {
        "codeCommit": "commit-a",
        "dataSnapshotHash": "snapshot-a",
        "preregistrationHash": "prereg-a",
        "strategyDefinitionHash": "strategy-a",
        "exitModelHash": "exit-a",
        "benchmarkHash": "benchmark-a",
        "riskCapitalHash": "risk-a",
        "environmentManifestHash": "environment-a",
    }


def test_holdout_can_move_only_from_zero_to_one_access(tmp_path: Path) -> None:
    store = HoldoutUnlockStore(tmp_path / "unlock.json")
    initialized = store.initialize(campaign_id="campaign-a", holdout_hash="holdout-a")
    unlocked = store.unlock(reason="formal adjudication", frozen_hashes=_hashes())

    assert initialized["accessCount"] == 0
    assert unlocked["accessCount"] == 1
    with pytest.raises(RuntimeError, match="already unlocked"):
        store.unlock(reason="second look", frozen_hashes=_hashes())


def test_technical_replay_requires_byte_identical_hashes_and_pre_metric_incident(tmp_path: Path) -> None:
    store = HoldoutUnlockStore(tmp_path / "unlock.json")
    store.initialize(campaign_id="campaign-a", holdout_hash="holdout-a")
    store.unlock(reason="formal adjudication", frozen_hashes=_hashes())

    replay = store.record_technical_replay(
        frozen_hashes=_hashes(),
        incident_hash="incident-a",
        failure_before_metrics=True,
    )

    assert replay["technicalReplay"] is True
    assert replay["accessCount"] == 1
    with pytest.raises(RuntimeError, match="byte-identical"):
        store.record_technical_replay(
            frozen_hashes={**_hashes(), "codeCommit": "changed"},
            incident_hash="incident-b",
            failure_before_metrics=True,
        )

