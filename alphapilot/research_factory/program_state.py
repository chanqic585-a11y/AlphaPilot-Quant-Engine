"""Identity-locked state and checkpoints for a resumable research program."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.program_types import ProgramState, program_state_from_dict


class ProgramStateStore:
    def __init__(self, paths: ProgramArtifactPaths) -> None:
        self.paths = paths

    def initialize(self, state: ProgramState) -> ProgramState:
        if self.paths.state.is_file():
            current = self.load()
            if (
                current.program_id != state.program_id
                or current.baseline_commit != state.baseline_commit
                or current.program_spec_hash != state.program_spec_hash
            ):
                raise ValueError("program identity mismatch")
            return current
        return self.save(state)

    def load(self) -> ProgramState:
        if not self.paths.state.is_file():
            raise FileNotFoundError(self.paths.state)
        payload = json.loads(self.paths.state.read_text(encoding="utf-8"))
        return program_state_from_dict(payload)

    def save(self, state: ProgramState) -> ProgramState:
        if self.paths.state.is_file():
            current = self.load()
            if (
                current.program_id != state.program_id
                or current.baseline_commit != state.baseline_commit
                or current.program_spec_hash != state.program_spec_hash
            ):
                raise ValueError("program identity mismatch")
        write_json_atomic(self.paths.state, state.to_dict())
        return state

    def write_checkpoint(
        self,
        *,
        stage: str,
        created_at: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        checkpoint = {
            "schemaVersion": "automatic_strategy_demo_checkpoint_v1",
            "stage": stage,
            "createdAt": created_at,
            "payload": payload,
        }
        checkpoint["checkpointHash"] = stable_hash(checkpoint)
        write_json_atomic(self.paths.checkpoint(stage), checkpoint)
        return checkpoint

    def load_checkpoint(self, stage: str) -> dict[str, Any]:
        path = self.paths.checkpoint(stage)
        if not path.is_file():
            raise FileNotFoundError(path)
        checkpoint = json.loads(path.read_text(encoding="utf-8"))
        supplied_hash = checkpoint.get("checkpointHash")
        canonical = {key: value for key, value in checkpoint.items() if key != "checkpointHash"}
        if supplied_hash != stable_hash(canonical):
            raise ValueError("checkpoint hash mismatch")
        return checkpoint
