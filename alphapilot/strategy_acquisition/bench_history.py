"""Bench-history helpers that keep factor evidence separate from Formal gates."""

from __future__ import annotations

from typing import Any

from .store import StrategyArtifactStore


def record_research_bench(
    store: StrategyArtifactStore, artifact_id: str, result: dict[str, Any]
) -> str:
    payload = dict(result)
    payload["strategyFormalPass"] = False
    payload["qualificationScope"] = "research_only"
    return store.record_bench(artifact_id, "research_bench", payload)
