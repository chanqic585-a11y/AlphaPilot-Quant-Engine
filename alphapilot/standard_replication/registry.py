"""Validated source registry for bounded canonical strategy replications."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class ReplicationRegistryError(ValueError):
    """Raised when source metadata or a replication budget is invalid."""


def _required_text(value: object) -> str:
    return str(value or "").strip()


@dataclass(frozen=True)
class ReplicationSource:
    url: str
    license: str
    summary: str
    citation: str


@dataclass(frozen=True)
class ReplicationVariant:
    candidate_id: str
    adaptation: str
    definition_path: str


@dataclass(frozen=True)
class ReplicationFamily:
    family_id: str
    title: str
    source: ReplicationSource
    mechanism: str
    formula: str
    parameters: Mapping[str, Any]
    universe: Mapping[str, Any]
    cost_assumptions: Mapping[str, Any]
    adaptation_limits: tuple[str, ...]
    replication_state: str
    variants: tuple[ReplicationVariant, ...]


@dataclass(frozen=True)
class ReplicationSourceRegistry:
    schema_version: str
    registry_id: str
    items: tuple[ReplicationFamily, ...]

    @property
    def family_ids(self) -> tuple[str, ...]:
        return tuple(sorted(item.family_id for item in self.items))

    def require(self, family_id: str) -> ReplicationFamily:
        for item in self.items:
            if item.family_id == family_id:
                return item
        raise ReplicationRegistryError(f"unknown_family:{family_id}")

    @classmethod
    def load(cls, path: Path) -> "ReplicationSourceRegistry":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        schema_version = _required_text(payload.get("schemaVersion"))
        registry_id = _required_text(payload.get("registryId"))
        if schema_version != "v35_strategy_research_source_registry_v1":
            raise ReplicationRegistryError("unsupported_registry_schema")
        if not registry_id:
            raise ReplicationRegistryError("registry_id_missing")

        families: list[ReplicationFamily] = []
        seen_family_ids: set[str] = set()
        seen_candidate_ids: set[str] = set()
        for raw_family in payload.get("families") or []:
            family_id = _required_text(raw_family.get("familyId"))
            if not family_id:
                raise ReplicationRegistryError("family_id_missing")
            if family_id in seen_family_ids:
                raise ReplicationRegistryError(f"duplicate_family:{family_id}")
            seen_family_ids.add(family_id)

            raw_source = raw_family.get("source") or {}
            source = ReplicationSource(
                url=_required_text(raw_source.get("url")),
                license=_required_text(raw_source.get("license")),
                summary=_required_text(raw_source.get("summary")),
                citation=_required_text(raw_source.get("citation")),
            )
            if not all(
                (source.url, source.license, source.summary, source.citation)
            ):
                raise ReplicationRegistryError(
                    f"source_metadata_incomplete:{family_id}"
                )

            raw_variants = raw_family.get("variants") or []
            if not 1 <= len(raw_variants) <= 2:
                if len(raw_variants) > 2:
                    raise ReplicationRegistryError(
                        f"variant_budget_exceeded:{family_id}"
                    )
                raise ReplicationRegistryError(f"variant_missing:{family_id}")
            variants: list[ReplicationVariant] = []
            for raw_variant in raw_variants:
                candidate_id = _required_text(raw_variant.get("candidateId"))
                adaptation = _required_text(raw_variant.get("adaptation"))
                definition_path = _required_text(raw_variant.get("definitionPath"))
                if not candidate_id or not adaptation:
                    raise ReplicationRegistryError(
                        f"variant_metadata_incomplete:{family_id}"
                    )
                if candidate_id in seen_candidate_ids:
                    raise ReplicationRegistryError(
                        f"duplicate_candidate:{candidate_id}"
                    )
                seen_candidate_ids.add(candidate_id)
                variants.append(
                    ReplicationVariant(
                        candidate_id=candidate_id,
                        adaptation=adaptation,
                        definition_path=definition_path,
                    )
                )

            families.append(
                ReplicationFamily(
                    family_id=family_id,
                    title=_required_text(raw_family.get("title")),
                    source=source,
                    mechanism=_required_text(raw_family.get("mechanism")),
                    formula=_required_text(raw_family.get("formula")),
                    parameters=dict(raw_family.get("parameters") or {}),
                    universe=dict(raw_family.get("universe") or {}),
                    cost_assumptions=dict(raw_family.get("costAssumptions") or {}),
                    adaptation_limits=tuple(
                        str(value) for value in raw_family.get("adaptationLimits") or []
                    ),
                    replication_state=_required_text(
                        raw_family.get("replicationState")
                    ),
                    variants=tuple(variants),
                )
            )

        if not families:
            raise ReplicationRegistryError("registry_empty")
        return cls(
            schema_version=schema_version,
            registry_id=registry_id,
            items=tuple(families),
        )
