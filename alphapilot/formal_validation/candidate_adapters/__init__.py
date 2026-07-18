"""Composition-layer registry for built-in formal candidate adapters."""

from __future__ import annotations

from alphapilot.formal_validation.candidate_adapter import CandidateAdapter
from alphapilot.research_factory.generated_candidate_adapter import (
    GeneratedDirectionalEventAdapter,
)

from .s01 import S01CandidateAdapter


def get_candidate_adapter(candidate_id: str) -> CandidateAdapter:
    """Resolve a built-in adapter without leaking it into the formal core."""

    normalized = str(candidate_id or "").strip()
    if normalized == S01CandidateAdapter.CANDIDATE_ID:
        return S01CandidateAdapter()
    if normalized.startswith("auto-"):
        return GeneratedDirectionalEventAdapter(candidate_id=normalized)
    raise KeyError(f"candidate_adapter_not_registered:{normalized}")


__all__ = [
    "GeneratedDirectionalEventAdapter",
    "get_candidate_adapter",
    "S01CandidateAdapter",
]
