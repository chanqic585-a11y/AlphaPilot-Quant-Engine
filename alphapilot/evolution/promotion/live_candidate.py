"""Build immutable Live candidates without creating or enabling a live adapter."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import DemoReleaseRecord, LiveCandidatePackageRecord


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
    capitalLimitUsdt: float = 1000.0
    riskPerTradePercent: float = 0.25
    maxOpenRiskPercent: float = 1.0
    maxOrderNotionalUsdt: float = 250.0
    maxConcurrentPositions: int = 3
    maxLeverage: int = 2
    dailyLossStopPercent: float = 2.0
    maxDrawdownStopPercent: float = 5.0

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


def _validate_risk_budget(risk: LiveRiskBudgetProposal) -> None:
    values = asdict(risk)
    if not all(math.isfinite(float(value)) and float(value) > 0 for value in values.values()):
        raise ValueError("Live risk budget values must be finite and positive")
    if risk.capitalLimitUsdt > 1000 or risk.riskPerTradePercent > 0.25:
        raise ValueError("Proposed Live capital or per-trade risk exceeds the reviewed boundary")
    if risk.maxOpenRiskPercent > 1.0 or risk.maxOrderNotionalUsdt > 250:
        raise ValueError("Proposed Live open risk or order notional exceeds the reviewed boundary")
    if risk.maxConcurrentPositions > 3 or risk.maxLeverage > 2:
        raise ValueError("Proposed Live concurrency or leverage exceeds the reviewed boundary")
    if risk.dailyLossStopPercent > 2.0 or risk.maxDrawdownStopPercent > 5.0:
        raise ValueError("Proposed Live loss limits exceed the reviewed boundary")


def build_live_candidate_package(
    *,
    demoRelease: DemoReleaseRecord,
    demoEvidence: DemoValidationEvidence,
    proposedRiskBudget: LiveRiskBudgetProposal,
    rollbackTargetReleaseId: str,
    repository: RegistryRepository,
) -> LiveCandidatePackageRecord:
    registered = repository.get_demo_release(demoRelease.demoReleaseId)
    if registered is None or registered.contentHash != demoRelease.contentHash:
        raise LiveCandidateNotEligible("Demo release is missing or checksum-mismatched")
    if demoRelease.status not in {"demo_validated", "demo_completed"}:
        raise LiveCandidateNotEligible("Demo release has not completed validation")
    failed = _validate_demo_evidence(demoEvidence)
    if failed:
        raise LiveCandidateNotEligible("Demo validation failed: " + ",".join(failed))
    _validate_risk_budget(proposedRiskBudget)
    rollback_target = str(rollbackTargetReleaseId or "").strip()
    if not rollback_target:
        raise ValueError("A reviewed Demo rollback target is required")
    checksums = demoRelease.release.get("checksums") if isinstance(demoRelease.release.get("checksums"), dict) else {}
    required_checksums = ("codeCommit", "data", "model")
    if any(not str(checksums.get(key) or "").strip() for key in required_checksums):
        raise LiveCandidateNotEligible("Demo release lineage checksums are incomplete")

    risk_budget = {**asdict(proposedRiskBudget), "maximumLossUsdt": proposedRiskBudget.maximumLossUsdt}
    payload = {
        "schemaVersion": "live_candidate_package_v1",
        "demoReleaseId": demoRelease.demoReleaseId,
        "demoReleaseHash": demoRelease.contentHash,
        "strategyCandidateId": demoRelease.strategyCandidateId,
        "strategy": demoRelease.release.get("strategy", {}),
        "lineageChecksums": checksums,
        "demoEvidence": asdict(demoEvidence),
        "proposedRiskBudget": risk_budget,
        "rollbackPolicy": {
            "targetDemoReleaseId": rollback_target,
            "stopNewEntriesFirst": True,
            "killSwitchRequired": True,
        },
        "manualApprovalRequired": True,
        "automaticApprovalAllowed": False,
        "liveExecutionAdapterPresent": False,
        "liveExecutionEnabled": False,
        "withdrawAllowed": False,
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
