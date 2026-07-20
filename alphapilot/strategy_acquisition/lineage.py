"""Canonical lineage helpers for source-backed artifacts."""

from __future__ import annotations

from alphapilot.evolution.registry.hashing import stable_hash

from .models import StrategyArtifact


def artifact_content_hash(artifact: StrategyArtifact) -> str:
    payload = artifact.to_dict()
    payload.pop("updatedAt", None)
    return stable_hash(payload, prefix="artifact")


def lifecycle_event_hash(payload: dict[str, object]) -> str:
    return stable_hash(payload, prefix="artifact_event")
