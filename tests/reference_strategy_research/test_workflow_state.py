from __future__ import annotations

from pathlib import Path

import pytest

from alphapilot.reference_strategy_research.workflow_state import WorkflowStateStore


def test_workflow_resumes_at_first_incomplete_stage(tmp_path: Path) -> None:
    path = tmp_path / "workflow_state.json"
    store = WorkflowStateStore(path, run_id="run-1")
    store.complete("source_verified", artifact_hash="a" * 64)
    store.complete("inventory_written", artifact_hash="b" * 64)

    resumed = WorkflowStateStore(path, run_id="run-1")

    assert resumed.next_stage() == "dedupe_complete"
    assert resumed.state["completedStages"] == ["source_verified", "inventory_written"]


def test_completed_stage_cannot_be_silently_rewritten(tmp_path: Path) -> None:
    path = tmp_path / "workflow_state.json"
    store = WorkflowStateStore(path, run_id="run-1")
    store.complete("source_verified", artifact_hash="a" * 64)

    with pytest.raises(RuntimeError, match="artifact hash drift"):
        store.complete("source_verified", artifact_hash="b" * 64)
