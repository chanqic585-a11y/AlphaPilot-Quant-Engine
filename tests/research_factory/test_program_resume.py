from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.program_ledger import ProgramLedger
from alphapilot.research_factory.program_state import ProgramStateStore
from alphapilot.research_factory.program_types import ProgramState
from alphapilot.research_factory.resume import build_resume_report


def _state() -> ProgramState:
    return ProgramState.create(
        program_id="automatic_strategy_demo_test",
        baseline_commit="f9f36f4",
        program_spec_hash="program_spec_abc",
        created_at="2026-07-18T00:00:00Z",
    )


def test_ledger_is_append_only_hash_chained_and_idempotent(tmp_path: Path) -> None:
    ledger = ProgramLedger(tmp_path / "program_ledger.jsonl")

    first = ledger.append(
        event_type="program_created",
        stage="program_created",
        created_at="2026-07-18T00:00:00Z",
        payload={"programId": "automatic_strategy_demo_test"},
    )
    duplicate = ledger.append(
        event_type="program_created",
        stage="program_created",
        created_at="2026-07-18T00:00:00Z",
        payload={"programId": "automatic_strategy_demo_test"},
    )
    second = ledger.append(
        event_type="baseline_frozen",
        stage="baseline_frozen",
        created_at="2026-07-18T00:01:00Z",
        payload={"baselineCommit": "f9f36f4"},
    )

    assert duplicate == first
    assert second["sequence"] == 2
    assert second["previousRecordHash"] == first["recordHash"]
    assert len(ledger.read_all()) == 2


def test_ledger_detects_tampering(tmp_path: Path) -> None:
    path = tmp_path / "program_ledger.jsonl"
    ledger = ProgramLedger(path)
    ledger.append(
        event_type="program_created",
        stage="program_created",
        created_at="2026-07-18T00:00:00Z",
        payload={"programId": "automatic_strategy_demo_test"},
    )
    record = json.loads(path.read_text(encoding="utf-8"))
    record["payload"]["programId"] = "tampered"
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(ValueError, match="ledger record hash mismatch"):
        ledger.read_all()


def test_state_store_resumes_without_overwriting_another_program(tmp_path: Path) -> None:
    paths = ProgramArtifactPaths(tmp_path, "automatic_strategy_demo_test")
    store = ProgramStateStore(paths)
    state = _state()

    store.initialize(state)
    assert store.initialize(state) == state
    resumed = store.save(
        state.transition(
            stage="baseline_frozen",
            updated_at="2026-07-18T00:01:00Z",
            previous_checkpoint="program_created",
            next_allowed_stage="data_capability_ready",
        )
    )
    assert store.load() == resumed

    other = ProgramState.create(
        program_id="automatic_strategy_demo_other",
        baseline_commit="f9f36f4",
        program_spec_hash="program_spec_other",
        created_at="2026-07-18T00:00:00Z",
    )
    with pytest.raises(ValueError, match="program identity mismatch"):
        store.initialize(other)


def test_checkpoint_payload_is_hash_verified(tmp_path: Path) -> None:
    paths = ProgramArtifactPaths(tmp_path, "automatic_strategy_demo_test")
    store = ProgramStateStore(paths)
    checkpoint = store.write_checkpoint(
        stage="v19",
        created_at="2026-07-18T00:02:00Z",
        payload={"status": "completed", "artifactCount": 4},
    )

    assert store.load_checkpoint("v19") == checkpoint
    raw = json.loads(paths.checkpoint("v19").read_text(encoding="utf-8"))
    raw["payload"]["artifactCount"] = 99
    paths.checkpoint("v19").write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="checkpoint hash mismatch"):
        store.load_checkpoint("v19")


def test_resume_report_exposes_required_counters(tmp_path: Path) -> None:
    paths = ProgramArtifactPaths(tmp_path, "automatic_strategy_demo_test")
    store = ProgramStateStore(paths)
    state = _state().transition(
        stage="formal_campaign_frozen",
        updated_at="2026-07-18T00:03:00Z",
        previous_checkpoint="prefilter_completed",
        next_allowed_stage="formal_validation_completed",
        one_shot_claims_consumed=2,
        result_read_count=1,
    )
    store.initialize(state)

    assert build_resume_report(store) == {
        "programId": "automatic_strategy_demo_test",
        "previousCheckpoint": "prefilter_completed",
        "nextAllowedStage": "formal_validation_completed",
        "oneShotClaimsConsumed": 2,
        "resultReadCount": 1,
        "stage": "formal_campaign_frozen",
        "terminalRoute": None,
    }
