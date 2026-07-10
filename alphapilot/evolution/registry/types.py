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
class FactorRunRecord:
    factorRunId: str
    factorDefinitionId: str
    dataSnapshotId: str
    codeCommit: str | None
    configHash: str
    resultPath: str | None
    resultSha256: str | None
    status: str
    payload: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class ExperimentRecord:
    experimentId: str
    experimentType: str
    status: str
    dataSnapshotId: str | None
    splitDefinition: dict[str, Any]
    costModel: dict[str, Any]
    parameters: dict[str, Any]
    codeCommit: str | None
    payload: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class ModelRecord:
    modelId: str
    experimentId: str
    algorithm: str
    status: str
    artifactPath: str | None
    artifactSha256: str | None
    payload: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class OutcomeLedgerRecord:
    outcomeId: str
    evidenceClass: str
    sourceEntityType: str
    sourceEntityId: str
    dataSnapshotId: str
    strategyCandidateId: str | None
    instrumentId: str
    timeframe: str
    direction: str
    decisionAt: str
    entryAt: str
    exitAt: str
    status: str
    outcome: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class ForwardReleaseRecord:
    forwardReleaseId: str
    strategyCandidateId: str
    status: str
    riskEnvelope: dict[str, Any]
    release: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class ForwardSessionRecord:
    forwardSessionId: str
    forwardReleaseId: str
    accountId: str
    initialEquity: float
    session: dict[str, Any]
    contentHash: str
    startedAt: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class ForwardEventRecord:
    forwardEventId: str
    forwardSessionId: str
    forwardReleaseId: str
    eventType: str
    observedAt: str
    instrumentId: str | None
    payload: dict[str, Any]
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
class PromotionDecisionRecord:
    promotionDecisionId: str
    strategyCandidateId: str
    fromStatus: str | None
    toStatus: str
    passed: bool
    reasons: list[str]
    evidence: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class DemoReleaseRecord:
    demoReleaseId: str
    strategyCandidateId: str
    status: str
    riskEnvelope: dict[str, Any]
    release: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class DriftEventRecord:
    driftEventId: str
    demoReleaseId: str
    severity: str
    eventType: str
    payload: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class LiveCandidatePackageRecord:
    liveCandidatePackageId: str
    demoReleaseId: str
    status: str
    package: dict[str, Any]
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
