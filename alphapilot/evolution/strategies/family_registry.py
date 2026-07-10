"""Stable strategy-family identity without automatic lifecycle promotion."""

from __future__ import annotations

import re
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import StrategyFamilyRecord


def normalize_family_key(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    if not normalized:
        raise ValueError("familyKey must contain letters or numbers")
    return normalized


def ensure_strategy_family(
    *,
    repository: RegistryRepository,
    family_key: str,
    name: str,
    metadata: dict[str, Any] | None = None,
) -> StrategyFamilyRecord:
    normalized = normalize_family_key(family_key)
    existing = repository.get_strategy_family_by_key(normalized)
    if existing:
        return existing
    family_metadata = {
        "schemaVersion": "strategy_family_v1",
        "researchOnly": True,
        "phase3MaximumLifecycle": "shadow",
        **(metadata or {}),
    }
    return repository.create_strategy_family(
        StrategyFamilyRecord(
            strategyFamilyId=stable_hash({"familyKey": normalized}, prefix="strategy_family"),
            familyKey=normalized,
            name=name,
            status="shadow_research",
            metadata=family_metadata,
            contentHash=stable_hash(family_metadata),
        )
    )
