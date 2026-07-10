"""Typed records for the auditable strategy workflow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alphapilot.evolution.registry.types import utc_now


@dataclass(frozen=True)
class StrategyVersionRecord:
    strategyVersionId: str
    strategyFamilyId: str
    parentStrategyVersionId: str | None
    strategyCandidateId: str | None
    displayName: str
    sourceType: str
    status: str
    definition: dict[str, Any]
    parameters: dict[str, Any]
    modelArtifactId: str | None
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class GateProfileRecord:
    gateProfileId: str
    profileKey: str
    version: int
    stage: str
    status: str
    rules: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class StrategyDataContractRecord:
    strategyDataContractId: str
    strategyVersionId: str
    schemaVersion: str
    contract: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class EvaluationBindingRecord:
    evaluationBindingId: str
    workflowRunId: str
    strategyDataContractId: str
    dataSnapshotId: str
    walkForwardManifestHash: str
    holdoutManifestHash: str
    lockedOosManifestHash: str
    gateProfileId: str
    runnerVersion: str
    costModel: dict[str, Any]
    evidence: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class WorkflowRunRecord:
    workflowRunId: str
    strategyVersionId: str
    stage: str
    status: str
    attemptNumber: int
    gateProfileId: str | None
    riskProfileId: str | None
    idempotencyKey: str
    progress: dict[str, Any]
    result: dict[str, Any]
    startedAt: str | None
    checkpointAt: str | None
    completedAt: str | None
    contentHash: str
    createdAt: str = field(default_factory=utc_now)
    updatedAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class StageEventRecord:
    stageEventId: str
    workflowRunId: str
    strategyVersionId: str
    previousStage: str | None
    nextStage: str
    previousStatus: str | None
    nextStatus: str
    reasonCode: str
    actor: str
    evidence: dict[str, Any]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)


@dataclass(frozen=True)
class FailureDiagnosisRecord:
    failureDiagnosisId: str
    workflowRunId: str
    category: str
    summary: str
    retryDisposition: str
    metrics: dict[str, Any]
    suggestions: list[str]
    contentHash: str
    createdAt: str = field(default_factory=utc_now)
