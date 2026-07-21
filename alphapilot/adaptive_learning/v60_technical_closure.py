"""Truthful V60.2 Adaptive Learning technical-closure evidence.

Engineering checks in this module never substitute for predictive validation,
reconciled Demo outcomes, or exact Live release approval.
"""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.evolution.promotion.drift_monitor import (
    DemoDriftObservation,
    evaluate_demo_drift,
)
from alphapilot.evolution.promotion.rollback import decide_demo_rollback
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.factors.alpha101_style_overlay import (
    ALPHA101_STYLE_FACTOR_COLUMNS,
    add_alpha101_style_factors,
)


REQUIRED_TECHNICAL_CAPABILITIES = (
    "factorProductionReady",
    "realFactorBenchReady",
    "alpha101Ready",
    "alpha191CompatibilityReady",
    "validatedCryptoFactorSubsetReady",
    "boundedFactorMiningReady",
    "adaptiveMlTrainingReady",
    "qlibOfflineCampaignReady",
    "modelRegistryReady",
    "continuousLearningDatasetReady",
    "demoOutcomeToTrainingSampleReady",
    "shadowInferenceReady",
    "demoDecisionModeValidated",
    "modelDriftMonitoringReady",
    "modelRollbackReady",
    "onlineInferenceLatencyReady",
    "liveFeaturePipelineReady",
    "liveModelInferenceReady",
    "modelReleaseBindingReady",
)

_DECISION_MODES = {"rank_only", "veto_only", "meta_label"}
_READY_STATUSES = {"completed", "passed", "ready", "validated"}


