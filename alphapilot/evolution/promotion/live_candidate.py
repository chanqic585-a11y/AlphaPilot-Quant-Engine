"""Build immutable Live candidates without creating or enabling a live adapter."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    DemoReleaseRecord,
    LiveCandidatePackageRecord,
    RiskProfileRecord,
)
from alphapilot.evolution.risk_profiles import (
    RiskProfileSpec,
    build_risk_profile_record,
    execution_envelope,
    validate_profile,
)


class LiveCandidateNotEligible(RuntimeError):
    """Raised when Demo evidence cannot support a manual Live review package."""


@dataclass(frozen=True)
class DemoValidationEvidence:
    demoClosedTrades: int
    demoCalendarDays: int
    netProfitFactor: float
    maxDrawdownPercent: float
    feeCostUsdt: float
    slippageCostUsdt: float
    unresolvedCriticalDriftEvents: int
    ledgerMatched: bool
    checksumsMatch: bool
    symbolStabilityPassed: bool
    regimeStabilityPassed: bool
    timeStabilityPassed: bool
    outcomeSampleManifestHash: str


@dataclass(frozen=True)
class LiveRiskBudgetProposal:
    profileKey: str = "live_canary_custom"
    profileVersion: int = 1
    profileName: str = "Live Canary Custom"
    capitalLimitUsdt: float = 1000.0
    maxActiveStrategies: int = 1
    riskPerTradePercent: float = 0.25
    maxOpenRiskPercent: float = 1.0
    maxStrategyOpenRiskPercent: float = 1.0
    maxSymbolOpenRiskPercent: float = 0.5
    maxDirectionOpenRiskPercent: float = 1.0
    maxCorrelatedOpenRiskPercent: float = 1.0
    maxOrderNotionalUsdt: float = 250.0
    maxConcurrentPositions: int = 3
    maxPositionsPerStrategy: int = 2
    maxPositionsPerSymbol: int = 1
    maxLeverage: int = 2
    marginMode: str = "isolated"
    dailyLossStopPercent: float = 2.0
    maxDrawdownStopPercent: float = 5.0
    canaryLossStopUsdt: float = 25.0
    cooldownAfterLossMinutes: int = 60
    rewardRiskRatio: float = 2.0
    feeRate: float = 0.0005
    slippageRate: float = 0.0002
    allowNewEntries: bool = True

    @property
    def maximumLossUsdt(self) -> float:
        return self.capitalLimitUsdt * self.maxDrawdownStopPercent / 100.0


def _validate_demo_evidence(evidence: DemoValidationEvidence) -> list[str]:
    numbers = (
        evidence.netProfitFactor,
        evidence.maxDrawdownPercent,
        evidence.feeCostUsdt,
        evidence.slippageCostUsdt,
    )
    if not all(math.isfinite(float(value)) for value in numbers):
        raise ValueError("Demo validation contains non-finite values")
    checks = {
        "demo_closed_trades": evidence.demoClosedTrades >= 50,
        "demo_calendar_days": evidence.demoCalendarDays >= 30,
        "demo_profit_factor": evidence.netProfitFactor >= 1.15,
        "demo_drawdown": 0 <= evidence.maxDrawdownPercent < 5.0,
        "critical_drift_resolved": evidence.unresolvedCriticalDriftEvents == 0,
        "ledger_matched": evidence.ledgerMatched,
        "checksums_match": evidence.checksumsMatch,
        "symbol_stability": evidence.symbolStabilityPassed,
        "regime_stability": evidence.regimeStabilityPassed,
        "time_stability": evidence.timeStabilityPassed,
        "outcome_manifest": str(evidence.outcomeSampleManifestHash).startswith("demo_outcomes_"),
    }
    return [name for name, passed in checks.items() if not passed]


def _profile_from_proposal(risk: LiveRiskBudgetProposal) -> RiskProfileRecord:
    spec = RiskProfileSpec(
        profileKey=risk.profileKey,
        version=risk.profileVersion,
        environment="live_canary",
        name=risk.profileName,
        capitalLimitUsdt=risk.capitalLimitUsdt,
        maxActiveStrategies=risk.maxActiveStrategies,
        maxConcurrentPositions=risk.maxConcurrentPositions,
        maxPositionsPerStrategy=risk.maxPositionsPerStrategy,
        maxPositionsPerSymbol=risk.maxPositionsPerSymbol,
        maxOrderNotionalUsdt=risk.maxOrderNotionalUsdt,
        maxLeverage=risk.maxLeverage,
        marginMode=risk.marginMode,
        riskPerTradePercent=risk.riskPerTradePercent,
        maxOpenRiskPercent=risk.maxOpenRiskPercent,
        maxStrategyOpenRiskPercent=risk.maxStrategyOpenRiskPercent,
        maxSymbolOpenRiskPercent=risk.maxSymbolOpenRiskPercent,
        maxDirectionOpenRiskPercent=risk.maxDirectionOpenRiskPercent,
        maxCorrelatedOpenRiskPercent=risk.maxCorrelatedOpenRiskPercent,
        dailyLossStopPercent=risk.dailyLossStopPercent,
        maxDrawdownStopPercent=risk.maxDrawdownStopPercent,
        canaryLossStopUsdt=risk.canaryLossStopUsdt,
        cooldownAfterLossMinutes=risk.cooldownAfterLossMinutes,
        rewardRiskRatio=risk.rewardRiskRatio,
        feeRate=risk.feeRate,
        slippageRate=risk.slippageRate,
        allowNewEntries=risk.allowNewEntries,
    )
    validate_profile(spec)
    return build_risk_profile_record(spec, status="awaiting_live_review")


def build_live_candidate_package(
    *,
    demoRelease: DemoReleaseRecord,
    demoEvidence: DemoValidationEvidence,
    proposedRiskBudget: LiveRiskBudgetProposal | None,
    rollbackTargetReleaseId: str,
    repository: RegistryRepository,
    riskProfile: RiskProfileRecord | None = None,
) -> LiveCandidatePackageRecord:
    registered = repository.get_demo_release(demoRelease.demoReleaseId)
    if registered is None or registered.contentHash != demoRelease.contentHash:
        raise LiveCandidateNotEligible("Demo release is missing or checksum-mismatched")
    if demoRelease.status not in {"demo_validated", "demo_completed"}:
        raise LiveCandidateNotEligible("Demo release has not completed validation")
    failed = _validate_demo_evidence(demoEvidence)
    if failed:
        raise LiveCandidateNotEligible("Demo validation failed: " + ",".join(failed))
    if proposedRiskBudget is None and riskProfile is None:
        raise ValueError("A versioned Live RiskProfile is required")
    profile = riskProfile or _profile_from_proposal(proposedRiskBudget or LiveRiskBudgetProposal())
    if not profile.environment.startswith("live_"):
        raise ValueError("Live candidate requires a Live RiskProfile")
    registered_profile = repository.create_risk_profile(profile)
    if registered_profile.contentHash != profile.contentHash:
        raise ValueError("Registered Live RiskProfile checksum mismatch")
    rollback_target = str(rollbackTargetReleaseId or "").strip()
    if not rollback_target:
        raise ValueError("A reviewed Demo rollback target is required")
    checksums = demoRelease.release.get("checksums") if isinstance(demoRelease.release.get("checksums"), dict) else {}
    required_checksums = ("codeCommit", "data", "model")
    if any(not str(checksums.get(key) or "").strip() for key in required_checksums):
        raise LiveCandidateNotEligible("Demo release lineage checksums are incomplete")

    risk_budget = {
        **execution_envelope(profile),
        "maximumLossUsdt": float(profile.profile["capitalLimitUsdt"])
        * float(profile.profile["maxDrawdownStopPercent"])
        / 100.0,
    }
    evidence_payload = asdict(demoEvidence)
    payload = {
        "schemaVersion": "live_candidate_package_v2",
        "demoReleaseId": demoRelease.demoReleaseId,
        "demoReleaseHash": demoRelease.contentHash,
        "riskProfileId": profile.riskProfileId,
        "riskProfileHash": profile.contentHash,
        "strategyCandidateId": demoRelease.strategyCandidateId,
        "strategy": demoRelease.release.get("strategy", {}),
        "lineageChecksums": checksums,
        "demoEvidence": evidence_payload,
        "demoEvidenceHash": stable_hash(evidence_payload),
        "proposedRiskBudget": risk_budget,
        "proposedRiskBudgetHash": stable_hash(risk_budget),
        "rollbackPolicy": {
            "targetDemoReleaseId": rollback_target,
            "stopNewEntriesFirst": True,
            "killSwitchRequired": True,
        },
        "manualApprovalRequired": True,
        "automaticApprovalAllowed": False,
        "liveReleaseExecutionApprovalImplemented": False,
        "liveExecutionAdapterPresent": False,
        "liveExecutionEnabled": False,
        "withdrawAllowed": False,
        "safetyPolicy": {
            "requestExpirySeconds": 30,
            "idempotencyRequired": True,
            "instrumentStateRequired": "live",
            "maximumReferencePriceDeviationPercent": 1.0,
            "privateStateReconciliationRequired": True,
            "restartRecoveryRequired": True,
            "circuitBreakerRequired": True,
            "killSwitchRequired": True,
            "approvalEnablesExecution": False,
        },
    }
    content_hash = stable_hash(payload)
    return repository.create_live_candidate_package(
        LiveCandidatePackageRecord(
            liveCandidatePackageId=stable_hash(payload, prefix="live_candidate_package"),
            demoReleaseId=demoRelease.demoReleaseId,
            status="awaiting_manual_approval",
            package=payload,
            contentHash=content_hash,
        )
    )
