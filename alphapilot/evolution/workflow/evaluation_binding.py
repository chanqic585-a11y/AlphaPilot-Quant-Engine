"""Construct immutable formal evaluation bindings for one workflow attempt."""

from __future__ import annotations

from alphapilot.evolution.evaluation.validation_pack import FormalValidationPack
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.types import DataSnapshotRecord

from .repository import WorkflowRepository
from .types import (
    EvaluationBindingRecord,
    StrategyDataContractRecord,
    WorkflowRunRecord,
)


RUNNER_VERSION = "dual_layer_fixed_2r_v1"


def create_formal_evaluation_binding(
    repository: WorkflowRepository,
    *,
    run: WorkflowRunRecord,
    contract: StrategyDataContractRecord,
    snapshot: DataSnapshotRecord,
    validation_pack: FormalValidationPack,
    canonical_root: str,
    research_smoke: dict,
) -> EvaluationBindingRecord:
    if run.strategyVersionId != contract.strategyVersionId:
        raise ValueError("evaluation_binding_strategy_contract_mismatch")
    if validation_pack.dataSnapshotId != snapshot.dataSnapshotId:
        raise ValueError("evaluation_binding_snapshot_pack_mismatch")
    if run.gateProfileId is None:
        raise ValueError("evaluation_binding_gate_profile_missing")
    smoke_evidence = {
        "status": research_smoke.get("status"),
        "implementationValid": bool(research_smoke.get("implementationValid")),
        "formalPromotionEligible": False,
        "reportHash": research_smoke.get("reportHash"),
        "blockers": list(research_smoke.get("blockers") or []),
    }
    evidence = {
        "evidenceClass": "formal_backtest",
        "canonicalRoot": canonical_root,
        "strategyContentHash": contract.contract["strategyContentHash"],
        "strategyDataContractHash": contract.contentHash,
        "dataSnapshotContentHash": snapshot.contentHash,
        "signalTimeframe": contract.contract["signalTimeframe"],
        "executionTimeframe": contract.contract["executionTimeframe"],
        "executionFallbackTimeframe": contract.contract.get(
            "executionFallbackTimeframe"
        ),
        "regimeManifestHash": validation_pack.regimeManifestHash,
        "costManifestHash": validation_pack.costManifestHash,
        "sourceFileHashes": [
            {"path": row.get("path"), "sha256": row.get("sha256")}
            for row in snapshot.manifest.get("files", [])
        ],
        "researchSmoke": smoke_evidence,
        "formalEvidenceOnly": True,
    }
    core = {
        "workflowRunId": run.workflowRunId,
        "strategyDataContractId": contract.strategyDataContractId,
        "dataSnapshotId": snapshot.dataSnapshotId,
        "walkForwardManifestHash": validation_pack.walkForwardManifestHash,
        "holdoutManifestHash": validation_pack.holdoutManifestHash,
        "lockedOosManifestHash": validation_pack.lockedOosManifestHash,
        "gateProfileId": run.gateProfileId,
        "runnerVersion": RUNNER_VERSION,
        "costModel": dict(contract.contract["costPolicy"]),
        "evidence": evidence,
    }
    content_hash = stable_hash(core, prefix="evaluation_binding")
    return repository.create_evaluation_binding(
        EvaluationBindingRecord(
            evaluationBindingId=content_hash,
            contentHash=content_hash,
            **core,
        )
    )
