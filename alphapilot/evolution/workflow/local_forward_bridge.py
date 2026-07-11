"""Promote only a formal workflow pass into public local forward observation."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.forward.release import create_workflow_forward_release
from alphapilot.evolution.forward.runner import ForwardPublicMarket, run_forward_cycle
from alphapilot.evolution.forward.rules import is_supported_frozen_policy
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import StrategyCandidateRecord
from alphapilot.evolution.risk_profiles import register_default_risk_profiles

from .repository import WorkflowRepository
from .service import (
    checkpoint_workflow_run,
    complete_workflow_run,
    create_next_stage_run,
    queue_workflow_run,
    start_workflow_run,
)
from .types import (
    EvaluationBindingRecord,
    StrategyVersionRecord,
    WorkflowRunRecord,
)


def _formal_evidence(backtest_run: WorkflowRunRecord) -> dict[str, Any]:
    evidence = backtest_run.result.get("evidence")
    return evidence if isinstance(evidence, dict) else {}


def _validate_promotion(
    strategy_version: StrategyVersionRecord,
    backtest_run: WorkflowRunRecord,
    binding: EvaluationBindingRecord,
) -> dict[str, Any]:
    if backtest_run.stage != "backtest" or backtest_run.status != "passed":
        raise ValueError("Local forward requires a passed backtest")
    if binding.workflowRunId != backtest_run.workflowRunId:
        raise ValueError("Evaluation binding does not belong to the passed backtest")
    if binding.evidence.get("evidenceClass") != "formal_backtest":
        raise ValueError("Local forward requires formal workflow evidence")
    if float(strategy_version.definition.get("targetR", 0.0)) < 2.0:
        raise ValueError("Local forward requires targetR >= 2")
    if strategy_version.contentHash != binding.evidence.get("strategyContentHash"):
        raise ValueError("Strategy content hash mismatch")
    signal_policy = strategy_version.definition.get("forwardSignalPolicy")
    if not isinstance(signal_policy, dict) or not is_supported_frozen_policy(
        signal_policy
    ):
        raise ValueError("Local forward requires a frozen signal policy")
    market_access = strategy_version.definition.get("marketDataAccess", "public")
    if market_access != "public":
        raise ValueError("Local forward requires public-only market data")
    evidence = _formal_evidence(backtest_run)
    expected = {
        "evaluationBindingId": binding.evaluationBindingId,
        "dataSnapshotId": binding.dataSnapshotId,
        "walkForwardManifestHash": binding.walkForwardManifestHash,
        "holdoutManifestHash": binding.holdoutManifestHash,
        "lockedOosManifestHash": binding.lockedOosManifestHash,
        "regimeManifestHash": binding.evidence.get("regimeManifestHash"),
        "costManifestHash": binding.evidence.get("costManifestHash"),
    }
    if any(evidence.get(key) != value for key, value in expected.items()):
        raise ValueError("Formal evidence hash mismatch")
    return signal_policy


def _ensure_candidate(
    repository: RegistryRepository,
    *,
    strategy_version: StrategyVersionRecord,
    binding: EvaluationBindingRecord,
    signal_policy: dict[str, Any],
) -> StrategyCandidateRecord:
    snapshot = repository.get_data_snapshot(binding.dataSnapshotId)
    if snapshot is None:
        raise ValueError("Local forward snapshot is not registered")
    instruments = sorted(
        {str(value).upper() for value in snapshot.manifest.get("universeMembers", [])}
    )
    if not instruments:
        raise ValueError("Local forward formal universe is empty")
    target_r = float(strategy_version.definition["targetR"])
    is_short_cycle = (
        signal_policy.get("schemaVersion") == "short_cycle_forward_policy_v1"
    )
    max_holding = int(
        strategy_version.parameters.get(
            "max_hold" if is_short_cycle else "horizonBars"
        )
        or 0
    )
    exit_rules = {
        "stopLossR": 1.0,
        "takeProfitR": target_r,
        "maxHoldingBars": max_holding,
    }
    if is_short_cycle:
        exit_rules["stopAtr"] = float(
            strategy_version.parameters.get("stop_atr") or 0
        )
    else:
        exit_rules["stopLossPct"] = float(
            strategy_version.parameters.get("stopLossPct") or 0
        )
    payload = {
        "schemaVersion": "workflow_strategy_candidate_v1",
        "strategyVersionId": strategy_version.strategyVersionId,
        "strategyContentHash": strategy_version.contentHash,
        "name": strategy_version.displayName,
        "direction": strategy_version.definition.get("direction"),
        "marketDefinition": {
            "exchange": "okx",
            "marketType": "swap",
            "timeframe": strategy_version.definition.get("timeframe"),
            "eligibleInstruments": instruments,
            "universePolicy": "formal_point_in_time_snapshot",
            "marketDataAccess": "public",
            "publicOnly": True,
        },
        "forwardSignalPolicy": signal_policy,
        "exitRules": exit_rules,
        "riskRules": {
            "riskPerTradePct": 0.25,
            "maxLeverage": 1,
            "maxConcurrentPositions": 3,
        },
        "evidence": {
            "evidenceClass": "formal_backtest",
            "evaluationBindingId": binding.evaluationBindingId,
            "dataSnapshotId": binding.dataSnapshotId,
            "walkForwardManifestHash": binding.walkForwardManifestHash,
            "holdoutManifestHash": binding.holdoutManifestHash,
            "lockedOosManifestHash": binding.lockedOosManifestHash,
            "regimeManifestHash": binding.evidence["regimeManifestHash"],
            "costManifestHash": binding.evidence["costManifestHash"],
        },
        "rewardRiskRatio": target_r,
        "executionEnabled": False,
        "createsOrders": False,
        "demoPromotionAllowed": False,
        "livePromotionAllowed": False,
    }
    content_hash = stable_hash(payload)
    return repository.create_strategy_candidate(
        StrategyCandidateRecord(
            strategyCandidateId=stable_hash(payload, prefix="strategy_candidate"),
            strategyFamilyId=strategy_version.strategyFamilyId,
            name=strategy_version.displayName,
            status="formal_backtest_passed",
            candidate=payload,
            contentHash=content_hash,
        )
    )


def start_local_forward_after_pass(
    workflow: WorkflowRepository,
    registry: RegistryRepository,
    strategy_version: StrategyVersionRecord,
    backtest_run: WorkflowRunRecord,
    evaluation_binding: EvaluationBindingRecord,
    code_commit: str,
    market_data: ForwardPublicMarket,
) -> WorkflowRunRecord:
    """Start one public/virtual cycle and keep the next stage restart-safe."""

    current = workflow.get_latest_workflow_run(strategy_version.strategyVersionId)
    if (
        current is not None
        and current.stage == "local_forward"
        and current.result.get("evaluationBindingId")
        == evaluation_binding.evaluationBindingId
    ):
        return current
    signal_policy = _validate_promotion(
        strategy_version, backtest_run, evaluation_binding
    )
    candidate = _ensure_candidate(
        registry,
        strategy_version=strategy_version,
        binding=evaluation_binding,
        signal_policy=signal_policy,
    )
    profile = register_default_risk_profiles(registry)["local_forward"]
    formal_result = {"status": backtest_run.status, **backtest_run.result}
    release = create_workflow_forward_release(
        strategy_version=strategy_version,
        strategy_candidate=candidate,
        evaluation_binding=evaluation_binding,
        backtest_result=formal_result,
        repository=registry,
        code_commit=code_commit,
        risk_profile=profile,
    )
    next_run = create_next_stage_run(
        workflow, strategy_version.strategyVersionId, actor="system"
    )
    next_run = queue_workflow_run(
        workflow, next_run.workflowRunId, actor="system"
    )
    next_run = start_workflow_run(
        workflow, next_run.workflowRunId, actor="worker"
    )
    try:
        cycle = run_forward_cycle(
            release,
            repository=registry,
            market_data=market_data,
            code_commit=code_commit,
        )
    except Exception as error:
        return complete_workflow_run(
            workflow,
            next_run.workflowRunId,
            status="blocked",
            actor="worker",
            result={
                "forwardReleaseId": release.forwardReleaseId,
                "evaluationBindingId": evaluation_binding.evaluationBindingId,
                "error": str(error),
            },
            evidence={
                "forwardReleaseId": release.forwardReleaseId,
                "evaluationBindingId": evaluation_binding.evaluationBindingId,
            },
            failure={
                "category": "exchange_operational",
                "summary": str(error),
                "retryDisposition": "same_version_retry",
                "metrics": {},
                "suggestions": ["Retry the public local-forward cycle."],
            },
        )
    cycle_result = {
        "forwardReleaseId": cycle.forwardReleaseId,
        "forwardSessionId": cycle.forwardSessionId,
        "evaluationBindingId": evaluation_binding.evaluationBindingId,
        "cycleStatus": cycle.status,
        "observedInstrumentCount": cycle.observedInstrumentCount,
        "eventCount": cycle.eventCount,
        "closedOutcomeCount": cycle.closedOutcomeCount,
        "collectionFailureCount": cycle.collectionFailureCount,
    }
    if cycle.collectionFailureCount:
        return complete_workflow_run(
            workflow,
            next_run.workflowRunId,
            status="blocked",
            actor="worker",
            result=cycle_result,
            evidence={
                "forwardReleaseId": cycle.forwardReleaseId,
                "forwardSessionId": cycle.forwardSessionId,
                "evaluationBindingId": evaluation_binding.evaluationBindingId,
            },
            failure={
                "category": "exchange_operational",
                "summary": "Public local-forward collection failed for one or more instruments.",
                "retryDisposition": "same_version_retry",
                "metrics": {
                    "collectionFailureCount": cycle.collectionFailureCount
                },
                "suggestions": ["Retry after public market data recovers."],
            },
        )
    return checkpoint_workflow_run(
        workflow,
        next_run.workflowRunId,
        progress={
            "phase": "public_forward_observation",
            "cycleStatus": cycle.status,
            "closedOutcomeCount": cycle.closedOutcomeCount,
        },
        result=cycle_result,
        actor="worker",
    )
