"""Atomic checkpoint state for the long-running reference research workflow."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any


STAGES = (
    "source_verified",
    "inventory_written",
    "dedupe_complete",
    "data_audit_complete",
    "implementation_verified",
    "preregistered",
    "campaign_running",
    "campaign_complete",
    "closeout_complete",
)


class WorkflowStateStore:
    def __init__(self, path: str | Path, *, run_id: str) -> None:
        self.path = Path(path)
        if self.path.exists():
            self.state = json.loads(self.path.read_text(encoding="utf-8"))
            if self.state.get("runId") != run_id:
                raise RuntimeError("workflow run id mismatch")
        else:
            self.state: dict[str, Any] = {
                "schemaVersion": "reference_strategy_workflow_state_v1",
                "runId": run_id,
                "completedStages": [],
                "artifactHashes": {},
            }

    def next_stage(self) -> str | None:
        completed = set(self.state["completedStages"])
        return next((stage for stage in STAGES if stage not in completed), None)

    def complete(self, stage: str, *, artifact_hash: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown workflow stage: {stage}")
        if len(artifact_hash) != 64:
            raise ValueError("artifact_hash must be a SHA-256 hex digest")
        existing = self.state["artifactHashes"].get(stage)
        if existing is not None and existing != artifact_hash:
            raise RuntimeError(f"artifact hash drift for completed stage: {stage}")
        if existing is None:
            expected = self.next_stage()
            if stage != expected:
                raise RuntimeError(f"workflow stage order violation: expected {expected}, got {stage}")
            self.state["artifactHashes"][stage] = artifact_hash
            self.state["completedStages"].append(stage)
            self._write()

    def _write(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
