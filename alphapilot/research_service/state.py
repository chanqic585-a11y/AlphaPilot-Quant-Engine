"""Atomic research-service state persistence without execution credentials."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .policy import ResearchServicePolicy


class ResearchServiceStateStore:
    def __init__(self, path: Path, *, policy: ResearchServicePolicy) -> None:
        self.path = Path(path)
        self.policy = policy

    def load_or_initialize(self, *, now: str) -> dict[str, Any]:
        if self.path.is_file():
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("policyHash") != self.policy.policy_hash:
                raise ValueError("research_policy_hash_mismatch")
            return payload
        payload = {
            "schemaVersion": "v35_research_service_state_v1",
            "policyHash": self.policy.policy_hash,
            "status": "idle",
            "updatedAt": now,
            "campaignsEnqueued": 0,
            "jobs": [],
        }
        self.save(payload)
        return payload

    def save(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, self.path)
