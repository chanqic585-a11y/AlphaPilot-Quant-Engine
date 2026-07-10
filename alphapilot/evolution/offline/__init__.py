"""Offline-only evidence diagnosis and bounded research evolution."""

from .evidence_feedback import (
    EvidenceIngestionResult,
    build_failure_attribution,
    build_research_triggers,
    ingest_evidence_classed_outcomes,
)
from .loop import OfflineEvolutionConfig, run_offline_evolution_loop

__all__ = [
    "EvidenceIngestionResult",
    "OfflineEvolutionConfig",
    "build_failure_attribution",
    "build_research_triggers",
    "ingest_evidence_classed_outcomes",
    "run_offline_evolution_loop",
]
