"""Freeze a replay-qualified strategy candidate for local forward observation."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import ForwardReleaseRecord, StrategyCandidateRecord

from .types import ForwardRiskEnvelope


def create_forward_release(
    candidate: StrategyCandidateRecord,
    *,
    replay_report: dict[str, Any],
    repository: RegistryRepository,
    code_commit: str,
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
    envelope = ForwardRiskEnvelope()
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
        "environment": "local_forward_public_market_only",
        "virtualAccountOnly": True,
        "createsOrders": False,
        "demoExecutionAllowed": False,
        "liveExecutionAllowed": False,
    }
    risk_envelope = envelope.to_dict()
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
