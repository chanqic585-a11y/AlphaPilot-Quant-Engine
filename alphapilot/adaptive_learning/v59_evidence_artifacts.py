"""Build truthful V59 evidence without promoting failed research.

These helpers separate engineering and compatibility evidence from predictive
validation. A completed campaign may still fail every Live-readiness gate.
"""

from __future__ import annotations

import math
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.models.trainer import (
    TrainedModelArtifact,
    predict_probabilities,
)


def _percentile(values: Sequence[float], percentile: float) -> float:
    ordered = sorted(float(value) for value in values)
    if not ordered:
        return 0.0
    rank = (len(ordered) - 1) * percentile
    lower = int(math.floor(rank))
    upper = int(math.ceil(rank))
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def build_alpha191_compatibility_audit(
    *,
    production_registry: Mapping[str, Any],
    numeric_crossvalidation: Mapping[str, Any],
) -> dict[str, Any]:
    """Audit the bounded reviewed Alpha191 compatibility layer only."""

    compatibility = dict(production_registry.get("alpha191Compatibility") or {})
    catalog_count = int(compatibility.get("catalogCount") or 0)
    reviewed_count = int(compatibility.get("formulaReviewedCount") or 0)
    crossvalidated_count = int(compatibility.get("numericCrossvalidatedCount") or 0)
    production_validated_count = int(compatibility.get("productionValidatedCount") or 0)
    seed_count = int(numeric_crossvalidation.get("seedCount") or 0)
    mismatch_count = int(numeric_crossvalidation.get("unexpectedMismatchCount") or 0)
    conflict_count = int(numeric_crossvalidation.get("formulaConflictCount") or 0)
    blockers: list[str] = []
    if catalog_count != 191:
        blockers.append("alpha191_catalog_incomplete")
    if reviewed_count <= 0:
        blockers.append("no_reviewed_alpha191_formulas")
    if crossvalidated_count < reviewed_count or seed_count < reviewed_count:
        blockers.append("reviewed_formulas_not_fully_crossvalidated")
    if mismatch_count:
        blockers.append("unexpected_numeric_mismatch")
    if conflict_count:
        blockers.append("formula_conflict_detected")

    core = {
        "schemaVersion": "alpha191_compatibility_audit_v2",
        "status": "passed" if not blockers else "blocked",
        "passed": not blockers,
        "validationScope": "formula_and_numeric_compatibility_only",
        "catalogCount": catalog_count,
        "formulaReviewedCount": reviewed_count,
        "numericCrossvalidatedCount": crossvalidated_count,
        "numericSeedCount": seed_count,
        "unexpectedMismatchCount": mismatch_count,
        "formulaConflictCount": conflict_count,
        "productionValidatedCount": production_validated_count,
        "allFactorsProductionValidated": production_validated_count == catalog_count,
        "predictiveValidationClaimed": False,
        "numericCrossvalidationRef": numeric_crossvalidation.get("reportHash"),
        "blockers": blockers,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {
        **core,
        "evidenceHash": stable_hash(core, prefix="alpha191_compatibility_audit"),
    }


def build_model_validation_report(
    *,
    campaign: Mapping[str, Any],
    registry_audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Bind formal campaign failure evidence to the model registry audit."""

    candidates = list(campaign.get("strategyCandidates") or [])
    live_model_count = int(registry_audit.get("liveEligibleModelCount") or 0)
    campaign_passed = (
        campaign.get("formalPromotionEligible") is True
        and bool(candidates)
        and live_model_count > 0
    )
    blockers = sorted(
        {
            *(str(item) for item in campaign.get("blockers") or []),
            *([] if live_model_count else ["no_live_eligible_models"]),
            *([] if candidates else ["no_formal_strategy_candidate"]),
        }
    )
    core = {
        "schemaVersion": "v59_model_validation_report_v1",
        "status": "passed" if campaign_passed else "completed_failed",
        "passed": campaign_passed,
        "campaignStatus": campaign.get("status"),
        "campaignReportId": campaign.get("reportId"),
        "dataSnapshotId": campaign.get("dataSnapshotId"),
        "walkForwardManifestHash": dict(campaign.get("walkForwardManifest") or {}).get(
            "manifestHash"
        ),
        "experimentCount": len(campaign.get("experiments") or []),
        "registeredModelCount": len(campaign.get("models") or []),
        "candidateCount": len(candidates),
        "liveEligibleModelCount": live_model_count,
        "registryAuditHash": registry_audit.get("auditHash"),
        "blockers": blockers,
        "failedEvidencePreserved": True,
        "researchOnly": not campaign_passed,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {
        **core,
        "evidenceHash": stable_hash(core, prefix="v59_model_validation"),
    }


def build_training_dataset_manifest(
    *,
    campaign: Mapping[str, Any],
    matrix_path: str | Path,
    demo_learning_sample_count: int,
    live_learning_sample_count: int,
) -> dict[str, Any]:
    """Describe market research rows separately from eligible outcome samples."""

    matrix = dict(campaign.get("matrix") or {})
    eligible_outcomes = int(demo_learning_sample_count) + int(live_learning_sample_count)
    blockers = [] if eligible_outcomes > 0 else ["no_reconciled_closed_strategy_outcomes"]
    core = {
        "schemaVersion": "v59_training_dataset_manifest_v1",
        "status": "passed" if not blockers else "blocked",
        "passed": not blockers,
        "dataSnapshotId": campaign.get("dataSnapshotId"),
        "formalMarketMatrixPath": str(matrix_path),
        "formalMarketMatrixHash": matrix.get("matrixHash") or matrix.get("contentHash"),
        "formalMarketRowCount": int(matrix.get("rowCount") or 0),
        "formalFeatureColumns": list(matrix.get("featureColumns") or []),
        "walkForwardManifestHash": dict(campaign.get("walkForwardManifest") or {}).get(
            "manifestHash"
        ),
        "demoLearningSampleCount": int(demo_learning_sample_count),
        "liveLearningSampleCount": int(live_learning_sample_count),
        "eligibleClosedOutcomeCount": eligible_outcomes,
        "syntheticOutcomesUsed": False,
        "engineeringSmokeIncluded": False,
        "blockers": blockers,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {
        **core,
        "evidenceHash": stable_hash(core, prefix="v59_training_dataset_manifest"),
    }


def build_qlib_preflight_audit(
    *,
    readiness_gate: Mapping[str, Any],
    qlib_package_available: bool,
    docker_daemon_available: bool,
) -> dict[str, Any]:
    """Record why Qlib is not runnable without manufacturing campaign evidence."""

    blockers = [str(item) for item in readiness_gate.get("blockers") or []]
    if not qlib_package_available:
        blockers.append("qlib_package_unavailable")
    if not docker_daemon_available:
        blockers.append("docker_daemon_unavailable")
    blockers = sorted(set(blockers))
    preflight_ready = not blockers and readiness_gate.get("status") in {
        "passed",
        "ready",
        "completed",
    }
    core = {
        "schemaVersion": "v59_qlib_preflight_audit_v1",
        "status": "ready_to_run" if preflight_ready else "blocked",
        "passed": preflight_ready,
        "campaignExecuted": False,
        "dataReadinessStatus": readiness_gate.get("status"),
        "qlibPackageAvailable": bool(qlib_package_available),
        "dockerDaemonAvailable": bool(docker_daemon_available),
        "blockers": blockers,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {
        **core,
        "evidenceHash": stable_hash(core, prefix="v59_qlib_preflight_audit"),
    }


def run_shadow_inference_engineering_audit(
    *,
    model_artifact: Mapping[str, Any],
    feature_rows: Sequence[Sequence[float]],
    iterations: int = 5,
) -> dict[str, Any]:
    """Verify deterministic shadow inference without granting trading authority."""

    if iterations <= 0:
        raise ValueError("iterations must be positive")
    if not feature_rows:
        raise ValueError("feature_rows must not be empty")

    artifact = TrainedModelArtifact(
        modelType=str(model_artifact["modelType"]),
        featureNames=tuple(str(item) for item in model_artifact["featureNames"]),
        parameters=dict(model_artifact["parameters"]),
        metrics={
            str(key): float(value)
            for key, value in dict(model_artifact.get("metrics") or {}).items()
        },
        trainingEvidence=dict(model_artifact.get("trainingEvidence") or {}),
        modelHash=str(model_artifact["modelHash"]),
        researchOnly=bool(model_artifact.get("researchOnly", True)),
    )
    rows = [list(map(float, row)) for row in feature_rows]
    predictions: list[list[float]] = []
    latencies_ms: list[float] = []
    for _ in range(iterations):
        started = time.perf_counter()
        predictions.append(predict_probabilities(artifact, rows))
        latencies_ms.append((time.perf_counter() - started) * 1000)

    reference = predictions[0]
    deterministic = all(result == reference for result in predictions[1:])
    probabilities_valid = all(
        math.isfinite(probability) and 0.0 <= probability <= 1.0
        for result in predictions
        for probability in result
    )
    engineering_checks_passed = deterministic and probabilities_valid
    blockers: list[str] = []
    if not engineering_checks_passed:
        blockers.append("nondeterministic_or_invalid_inference")
    if artifact.researchOnly:
        blockers.append("research_only_model")
    if int(artifact.trainingEvidence.get("foldCount") or 0) <= 0:
        blockers.append("purged_walk_forward_fold_count_zero")

    core = {
        "schemaVersion": "v59_shadow_inference_engineering_audit_v1",
        "status": "passed" if not blockers else "blocked",
        "passed": not blockers,
        "engineeringChecksPassed": engineering_checks_passed,
        "modelHash": artifact.modelHash,
        "modelType": artifact.modelType,
        "rowCount": len(rows),
        "iterationCount": iterations,
        "deterministic": deterministic,
        "probabilitiesValid": probabilities_valid,
        "latencyMs": {
            "p50": _percentile(latencies_ms, 0.50),
            "p95": _percentile(latencies_ms, 0.95),
            "p99": _percentile(latencies_ms, 0.99),
            "maximum": max(latencies_ms),
        },
        "researchOnly": artifact.researchOnly,
        "trainingFoldCount": int(artifact.trainingEvidence.get("foldCount") or 0),
        "blockers": blockers,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {
        **core,
        "evidenceHash": stable_hash(core, prefix="v59_shadow_inference_audit"),
    }
