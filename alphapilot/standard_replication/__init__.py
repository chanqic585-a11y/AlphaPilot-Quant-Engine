"""Canonical source-replication contracts for the V35 research track."""

from .candidate_adapter import CanonicalReplicationCandidateAdapter
from .plan_executor import ReplicationPlanExecutor
from .registry import (
    ReplicationFamily,
    ReplicationRegistryError,
    ReplicationSource,
    ReplicationSourceRegistry,
    ReplicationVariant,
)

__all__ = [
    "CanonicalReplicationCandidateAdapter",
    "ReplicationPlanExecutor",
    "ReplicationFamily",
    "ReplicationRegistryError",
    "ReplicationSource",
    "ReplicationSourceRegistry",
    "ReplicationVariant",
]
