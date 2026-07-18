"""Dynamic artifact paths for candidate-neutral automatic research programs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_SAFE_COMPONENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


def _safe(value: str) -> str:
    text = str(value or "").strip()
    if not _SAFE_COMPONENT.fullmatch(text):
        raise ValueError(f"unsafe path component: {value!r}")
    return text


@dataclass(frozen=True)
class ProgramArtifactPaths:
    reports_root: Path
    program_id: str

    @property
    def program_root(self) -> Path:
        return Path(self.reports_root) / "automatic_research_program" / _safe(self.program_id)

    @property
    def state(self) -> Path:
        return self.program_root / "program_state.json"

    @property
    def ledger(self) -> Path:
        return self.program_root / "program_ledger.jsonl"

    @property
    def artifact_manifest(self) -> Path:
        return self.program_root / "artifact_manifest.json"

    def checkpoint(self, stage: str) -> Path:
        return self.program_root / "checkpoints" / f"{_safe(stage)}.json"

    def campaign(self, campaign_id: str) -> Path:
        return self.program_root / "campaigns" / _safe(campaign_id)

    def candidate(self, campaign_id: str, candidate_id: str) -> Path:
        return self.campaign(campaign_id) / "candidates" / _safe(candidate_id)
