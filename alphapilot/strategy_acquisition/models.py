"""Typed records for source-backed strategy and factor artifacts."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class SourceEvidence:
    sourceId: str
    sourcePath: str
    locator: str
    sourceHash: str
    extractionConfidence: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyArtifact:
    artifactId: str
    artifactType: str
    name: str
    familyId: str
    authorityRef: str
    sourceIds: tuple[str, ...]
    sourceHashes: tuple[str, ...]
    licenseClass: str
    sourceEquivalenceClass: str
    marketMechanism: str
    formula: str | None
    requiredFields: tuple[str, ...]
    universe: tuple[str, ...]
    timeframe: str
    entryRules: tuple[str, ...]
    exitRules: tuple[str, ...]
    positionSizing: str
    riskManagement: str
    dataProfile: dict[str, Any]
    evidence: tuple[SourceEvidence, ...]
    candidateId: str | None = None
    candidateHash: str | None = None
    status: str = "source_ingested"
    createdAt: str = field(default_factory=utc_now)
    updatedAt: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["sourceIds"] = list(self.sourceIds)
        result["sourceHashes"] = list(self.sourceHashes)
        result["requiredFields"] = list(self.requiredFields)
        result["universe"] = list(self.universe)
        result["entryRules"] = list(self.entryRules)
        result["exitRules"] = list(self.exitRules)
        result["evidence"] = [item.to_dict() for item in self.evidence]
        return result

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "StrategyArtifact":
        payload = dict(value)
        for name in (
            "sourceIds",
            "sourceHashes",
            "requiredFields",
            "universe",
            "entryRules",
            "exitRules",
        ):
            payload[name] = tuple(payload.get(name) or ())
        payload["evidence"] = tuple(
            SourceEvidence(**item) for item in payload.get("evidence") or ()
        )
        return cls(**payload)
