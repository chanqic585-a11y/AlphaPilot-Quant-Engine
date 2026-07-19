"""Composition-layer registry for built-in formal candidate adapters."""

from __future__ import annotations

from pathlib import Path

from alphapilot.formal_validation.candidate_adapter import CandidateAdapter
from alphapilot.research_factory.generated_candidate_adapter import (
    GeneratedDirectionalEventAdapter,
)
from alphapilot.standard_replication.candidate_adapter import (
    CanonicalReplicationCandidateAdapter,
)
from alphapilot.standard_replication.registry import ReplicationSourceRegistry
from alphapilot.standard_replication.tsmom_engine import SELECTED_TSMOM_TRIALS

from .s01 import S01CandidateAdapter


def get_candidate_adapter(candidate_id: str) -> CandidateAdapter:
    """Resolve a built-in adapter without leaking it into the formal core."""

    normalized = str(candidate_id or "").strip()
    if normalized == S01CandidateAdapter.CANDIDATE_ID:
        return S01CandidateAdapter()
    if normalized.startswith("auto-"):
        return GeneratedDirectionalEventAdapter(candidate_id=normalized)
    if normalized in SELECTED_TSMOM_TRIALS:
        repo_root = Path(__file__).resolve().parents[3]
        registry = ReplicationSourceRegistry.load(
            repo_root
            / "research"
            / "source_registry"
            / "strategy_research_source_registry.json"
        )
        family = registry.require("crypto_tsmom_turtle_v1")
        variant = next(
            row for row in family.variants if row.candidate_id == normalized
        )
        return CanonicalReplicationCandidateAdapter(
            family=family,
            variant=variant,
        )
    raise KeyError(f"candidate_adapter_not_registered:{normalized}")


__all__ = [
    "GeneratedDirectionalEventAdapter",
    "CanonicalReplicationCandidateAdapter",
    "get_candidate_adapter",
    "S01CandidateAdapter",
]