def _write_atomic(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(content)
    temporary.replace(path)


def _canonical_json(payload: Mapping[str, Any]) -> bytes:
    return (
        json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    _write_atomic(path, json.dumps(
        dict(payload),
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ).encode("utf-8") + b"\n")


def _explicit_evidence(
    *,
    schema_version: str,
    ready: bool,
    reason: str,
    blockers: Sequence[str] = (),
    details: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    core = {
        "schemaVersion": schema_version,
        "status": "passed" if ready else "blocked",
        "passed": ready,
        "reason": reason,
        "blockers": list(blockers),
        "details": dict(details or {}),
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {**core, "evidenceHash": stable_hash(core, prefix=schema_version)}


def _maximum_walk_forward_fold_count(payload: Any) -> int:
    if isinstance(payload, Mapping):
        counts = [
            len(value)
            for key, value in payload.items()
            if key == "folds" and isinstance(value, list)
        ]
        counts.extend(_maximum_walk_forward_fold_count(value) for value in payload.values())
        return max(counts, default=0)
    if isinstance(payload, list):
        return max((_maximum_walk_forward_fold_count(item) for item in payload), default=0)
    return 0


def _artifact_manifest(output: Path, *, generated_at: str) -> dict[str, Any]:
    rows = []
    for path in sorted(item for item in output.rglob("*") if item.is_file()):
        if path.name == "artifact_manifest.json":
            continue
        content = path.read_bytes()
        rows.append(
            {
                "path": path.relative_to(output).as_posix(),
                "sha256": hashlib.sha256(content).hexdigest(),
                "sizeBytes": len(content),
            }
        )
    core = {
        "schemaVersion": "v60_2_adaptive_learning_technical_closure_manifest_v1",
        "generatedAt": generated_at,
        "artifactCount": len(rows),
        "artifacts": rows,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {**core, "manifestHash": stable_hash(core, prefix="v60_2_manifest")}


def serialize_research_model_artifact(
    *,
    artifact: Mapping[str, Any],
    output_path: Path | str,
) -> dict[str, Any]:
    """Persist canonical research-model bytes without changing lifecycle."""

    payload = dict(artifact)
    if payload.get("researchOnly") is not True:
        raise ValueError("Only research-only artifacts may use this closure writer")
    if not str(payload.get("modelHash") or ""):
        raise ValueError("A modelHash is required")
    content = _canonical_json(payload)
    path = Path(output_path).expanduser().resolve()
    _write_atomic(path, content)
    digest = hashlib.sha256(content).hexdigest()
    core = {
        "schemaVersion": "v60_2_research_model_artifact_integrity_v1",
        "status": "passed",
        "passed": True,
        "artifactIntegrityReady": True,
        "artifactPath": str(path),
        "artifactSha256": digest,
        "modelHash": str(payload["modelHash"]),
        "researchOnly": True,
        "liveEligible": False,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {
        **core,
        "evidenceHash": stable_hash(core, prefix="research_model_integrity"),
    }


def run_alpha101_prefix_invariance_fixture() -> dict[str, Any]:
    """Prove the local Alpha101-style overlay does not read future rows."""

    rows: list[dict[str, Any]] = []
    timestamps = pd.date_range("2025-01-01", periods=40, freq="4h", tz="UTC")
    for time_index, timestamp in enumerate(timestamps):
        for pair_index, pair in enumerate(("BTC/USDT", "ETH/USDT", "SOL/USDT")):
            wave = math.sin((time_index + pair_index) / 5)
            close = 100 + pair_index * 25 + time_index * 0.3 + wave
            rows.append(
                {
                    "date": timestamp,
                    "pair": pair,
                    "close": close,
                    "volume": 1_000 + pair_index * 100 + time_index * 7,
                    "return_1": 0.001 * (pair_index - 1) + wave * 0.002,
                    "return_3": 0.003 * (pair_index - 1) + wave * 0.004,
                    "return_12": 0.006 * (pair_index - 1) + wave * 0.008,
                    "volume_ratio": 0.8 + pair_index * 0.2 + abs(wave) * 0.3,
                    "bollinger_z": wave + (pair_index - 1) * 0.2,
                    "mark_basis_pct": (pair_index - 1) * 0.0005 + wave * 0.0002,
                    "atr_pct": 0.01 + pair_index * 0.002 + abs(wave) * 0.001,
                    "close_location": 0.5 + wave * 0.25,
                }
            )
    frame = pd.DataFrame(rows)
    cutoff = timestamps[29]
    prefix = frame.loc[frame["date"] <= cutoff].copy()
    full_result = add_alpha101_style_factors(frame)
    prefix_result = add_alpha101_style_factors(prefix)
    full_prefix = full_result.loc[full_result["date"] <= cutoff].reset_index(drop=True)
    prefix_result = prefix_result.reset_index(drop=True)
    deterministic = add_alpha101_style_factors(prefix).equals(prefix_result)
    prefix_invariant = len(full_prefix) == len(prefix_result)
    if prefix_invariant:
        for column in ALPHA101_STYLE_FACTOR_COLUMNS:
            left = full_prefix[column]
            right = prefix_result[column]
            equal = (left.eq(right) | (left.isna() & right.isna())).all()
            if not bool(equal):
                prefix_invariant = False
                break
    core = {
        "schemaVersion": "v60_2_alpha101_prefix_invariance_v1",
        "status": "passed" if deterministic and prefix_invariant else "blocked",
        "passed": deterministic and prefix_invariant,
        "deterministic": deterministic,
        "prefixInvariant": prefix_invariant,
        "checkedFactorCount": len(ALPHA101_STYLE_FACTOR_COLUMNS),
        "checkedRowCount": len(prefix_result),
        "cutoff": cutoff.isoformat(),
        "usesSyntheticFixture": True,
        "predictiveValidationClaimed": False,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {**core, "checkHash": stable_hash(core, prefix="alpha101_prefix_check")}


def audit_alpha101_compatibility(
    *,
    production_registry: Mapping[str, Any],
    prefix_invariance: Mapping[str, Any],
) -> dict[str, Any]:
    """Audit bounded local Alpha101-style compatibility, not alpha performance."""

    factors = [
        dict(item)
        for item in production_registry.get("factors") or []
        if isinstance(item, Mapping)
        and str(item.get("sourceClass") or "") == "alpha101_style"
    ]
    blockers: list[str] = []
    if not factors:
        blockers.append("no_registered_alpha101_style_factors")
    if prefix_invariance.get("passed") is not True:
        blockers.append("alpha101_prefix_invariance_failed")
    if prefix_invariance.get("deterministic") is not True:
        blockers.append("alpha101_overlay_not_deterministic")
    if prefix_invariance.get("prefixInvariant") is not True:
        blockers.append("alpha101_overlay_reads_future_rows")
    core = {
        "schemaVersion": "v60_2_alpha101_crypto_compatibility_audit_v1",
        "status": "passed" if not blockers else "blocked",
        "passed": not blockers,
        "validationScope": "bounded_implementation_and_point_in_time_compatibility_only",
        "registeredFactorIds": sorted(str(item.get("factorId") or "") for item in factors),
        "registeredFactorCount": len(factors),
        "checkedFactorCount": int(prefix_invariance.get("checkedFactorCount") or 0),
        "checkedRowCount": int(prefix_invariance.get("checkedRowCount") or 0),
        "prefixCheckHash": prefix_invariance.get("checkHash"),
        "pointInTimeCompatibilityReady": not blockers,
        "predictiveValidationClaimed": False,
        "externalSourceCodeCopied": False,
        "blockers": blockers,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {**core, "evidenceHash": stable_hash(core, prefix="alpha101_compatibility")}


def _healthy_observation() -> DemoDriftObservation:
    return DemoDriftObservation(
        dataFresh=True,
        metadataFresh=True,
        clockSynchronized=True,
        ledgerMatchesExchange=True,
        checksumsMatch=True,
        rollingProfitFactor=1.25,
        consecutiveLosses=1,
        observedSlippageBps=2.0,
        assumedSlippageBps=2.0,
        calibrationError=0.04,
        regimePerformanceDrop=0.10,
    )


def build_drift_rollback_engineering_rehearsal(
    *,
    champion_model_id: str | None,
    predecessor_model_id: str | None,
    production_observation_count: int = 0,
    exact_rollback_rehearsed: bool = False,
) -> dict[str, Any]:
    """Exercise fail-closed model controls without claiming production evidence."""

    healthy = evaluate_demo_drift(_healthy_observation())
    critical = evaluate_demo_drift(
        DemoDriftObservation(
            **{
                **_healthy_observation().__dict__,
                "checksumsMatch": False,
                "rollingProfitFactor": 0.8,
            }
        )
    )
    rollback = decide_demo_rollback(
        critical,
        previousStableReleaseId=predecessor_model_id or "fixture-predecessor",
        previousReleaseStillValid=True,
    )
    pause = decide_demo_rollback(
        critical,
        previousStableReleaseId=None,
        previousReleaseStillValid=False,
    )
    engineering_passed = (
        not healthy.pauseRequired
        and critical.pauseRequired
        and "checksum_mismatch" in critical.reasonCodes
        and rollback.action == "rollback_demo_release"
        and rollback.stopNewEntries
        and pause.action == "pause_demo_release"
        and pause.stopNewEntries
        and not rollback.liveActionAllowed
    )
    drift_ready = bool(champion_model_id) and production_observation_count > 0
    rollback_ready = bool(
        champion_model_id and predecessor_model_id and exact_rollback_rehearsed
    )
    blockers: list[str] = []
    if not champion_model_id:
        blockers.append("no_live_eligible_champion_model")
    if production_observation_count <= 0:
        blockers.append("no_production_drift_observations")
    if not champion_model_id or not predecessor_model_id:
        blockers.append("no_champion_predecessor_pair")
    if not exact_rollback_rehearsed:
        blockers.append("exact_model_rollback_not_rehearsed")
    core = {
        "schemaVersion": "v60_2_drift_rollback_engineering_rehearsal_v1",
        "status": "completed_with_production_blockers" if engineering_passed else "blocked",
        "passed": engineering_passed,
        "engineeringPassed": engineering_passed,
        "healthyAction": "continue_demo_release" if not healthy.pauseRequired else "unexpected_pause",
        "criticalReasonCodes": list(critical.reasonCodes),
        "criticalRollbackAction": rollback.action,
        "criticalWithoutPredecessorAction": pause.action,
        "productionObservationCount": int(production_observation_count),
        "productionDriftMonitoringReady": drift_ready,
        "productionRollbackReady": rollback_ready,
        "blockers": blockers,
        "fixtureEvidenceExcludedFromProductionReadiness": True,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {**core, "evidenceHash": stable_hash(core, prefix="drift_rollback_rehearsal")}


def audit_demo_decision_mode(
    *,
    decisions: Sequence[Mapping[str, Any]],
    reconciled_outcomes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Require real decision-participating Demo evidence and closed outcomes."""

    production_decisions = [
        dict(item)
        for item in decisions
        if str(item.get("decisionMode") or "") in _DECISION_MODES
        and item.get("engineeringSmoke") is not True
        and item.get("fixture") is not True
    ]
    decision_ids = {
        str(item.get("modelDecisionId") or "")
        for item in production_decisions
        if str(item.get("modelDecisionId") or "")
    }
    outcomes = [
        dict(item)
        for item in reconciled_outcomes
        if item.get("reconciled") is True
        and item.get("closed") is True
        and item.get("engineeringSmoke") is not True
        and str(item.get("modelDecisionId") or "") in decision_ids
    ]
    blockers: list[str] = []
    if not production_decisions:
        blockers.append("no_decision_participating_demo_mode")
    if not outcomes:
        blockers.append("no_reconciled_closed_demo_outcomes")
    core = {
        "schemaVersion": "v60_2_demo_decision_mode_validation_v1",
        "status": "passed" if not blockers else "blocked",
        "passed": not blockers,
        "decisionCount": len(production_decisions),
        "reconciledClosedOutcomeCount": len(outcomes),
        "validatedModes": sorted(
            {str(item.get("decisionMode")) for item in production_decisions}
        ),
        "observerDecisionsExcluded": sum(
            str(item.get("decisionMode") or "") == "observer" for item in decisions
        ),
        "engineeringSmokeExcluded": True,
        "blockers": blockers,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {**core, "evidenceHash": stable_hash(core, prefix="demo_decision_mode")}


def _artifact_ready(payload: Mapping[str, Any] | None) -> bool:
    artifact = dict(payload or {})
    return artifact.get("passed") is True and str(artifact.get("status") or "") in _READY_STATUSES


def build_technical_closure_matrix(
    *,
    prior_readiness: Mapping[str, Any],
    evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Merge evidence without creating a successor model or Live identity."""

    prior = dict(
        prior_readiness.get("evidenceStatus")
        or prior_readiness.get("evidence")
        or {}
    )
    status: dict[str, bool] = {}
    rows: list[dict[str, Any]] = []
    for capability in REQUIRED_TECHNICAL_CAPABILITIES:
        artifact = evidence.get(capability)
        ready = prior.get(capability) is True or _artifact_ready(artifact)
        status[capability] = ready
        rows.append(
            {
                "capability": capability,
                "ready": ready,
                "source": "new_evidence" if _artifact_ready(artifact) else (
                    "prior_verified_evidence" if prior.get(capability) is True else "blocked"
                ),
                "evidenceHash": (
                    artifact.get("evidenceHash") if isinstance(artifact, Mapping) else None
                ),
                "blockers": list(artifact.get("blockers") or [])
                if isinstance(artifact, Mapping) and not ready
                else [],
            }
        )
    passed = all(status.values())
    core = {
        "schemaVersion": "v60_2_adaptive_learning_technical_closure_matrix_v1",
        "status": "ready_for_successor_identity_generation" if passed else "blocked_not_ready",
        "passed": passed,
        "readyCount": sum(status.values()),
        "requiredCount": len(status),
        "capabilities": rows,
        "evidence": status,
        "successorIdentity": None,
        "successorIdentityGenerationAllowed": passed,
        "approvalRequestActionable": False,
        "liveArmAllowed": False,
        "liveEnabled": False,
        "withdrawAllowed": False,
        "createsOrders": False,
        "changesRisk": False,
    }
    return {**core, "matrixHash": stable_hash(core, prefix="adaptive_technical_closure")}


def build_v60_technical_closure_evidence(
    *,
    output_dir: Path | str,
    generated_at: str,
    production_registry: Mapping[str, Any],
    prior_readiness: Mapping[str, Any],
    model_record: Mapping[str, Any],
    factor_campaign: Mapping[str, Any],
    registry_audit: Mapping[str, Any],
    factor_benchmark: Mapping[str, Any],
    qlib_readiness: Mapping[str, Any],
    decisions: Sequence[Mapping[str, Any]],
    reconciled_outcomes: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Write a versioned closure bundle without changing frozen identities."""

    output = Path(output_dir).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)

    prefix_check = run_alpha101_prefix_invariance_fixture()
    alpha101 = audit_alpha101_compatibility(
        production_registry=production_registry,
        prefix_invariance=prefix_check,
    )
    artifact = dict(model_record.get("artifact") or {})
    model_integrity = serialize_research_model_artifact(
        artifact=artifact,
        output_path=output / "research_model_artifact.json",
    )

    eligible_factor_count = int(factor_benchmark.get("eligibleFactorCount") or 0)
    validated_subset = _explicit_evidence(
        schema_version="v60_2_validated_crypto_factor_subset_v1",
        ready=eligible_factor_count > 0,
        reason=(
            "At least one crypto factor survived the formal benchmark."
            if eligible_factor_count > 0
            else "The real Factor Bench completed, but no factor survived its formal gates."
        ),
        blockers=() if eligible_factor_count > 0 else ("no_formal_eligible_crypto_factor",),
        details={
            "factorBenchmarkStatus": factor_benchmark.get("status"),
            "eligibleFactorCount": eligible_factor_count,
            "formalTrialCount": int(factor_benchmark.get("formalTrialCount") or 0),
        },
    )

    fold_count = _maximum_walk_forward_fold_count(factor_campaign)
    live_model_count = int(registry_audit.get("liveEligibleModelCount") or 0)
    training_ready = bool(
        factor_campaign.get("formalPromotionEligible") is True
        and fold_count > 0
        and live_model_count > 0
    )
    training_blockers: list[str] = []
    if factor_campaign.get("formalPromotionEligible") is not True:
        training_blockers.append("formal_factor_campaign_has_no_promotable_candidate")
    if fold_count <= 0:
        training_blockers.append("purged_walk_forward_fold_evidence_missing")
    if live_model_count <= 0:
        training_blockers.append("no_validated_live_eligible_model")
    adaptive_training = _explicit_evidence(
        schema_version="v60_2_adaptive_ml_training_readiness_v1",
        ready=training_ready,
        reason=(
            "Training, purged walk-forward, and model validation all passed."
            if training_ready
            else "Training ran, but predictive and promotion evidence is not Live-ready."
        ),
        blockers=training_blockers,
        details={
            "campaignStatus": factor_campaign.get("status"),
            "formalPromotionEligible": factor_campaign.get("formalPromotionEligible") is True,
            "observedPurgedWalkForwardFoldCount": fold_count,
            "liveEligibleModelCount": live_model_count,
            "campaignBlockers": list(factor_campaign.get("blockers") or []),
        },
    )

    qlib_ready = bool(
        qlib_readiness.get("qlibCampaignMayRun") is True
        and qlib_readiness.get("modelCampaignRun") is True
        and qlib_readiness.get("status") in _READY_STATUSES
    )
    qlib = _explicit_evidence(
        schema_version="v60_2_qlib_campaign_readiness_v1",
        ready=qlib_ready,
        reason=(
            "A production Qlib campaign completed."
            if qlib_ready
            else "Qlib remains blocked by formal data/runtime prerequisites."
        ),
        blockers=() if qlib_ready else tuple(qlib_readiness.get("blockers") or ("qlib_campaign_not_run",)),
        details={
            "qlibCampaignMayRun": qlib_readiness.get("qlibCampaignMayRun") is True,
            "modelCampaignRun": qlib_readiness.get("modelCampaignRun") is True,
        },
    )

    registered_binary_ready = bool(
        model_record.get("artifactPath")
        and model_record.get("artifactSha256")
        and model_integrity.get("artifactSha256") == model_record.get("artifactSha256")
    )
    model_registry = _explicit_evidence(
        schema_version="v60_2_model_registry_readiness_v1",
        ready=registered_binary_ready,
        reason=(
            "The registered model binary path and digest were verified."
            if registered_binary_ready
            else "Canonical research bytes exist, but the registry has no verified production artifact binding."
        ),
        blockers=() if registered_binary_ready else ("research_model_artifact_not_registered_with_verified_binary",),
        details={
            "modelId": model_record.get("modelId"),
            "modelHash": artifact.get("modelHash"),
            "registryStatus": model_record.get("status"),
            "researchOnly": artifact.get("researchOnly") is True,
            "canonicalArtifactSha256": model_integrity.get("artifactSha256"),
        },
    )

    decision_audit = audit_demo_decision_mode(
        decisions=decisions,
        reconciled_outcomes=reconciled_outcomes,
    )
    production_decision_count = int(decision_audit.get("decisionCount") or 0)
    closed_outcome_count = int(decision_audit.get("reconciledClosedOutcomeCount") or 0)
    continuous_dataset = _explicit_evidence(
        schema_version="v60_2_continuous_learning_dataset_readiness_v1",
        ready=production_decision_count > 0 and closed_outcome_count > 0,
        reason=(
            "Decision-participating Demo observations and reconciled outcomes exist."
            if production_decision_count > 0 and closed_outcome_count > 0
            else "No closed decision-participating Demo sample is available."
        ),
        blockers=() if production_decision_count > 0 and closed_outcome_count > 0 else ("no_closed_demo_learning_samples",),
        details={
            "decisionCount": production_decision_count,
            "reconciledClosedOutcomeCount": closed_outcome_count,
        },
    )
    demo_samples = _explicit_evidence(
        schema_version="v60_2_demo_outcome_training_sample_readiness_v1",
        ready=closed_outcome_count > 0,
        reason=(
            "Reconciled closed Demo outcomes are linked to model decisions."
            if closed_outcome_count > 0
            else "There are no reconciled closed Demo outcomes linked to model decisions."
        ),
        blockers=() if closed_outcome_count > 0 else ("demo_learning_sample_count_zero",),
        details={"reconciledClosedOutcomeCount": closed_outcome_count},
    )

    drift_rollback = build_drift_rollback_engineering_rehearsal(
        champion_model_id=None,
        predecessor_model_id=None,
        production_observation_count=closed_outcome_count,
        exact_rollback_rehearsed=False,
    )
    live_model = _explicit_evidence(
        schema_version="v60_2_live_model_inference_readiness_v1",
        ready=False,
        reason="The current model is research-only observer evidence and cannot enter Live.",
        blockers=("no_live_eligible_decision_participating_model",),
        details={
            "modelHash": artifact.get("modelHash"),
            "researchOnly": artifact.get("researchOnly") is True,
            "observerModelMayEnterLive": False,
        },
    )
    release_binding = _explicit_evidence(
        schema_version="v60_2_model_release_binding_readiness_v1",
        ready=False,
        reason="No successor Live identity may be minted before all technical evidence passes.",
        blockers=("adaptive_learning_technical_readiness_incomplete",),
        details={
            "newModelHash": None,
            "newModelPolicyHash": None,
            "newLiveReleaseHash": None,
            "approvalRequest": None,
        },
    )

    capability_evidence = {
        "alpha101Ready": alpha101,
        "validatedCryptoFactorSubsetReady": validated_subset,
        "adaptiveMlTrainingReady": adaptive_training,
        "qlibOfflineCampaignReady": qlib,
        "modelRegistryReady": model_registry,
        "continuousLearningDatasetReady": continuous_dataset,
        "demoOutcomeToTrainingSampleReady": demo_samples,
        "demoDecisionModeValidated": decision_audit,
        "modelDriftMonitoringReady": drift_rollback,
        "modelRollbackReady": drift_rollback,
        "liveModelInferenceReady": live_model,
        "modelReleaseBindingReady": release_binding,
    }
    matrix = build_technical_closure_matrix(
        prior_readiness=prior_readiness,
        evidence=capability_evidence,
    )

    artifacts: dict[str, Mapping[str, Any]] = {
        "alpha101_prefix_invariance.json": prefix_check,
        "alpha101_compatibility_audit.json": alpha101,
        "research_model_artifact_integrity.json": model_integrity,
        "validated_crypto_factor_subset.json": validated_subset,
        "adaptive_ml_training_readiness.json": adaptive_training,
        "qlib_campaign_readiness.json": qlib,
        "model_registry_readiness.json": model_registry,
        "continuous_learning_dataset_readiness.json": continuous_dataset,
        "demo_outcome_training_sample_readiness.json": demo_samples,
        "demo_decision_mode_validation.json": decision_audit,
        "drift_rollback_engineering_rehearsal.json": drift_rollback,
        "live_model_inference_readiness.json": live_model,
        "model_release_binding_readiness.json": release_binding,
        "adaptive_learning_technical_closure_matrix.json": matrix,
    }
    for filename, payload in artifacts.items():
        _write_json(output / filename, {**dict(payload), "generatedAt": generated_at})

    gap_register = {
        "schemaVersion": "v60_2_adaptive_learning_technical_gap_register_v1",
        "generatedAt": generated_at,
        "status": "completed" if matrix["passed"] else "blocked_not_ready",
        "readyCount": matrix["readyCount"],
        "requiredCount": matrix["requiredCount"],
        "gaps": [row for row in matrix["capabilities"] if not row["ready"]],
        "exactHumanApprovalIsTechnicalPrerequisite": False,
        "approvalRequestActionable": False,
        "liveArmAllowed": False,
        "createsOrders": False,
    }
    _write_json(output / "technical_gap_register.json", gap_register)

    closeout = f"""# V60.2 Adaptive Learning 技术缺口收口报告

- 技术就绪：`{matrix['readyCount']}/{matrix['requiredCount']}`，状态 `{matrix['status']}`。
- Alpha101：完成本地实现的确定性与时点前缀一致性核验；不声明预测有效性。
- 真实 Factor Bench：已运行，但合格因子数为 `{eligible_factor_count}`。
- 当前模型：`{artifact.get('modelHash')}`，仅为 research-only / observer 证据，不得进入 Live。
- Demo 学习证据：决策参与记录 `{production_decision_count}` 条，已对账闭合结果 `{closed_outcome_count}` 条。
- Qlib：`{qlib['status']}`；Formal 数据与运行前置未满足时不伪造 Campaign。
- 漂移与回滚：工程故障路径已演练，但生产观测、冠军/前任模型与精确回滚仍缺失。
- 后续 Model / Model Policy / Live Release / Approval Request：均未生成。
- 人工精确批准不属于技术就绪前置；技术就绪通过前不请求批准、不 ARM、不创建 Live 策略订单。
- Live 与 Withdraw 保持关闭，Risk Profile 及策略参数未修改。
"""
    _write_atomic((output / "final_closeout_cn.md"), closeout.encode("utf-8"))
    manifest = _artifact_manifest(output, generated_at=generated_at)
    _write_json(output / "artifact_manifest.json", manifest)

    return {
        "status": matrix["status"],
        "technicalReadinessPassed": matrix["passed"],
        "readyCount": matrix["readyCount"],
        "requiredCount": matrix["requiredCount"],
        "successorIdentity": None,
        "approvalRequestActionable": False,
        "liveArmAllowed": False,
        "createsOrders": False,
        "manifestHash": manifest["manifestHash"],
        "output": str(output),
    }
