"""Immutable bounded-campaign contracts for Phase 3C research."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.exit_policy import (
    ExitPolicy,
    canonical_exit_policy,
    exit_policy_hash,
    validate_exit_policy,
)


LEGACY_CANDIDATE_SCHEMA = "phase3c_candidate_v1"
ADVISORY_CANDIDATE_SCHEMA = "phase3c_candidate_v2"


@dataclass(frozen=True)
class ExperimentBudget:
    maximumFamilies: int = 8
    maximumInitialVariantsPerFamily: int = 2
    maximumInitialCandidates: int = 16
    maximumStructuralRevisionsPerFamily: int = 1
    maximumFullBacktests: int = 48

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True)
class CandidateSpec:
    candidateId: str
    familyId: str
    marketMechanismId: str
    direction: str
    timeframe: str
    causalRationale: str
    eventDefinition: Mapping[str, Any]
    invalidation: str
    stopAtr: float
    targetR: float | None
    maximumHoldBars: int
    requiredData: tuple[str, ...]
    expectedFailureRegimes: tuple[str, ...]
    factorConfirmations: tuple[str, ...] = field(default_factory=tuple)
    factorRanking: tuple[str, ...] = field(default_factory=tuple)
    factorVetoes: tuple[str, ...] = field(default_factory=tuple)
    schemaVersion: str = LEGACY_CANDIDATE_SCHEMA
    exitPolicy: ExitPolicy | None = None

    def __post_init__(self) -> None:
        if self.direction not in {"long", "short"}:
            raise ValueError("direction must be long or short")
        if self.timeframe == "5m":
            raise ValueError("5m is disabled for the first formal campaign")
        if self.timeframe not in {"15m", "1h", "4h", "1d"}:
            raise ValueError("unsupported timeframe")
        if self.stopAtr <= 0 or self.maximumHoldBars <= 0:
            raise ValueError("stopAtr and maximumHoldBars must be positive")
        if self.schemaVersion == LEGACY_CANDIDATE_SCHEMA:
            if self.exitPolicy is not None:
                raise ValueError("legacy candidates may not serialize exitPolicy")
            if self.targetR is None or self.targetR < 2:
                raise ValueError("targetR must be at least 2R")
        elif self.schemaVersion == ADVISORY_CANDIDATE_SCHEMA:
            if self.exitPolicy is None:
                raise ValueError("schema-v2 candidates require exitPolicy")
            validate_exit_policy(self.exitPolicy)
            if self.exitPolicy.maximumHoldBars != self.maximumHoldBars:
                raise ValueError("exitPolicy maximumHoldBars must match candidate maximumHoldBars")
            if self.targetR is not None and self.targetR <= 0:
                raise ValueError("advisory targetR must be positive when provided")
        else:
            raise ValueError(f"unsupported candidate schema: {self.schemaVersion}")

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "candidateId": self.candidateId,
            "familyId": self.familyId,
            "marketMechanismId": self.marketMechanismId,
            "direction": self.direction,
            "timeframe": self.timeframe,
            "causalRationale": self.causalRationale,
            "eventDefinition": dict(self.eventDefinition),
            "invalidation": self.invalidation,
            "stopAtr": self.stopAtr,
            "targetR": self.targetR,
            "maximumHoldBars": self.maximumHoldBars,
            "requiredData": self.requiredData,
            "expectedFailureRegimes": self.expectedFailureRegimes,
            "factorConfirmations": self.factorConfirmations,
            "factorRanking": self.factorRanking,
            "factorVetoes": self.factorVetoes,
        }
        if self.schemaVersion == ADVISORY_CANDIDATE_SCHEMA:
            assert self.exitPolicy is not None
            payload.update(
                {
                    "schemaVersion": self.schemaVersion,
                    "riskMetric": "R",
                    "targetRGateMode": "advisory",
                    "minimumTargetR": None,
                    "initialStopMayWiden": False,
                    "exitPolicyRequired": True,
                    "exitPolicyVersion": self.exitPolicy.version,
                    "exitPolicy": canonical_exit_policy(self.exitPolicy),
                    "exitPolicyHash": exit_policy_hash(self.exitPolicy),
                }
            )
        payload["definitionHash"] = stable_hash(payload, prefix="candidate_definition")
        return payload


def _validate_budget(candidates: Sequence[CandidateSpec], budget: ExperimentBudget) -> None:
    if len(candidates) > budget.maximumInitialCandidates:
        raise ValueError("maximumInitialCandidates exceeded")
    families: dict[str, int] = {}
    for candidate in candidates:
        families[candidate.familyId] = families.get(candidate.familyId, 0) + 1
    if len(families) > budget.maximumFamilies:
        raise ValueError("maximumFamilies exceeded")
    if any(count > budget.maximumInitialVariantsPerFamily for count in families.values()):
        raise ValueError("maximumInitialVariantsPerFamily exceeded")


def build_campaign_preregistration(
    *,
    external_reference_manifest_hash: str,
    data_snapshot_hash: str,
    factor_shortlist_hash: str,
    candidates: Sequence[CandidateSpec],
    time_boundaries: Mapping[str, Mapping[str, Any]],
    code_commit: str,
    budget: ExperimentBudget | None = None,
    universe_policy: Mapping[str, Any] | None = None,
    factor_registry_hash: str | None = None,
    implementation_source_hashes: Mapping[str, str] | None = None,
) -> dict[str, Any]:
    active_budget = budget or ExperimentBudget()
    _validate_budget(candidates, active_budget)
    candidate_schemas = {candidate.schemaVersion for candidate in candidates}
    if len(candidate_schemas) != 1:
        raise ValueError("campaigns may not mix legacy and Advisory-R candidate schemas")
    candidate_schema = next(iter(candidate_schemas), LEGACY_CANDIDATE_SCHEMA)
    advisory = candidate_schema == ADVISORY_CANDIDATE_SCHEMA
    candidate_rows = [candidate.to_dict() for candidate in candidates]
    holdout_core = {
        "dataSnapshotHash": data_snapshot_hash,
        "timeBoundaries": dict(time_boundaries),
        "ratio": 0.2,
        "selectionAccessPolicy": "locked_until_final_evaluation",
    }
    holdout_hash = stable_hash(holdout_core, prefix="holdout")
    core = {
        "schemaVersion": (
            "phase3c_campaign_preregistration_v2"
            if advisory
            else "phase3c_campaign_preregistration_v1"
        ),
        "codeCommit": code_commit,
        "externalReferenceManifestHash": external_reference_manifest_hash,
        "dataSnapshotHash": data_snapshot_hash,
        "factorShortlistHash": factor_shortlist_hash,
        "factorRegistryHash": factor_registry_hash,
        "implementationSourceHashes": dict(implementation_source_hashes or {}),
        "candidates": candidate_rows,
        "experimentBudget": active_budget.to_dict(),
        "universePolicy": dict(universe_policy or {}),
        "splitPolicy": {
            "ratios": {"development": 0.55, "walkForward": 0.25, "holdout": 0.2},
            "walkForwardFolds": 5,
            "purged": True,
            "embargoPolicy": "candidate_maximum_hold_bars",
            "timeBoundaries": dict(time_boundaries),
        },
        "holdout": {
            **holdout_core,
            "hash": holdout_hash,
            "accessCountBeforeFinalEvaluation": 0,
        },
        "sampleGates": {
            "15m": {"minimumEvents": 300, "minimumMonths": 12},
            "1h": {"minimumEvents": 150, "minimumMonths": 12},
            "4h": {"minimumEvents": 80, "minimumMonths": 18},
            "1d": {"minimumEvents": 40, "minimumMonths": 24},
        },
        "prescreenGates": {
            "developmentProfitFactor": {"operator": ">=", "required": 1.08},
            "developmentAverageNetR": {"operator": ">=", "required": 0.03},
            "positiveDevelopmentMonthRatio": {"operator": ">=", "required": 0.6},
        },
        "baseGates": {
            "oosProfitFactor": {"operator": ">=", "required": 1.05},
            "oosAverageNetR": {"operator": ">", "required": 0.0},
            "oosTotalNetR": {"operator": ">", "required": 0.0},
            "maximumDrawdownPct": {"operator": "<=", "required": 25.0},
            "positiveFoldCount": {"operator": ">=", "required": 3},
        },
        "formalGates": {
            "oosProfitFactor": {"operator": ">=", "required": 1.15},
            "oosAverageNetR": {"operator": ">=", "required": 0.05},
            "oosTotalNetR": {"operator": ">", "required": 0.0},
            "maximumDrawdownPct": {"operator": "<=", "required": 20.0},
            "positiveFoldCount": {"operator": ">=", "required": 4},
            "stress1_5xProfitFactor": {"operator": ">=", "required": 1.05},
            "stress1_5xAverageNetR": {"operator": ">", "required": 0.0},
            "singleInstrumentPositiveContribution": {"operator": "<=", "required": 0.35},
            "singleMonthPositiveContribution": {"operator": "<=", "required": 0.35},
            "holdoutAccessBeforeFinalEvaluation": {"operator": "==", "required": 0},
        },
        "costScenarios": {
            "base": {"multiplier": 1.0, "feeBpsPerSide": 5.0, "slippageBpsPerSide": 3.0, "spreadProxyBpsPerSide": 2.0},
            "stress_1_5x": {"multiplier": 1.5},
            "stress_2x": {"multiplier": 2.0},
        },
        "sameBarRule": "stop_first_conservative",
        "riskPolicy": (
            {
                "riskFractionPerEvent": 0.01,
                "initialStopMayWiden": False,
                "riskMetric": "R",
                "targetRGateMode": "advisory",
                "minimumTargetR": None,
                "exitPolicyRequired": True,
                "exitPolicyVersion": candidates[0].exitPolicy.version,
            }
            if advisory
            else {
                "riskFractionPerEvent": 0.01,
                "initialStopMayWiden": False,
                "minimumTargetR": 2.0,
            }
        ),
        "stopRules": {
            "prescreenFailure": "stop_candidate_before_full_backtest",
            "formalFailure": "retain_failed_evidence_without_release",
            "noForcedWinner": True,
        },
        "factorDiscoveryBranch": {"enabled": False},
    }
    campaign_id = stable_hash(core, prefix="phase3c_campaign")
    return {**core, "campaignId": campaign_id, "preregistrationHash": stable_hash(core, prefix="campaign_preregistration")}
