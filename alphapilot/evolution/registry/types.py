"""Typed immutable records used by the evolution registry."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class DataSnapshotRecord:
    dataSnapshotId: str
    source: str
    exchange: str | None
    marketType: str | None
    timeframe: str | None
    startTime: str | None
    endTime: str | None
    pointInTimeCutoff: str | None
    manifest: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class FactorDefinitionRecord:
    factorDefinitionId: str
    name: str
    version: str
    expression: str
    definition: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class StrategyFamilyRecord:
    strategyFamilyId: str
    familyKey: str
    name: str
    status: str
    metadata: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class StrategyCandidateRecord:
    strategyCandidateId: str
    strategyFamilyId: str
    name: str
    status: str
    candidate: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class LegacyEvidenceRecord:
    legacyEvidenceId: str
    sourcePath: str
    sourceSha256: str
    evidenceType: str
    strategyFamilyId: str | None
    familyFingerprint: str | None
    ruleFingerprint: str | None
    classificationReasons: list[str]
    payload: Any
    contentHash: str
    importedAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class AuditEventRecord:
    auditEventId: str
    eventType: str
    entityType: str
    entityId: str | None
    payload: dict[str, Any]
    createdAt: str = field(default_factory=utc_now)
