"""Freeze a replay-qualified strategy candidate for local forward observation."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    ForwardReleaseRecord,
    RiskProfileRecord,
    StrategyCandidateRecord,
)
from alphapilot.evolution.risk_profiles import execution_envelope, register_default_risk_profiles
from alphapilot.evolution.workflow.types import (
    EvaluationBindingRecord,
    StrategyVersionRecord,
)

from .types import ForwardRiskEnvelope


def create_forward_release(
    candidate: StrategyCandidateRecord,
    *,
    replay_report: dict[str, Any],
    repository: RegistryRepository,
    code_commit: str,
    risk_profile: RiskProfileRecord | None = None,
) -> ForwardReleaseRecord:
    """Create an immutable release only from formal, candidate-bound replay evidence."""

    registered = repository.get_strategy_candidate(candidate.strategyCandidateId)
    if registered is None or registered.contentHash != candidate.contentHash:
        raise ValueError("Forward release requires the registered immutable candidate")
    if not code_commit.strip():
        raise ValueError("Forward release requires a code commit")
    if replay_report.get("engineProbeOnly") is not False:
        raise ValueError("Engine probe evidence cannot create a forward release")
    if replay_report.get("evidenceClass") != "historical_path_replay":
        raise ValueError("Forward release requires formal historical path replay evidence")
    if replay_report.get("strategyCandidateId") != candidate.strategyCandidateId:
        raise ValueError("Replay evidence is not bound to this strategy candidate")
    if int(replay_report.get("formalStrategyReplayCount", 0)) < 1:
        raise ValueError("Forward release requires at least one formal strategy replay")
    outcome_ledger = replay_report.get("outcomeLedger")
    if not isinstance(outcome_ledger, dict) or not outcome_ledger.get("artifactSha256"):
        raise ValueError("Forward release requires a hashed replay outcome manifest")
    instruments = replay_report.get("eligibleInstruments")
    if not isinstance(instruments, list) or not instruments:
        raise ValueError("Forward release requires replay-verified eligible instruments")
    signal_policy = candidate.candidate.get("forwardSignalPolicy")
    if not isinstance(signal_policy, dict) or not signal_policy.get("rules"):
        raise ValueError("Candidate is missing a frozen forward signal policy")
    market_definition = candidate.candidate.get("marketDefinition")
    evidence = candidate.candidate.get("evidence")
    if not isinstance(market_definition, dict) or not isinstance(evidence, dict):
        raise ValueError("Candidate market definition or evidence is incomplete")
    data_snapshot_id = evidence.get("dataSnapshotId")
    if not data_snapshot_id or repository.get_data_snapshot(str(data_snapshot_id)) is None:
        raise ValueError("Forward release training snapshot is not registered")
    profile = risk_profile or register_default_risk_profiles(repository)["local_forward"]
    registered_profile = repository.get_risk_profile(profile.riskProfileId)
    if registered_profile is None or registered_profile.contentHash != profile.contentHash:
        raise ValueError("Forward release requires a registered immutable RiskProfile")
    if profile.environment != "local_forward":
        raise ValueError("Forward release requires a local_forward RiskProfile")
    envelope = ForwardRiskEnvelope(
        initialEquityUsdt=float(profile.profile["capitalLimitUsdt"]),
        riskPerTradePercent=float(profile.profile["riskPerTradePercent"]),
        maxOpenRiskPercent=float(profile.profile["maxOpenRiskPercent"]),
        maxOrderNotionalUsdt=float(profile.profile["maxOrderNotionalUsdt"]),
        maxConcurrentPositions=int(profile.profile["maxConcurrentPositions"]),
        feeRate=float(profile.profile["feeRate"]),
        slippageRate=float(profile.profile["slippageRate"]),
        rewardRiskRatio=float(profile.profile["rewardRiskRatio"]),
    )
    envelope.validate()
    release_payload = {
        "schemaVersion": "local_forward_release_v1",
        "strategyCandidateId": candidate.strategyCandidateId,
        "strategyCandidateHash": candidate.contentHash,
        "trainingDataSnapshotId": str(data_snapshot_id),
        "marketDefinition": {
            **market_definition,
            "eligibleInstruments": sorted({str(item).upper() for item in instruments}),
        },
        "signalPolicy": signal_policy,
        "exitRules": candidate.candidate.get("exitRules", {}),
        "riskRules": candidate.candidate.get("riskRules", {}),
        "replayEvidence": {
            "reportId": replay_report.get("reportId"),
            "codeCommit": replay_report.get("codeCommit"),
            "outcomeArtifactSha256": outcome_ledger["artifactSha256"],
            "closedReplayCount": int(replay_report.get("formalStrategyReplayCount", 0)),
        },
        "codeCommit": code_commit,
        "riskProfileId": profile.riskProfileId,
        "riskProfileHash": profile.contentHash,
        "environment": "local_forward_public_market_only",
        "virtualAccountOnly": True,
        "createsOrders": False,
        "demoExecutionAllowed": False,
        "liveExecutionAllowed": False,
    }
    risk_envelope = {**execution_envelope(profile), **envelope.to_dict()}
    content_hash = stable_hash({"release": release_payload, "riskEnvelope": risk_envelope})
    return repository.create_forward_release(
        ForwardReleaseRecord(
            forwardReleaseId=stable_hash(content_hash, prefix="forward_release"),
            strategyCandidateId=candidate.strategyCandidateId,
            status="forward_eligible",
            riskEnvelope=risk_envelope,
            release=release_payload,
            contentHash=content_hash,
        )
    )


def create_workflow_forward_release(
    *,
    strategy_version: StrategyVersionRecord,
    strategy_candidate: StrategyCandidateRecord,
    evaluation_binding: EvaluationBindingRecord,
    backtest_result: dict[str, Any],
    repository: RegistryRepository,
    code_commit: str,
    risk_profile: RiskProfileRecord | None = None,
) -> ForwardReleaseRecord:
    """Freeze a formal workflow pass for virtual public-market observation."""

    if backtest_result.get("status") != "passed":
        raise ValueError("Formal passed backtest evidence is required")
    if evaluation_binding.evidence.get("evidenceClass") != "formal_backtest":
        raise ValueError("Formal workflow evidence is required")
    if float(strategy_version.definition.get("targetR", 0.0)) < 2.0:
        raise ValueError("Forward release requires targetR >= 2")
    if not code_commit.strip():
        raise ValueError("Forward release requires a code commit")
    registered = repository.get_strategy_candidate(
        strategy_candidate.strategyCandidateId
    )
    if registered is None or registered.contentHash != strategy_candidate.contentHash:
        raise ValueError("Forward release requires the registered immutable candidate")
    candidate = strategy_candidate.candidate
    if candidate.get("strategyVersionId") != strategy_version.strategyVersionId:
        raise ValueError("Forward candidate strategy version hash mismatch")
    if candidate.get("strategyContentHash") != strategy_version.contentHash:
        raise ValueError("Forward candidate strategy content hash mismatch")
    signal_policy = candidate.get("forwardSignalPolicy")
    if not isinstance(signal_policy, dict) or not signal_policy.get("rules"):
        raise ValueError("Candidate is missing a frozen forward signal policy")
    market_definition = candidate.get("marketDefinition")
    if (
        not isinstance(market_definition, dict)
        or market_definition.get("publicOnly") is not True
        or market_definition.get("marketDataAccess") != "public"
    ):
        raise ValueError("Forward release requires public-only market data")
    instruments = market_definition.get("eligibleInstruments")
    if not isinstance(instruments, list) or not instruments:
        raise ValueError("Forward release requires formal eligible instruments")
    evidence = backtest_result.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("Formal backtest evidence is incomplete")
    expected_hashes = {
        "evaluationBindingId": evaluation_binding.evaluationBindingId,
        "dataSnapshotId": evaluation_binding.dataSnapshotId,
        "walkForwardManifestHash": evaluation_binding.walkForwardManifestHash,
        "holdoutManifestHash": evaluation_binding.holdoutManifestHash,
        "lockedOosManifestHash": evaluation_binding.lockedOosManifestHash,
        "regimeManifestHash": evaluation_binding.evidence.get(
            "regimeManifestHash"
        ),
        "costManifestHash": evaluation_binding.evidence.get("costManifestHash"),
    }
    mismatches = [
        key for key, value in expected_hashes.items() if evidence.get(key) != value
    ]
    if mismatches:
        raise ValueError(
            f"Formal evidence hash mismatch: {', '.join(sorted(mismatches))}"
        )
    snapshot = repository.get_data_snapshot(evaluation_binding.dataSnapshotId)
    if snapshot is None:
        raise ValueError("Forward release snapshot is not registered")
    profile = risk_profile or register_default_risk_profiles(repository)[
        "local_forward"
    ]
    registered_profile = repository.get_risk_profile(profile.riskProfileId)
    if registered_profile is None or registered_profile.contentHash != profile.contentHash:
        raise ValueError("Forward release requires a registered immutable RiskProfile")
    if profile.environment != "local_forward":
        raise ValueError("Forward release requires a local_forward RiskProfile")
    envelope = ForwardRiskEnvelope(
        initialEquityUsdt=float(profile.profile["capitalLimitUsdt"]),
        riskPerTradePercent=float(profile.profile["riskPerTradePercent"]),
        maxOpenRiskPercent=float(profile.profile["maxOpenRiskPercent"]),
        maxOrderNotionalUsdt=float(profile.profile["maxOrderNotionalUsdt"]),
        maxConcurrentPositions=int(profile.profile["maxConcurrentPositions"]),
        feeRate=float(profile.profile["feeRate"]),
        slippageRate=float(profile.profile["slippageRate"]),
        rewardRiskRatio=float(profile.profile["rewardRiskRatio"]),
    )
    envelope.validate()
    release_payload = {
        "schemaVersion": "workflow_local_forward_release_v1",
        "strategyVersionId": strategy_version.strategyVersionId,
        "strategyContentHash": strategy_version.contentHash,
        "strategyCandidateId": strategy_candidate.strategyCandidateId,
        "strategyCandidateHash": strategy_candidate.contentHash,
        "evaluationBindingId": evaluation_binding.evaluationBindingId,
        "trainingDataSnapshotId": evaluation_binding.dataSnapshotId,
        "marketDefinition": market_definition,
        "signalPolicy": signal_policy,
        "exitRules": candidate["exitRules"],
        "riskRules": candidate["riskRules"],
        "formalEvidence": expected_hashes,
        "codeCommit": code_commit,
        "riskProfileId": profile.riskProfileId,
        "riskProfileHash": profile.contentHash,
        "environment": "local_forward_public_market_only",
        "virtualAccountOnly": True,
        "createsOrders": False,
        "demoExecutionAllowed": False,
        "liveExecutionAllowed": False,
    }
    risk_envelope = {**execution_envelope(profile), **envelope.to_dict()}
    content_hash = stable_hash(
        {"release": release_payload, "riskEnvelope": risk_envelope}
    )
    return repository.create_forward_release(
        ForwardReleaseRecord(
            forwardReleaseId=stable_hash(content_hash, prefix="forward_release"),
            strategyCandidateId=strategy_candidate.strategyCandidateId,
            status="forward_eligible",
            riskEnvelope=risk_envelope,
            release=release_payload,
            contentHash=content_hash,
        )
    )
