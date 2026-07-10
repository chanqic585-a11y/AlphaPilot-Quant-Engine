"""Create immutable Demo-only releases after every promotion gate passes."""

from __future__ import annotations

from dataclasses import dataclass

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    DemoReleaseRecord,
    PromotionDecisionRecord,
    StrategyCandidateRecord,
)

from .gate import PromotionGateResult


DEFAULT_DEMO_RISK_ENVELOPE = {
    "schemaVersion": "demo_risk_envelope_v1",
    "initialEquityUsdt": 1000.0,
    "riskPerTradePercent": 0.25,
    "maxOpenRiskPercent": 1.0,
    "maxOrderNotionalUsdt": 250.0,
    "maxConcurrentPositions": 3,
    "defaultMaxLeverage": 2,
    "hardMaxLeverage": 5,
    "dailyLossStopPercent": 2.0,
    "demoDrawdownPausePercent": 5.0,
}


@dataclass(frozen=True)
class DemoPromotionOutcome:
    promotionDecision: PromotionDecisionRecord
    demoRelease: DemoReleaseRecord | None


def _required_text(value: str, field_name: str) -> str:
    cleaned = str(value or "").strip()
    if not cleaned:
        raise ValueError(f"{field_name} is required for an immutable Demo release")
    return cleaned


def promote_candidate_to_demo(
    *,
    candidate: StrategyCandidateRecord,
    gateResult: PromotionGateResult,
    repository: RegistryRepository,
    codeCommit: str,
    dataChecksum: str,
    modelChecksum: str,
) -> DemoPromotionOutcome:
    code_commit = _required_text(codeCommit, "codeCommit")
    data_checksum = _required_text(dataChecksum, "dataChecksum")
    model_checksum = _required_text(modelChecksum, "modelChecksum")
    if repository.get_strategy_candidate(candidate.strategyCandidateId) is None:
        raise ValueError("Strategy candidate must be registered before promotion")

    decision_evidence = {
        "candidateContentHash": candidate.contentHash,
        "gate": gateResult.as_dict(),
        "checksums": {
            "codeCommit": code_commit,
            "data": data_checksum,
            "model": model_checksum,
        },
    }
    reasons = ["all_demo_hard_gates_passed"] if gateResult.passed else list(gateResult.failedCheckIds)
    decision_payload = {
        "strategyCandidateId": candidate.strategyCandidateId,
        "fromStatus": gateResult.sourceStatus,
        "toStatus": gateResult.targetStatus,
        "passed": gateResult.passed,
        "reasons": reasons,
        "evidence": decision_evidence,
    }
    decision_hash = stable_hash(decision_payload)
    decision = repository.create_promotion_decision(
        PromotionDecisionRecord(
            promotionDecisionId=stable_hash(decision_payload, prefix="promotion_decision"),
            strategyCandidateId=candidate.strategyCandidateId,
            fromStatus=gateResult.sourceStatus,
            toStatus=gateResult.targetStatus,
            passed=gateResult.passed,
            reasons=reasons,
            evidence=decision_evidence,
            contentHash=decision_hash,
        )
    )
    if not gateResult.passed:
        return DemoPromotionOutcome(promotionDecision=decision, demoRelease=None)

    release_payload = {
        "schemaVersion": "demo_release_contract_v1",
        "promotionDecisionId": decision.promotionDecisionId,
        "strategyCandidateId": candidate.strategyCandidateId,
        "strategyCandidateHash": candidate.contentHash,
        "strategy": candidate.candidate,
        "checksums": decision_evidence["checksums"],
        "gateEvidenceHash": stable_hash(gateResult.as_dict()),
        "executionEnvironment": "okx_demo_only",
        "automaticDemoExecutionAllowed": True,
        "liveExecutionAllowed": False,
        "withdrawAllowed": False,
        "immutable": True,
    }
    release_hash = stable_hash(
        {"release": release_payload, "riskEnvelope": DEFAULT_DEMO_RISK_ENVELOPE}
    )
    release = repository.create_demo_release(
        DemoReleaseRecord(
            demoReleaseId=stable_hash(release_hash, prefix="demo_release"),
            strategyCandidateId=candidate.strategyCandidateId,
            status="demo_eligible",
            riskEnvelope=dict(DEFAULT_DEMO_RISK_ENVELOPE),
            release=release_payload,
            contentHash=release_hash,
        )
    )
    return DemoPromotionOutcome(promotionDecision=decision, demoRelease=release)
