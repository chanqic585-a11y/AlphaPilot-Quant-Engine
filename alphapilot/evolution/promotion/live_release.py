"""Create checksum-bound Live releases after one explicit manual approval."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    LiveCandidatePackageRecord,
    LiveReleaseRecord,
    RiskProfileRecord,
)


class LiveReleaseNotEligible(RuntimeError):
    """Raised when a Live candidate has not completed the release gate."""


@dataclass(frozen=True)
class ManualLiveApprovalEvidence:
    liveCandidatePackageId: str
    packageHash: str
    riskProfileId: str
    riskProfileHash: str
    actor: str
    approvedAt: str
    confirmationHash: str


def build_live_release(
    *,
    package: LiveCandidatePackageRecord,
    riskProfile: RiskProfileRecord,
    approval: ManualLiveApprovalEvidence,
    repository: RegistryRepository,
) -> LiveReleaseRecord:
    registered_package = repository.get_live_candidate_package(package.liveCandidatePackageId)
    if registered_package is None or registered_package.contentHash != package.contentHash:
        raise LiveReleaseNotEligible("Live candidate package is missing or checksum-mismatched")
    if package.status != "awaiting_manual_approval":
        raise LiveReleaseNotEligible("Live candidate package is not awaiting approval")
    registered_profile = repository.get_risk_profile(riskProfile.riskProfileId)
    if registered_profile is None or registered_profile.contentHash != riskProfile.contentHash:
        raise LiveReleaseNotEligible("Live RiskProfile is missing or checksum-mismatched")
    if riskProfile.environment != "live_canary":
        raise LiveReleaseNotEligible("The first Live release must use a live_canary RiskProfile")
    active_profile = repository.get_active_risk_profile("live_canary")
    if active_profile is None or active_profile.riskProfileId != riskProfile.riskProfileId:
        raise LiveReleaseNotEligible("Live Canary RiskProfile is not active")

    package_payload = package.package
    expected = {
        "liveCandidatePackageId": package.liveCandidatePackageId,
        "packageHash": package.contentHash,
        "riskProfileId": riskProfile.riskProfileId,
        "riskProfileHash": riskProfile.contentHash,
    }
    for key, value in expected.items():
        if str(getattr(approval, key)) != str(value):
            raise LiveReleaseNotEligible(f"Manual approval does not match {key}")
    if approval.actor != "user_manual" or not approval.approvedAt.strip():
        raise LiveReleaseNotEligible("Live release requires a timestamped user_manual approval")
    if len(approval.confirmationHash.strip()) != 64:
        raise LiveReleaseNotEligible("Live approval confirmation hash is invalid")
    if package_payload.get("riskProfileId") != riskProfile.riskProfileId:
        raise LiveReleaseNotEligible("Package RiskProfile id mismatch")
    if package_payload.get("riskProfileHash") != riskProfile.contentHash:
        raise LiveReleaseNotEligible("Package RiskProfile checksum mismatch")
    if float(riskProfile.profile.get("rewardRiskRatio") or 0) < 2.0:
        raise LiveReleaseNotEligible("Live RiskProfile reward/risk must remain at least 2R")

    approval_payload = asdict(approval)
    release_payload: dict[str, Any] = {
        "schemaVersion": "live_release_contract_v1",
        "liveCandidatePackageId": package.liveCandidatePackageId,
        "liveCandidatePackageHash": package.contentHash,
        "demoReleaseId": package.demoReleaseId,
        "strategyCandidateId": str(package_payload.get("strategyCandidateId") or ""),
        "strategy": package_payload.get("strategy", {}),
        "lineageChecksums": package_payload.get("lineageChecksums", {}),
        "riskProfileId": riskProfile.riskProfileId,
        "riskProfileHash": riskProfile.contentHash,
        "riskProfile": riskProfile.profile,
        "manualApproval": approval_payload,
        "manualApprovalHash": stable_hash(approval_payload),
        "rollbackPolicy": package_payload.get("rollbackPolicy", {}),
        "protectionPolicy": {
            "attachedTakeProfitRequired": True,
            "attachedStopLossRequired": True,
            "minimumRewardRiskRatio": 2.0,
            "privateStateReconciliationRequired": True,
            "restartRecoveryRequired": True,
            "unknownStatePausesEntries": True,
            "killSwitchRequired": True,
        },
        "executionBoundary": {
            "environment": "okx_live_canary_only",
            "manualReleaseApprovalRequired": True,
            "automaticPerOrderConfirmationRequired": False,
            "mechanicalExecutionAllowed": True,
            "withdrawAllowed": False,
            "rawCredentialStorageAllowed": False,
        },
    }
    content_hash = stable_hash(release_payload)
    return repository.create_live_release(
        LiveReleaseRecord(
            liveReleaseId=stable_hash(release_payload, prefix="live_release"),
            liveCandidatePackageId=package.liveCandidatePackageId,
            strategyCandidateId=release_payload["strategyCandidateId"],
            status="live_canary_approved",
            riskProfileId=riskProfile.riskProfileId,
            release=release_payload,
            contentHash=content_hash,
        )
    )


def export_live_release(record: LiveReleaseRecord) -> dict[str, Any]:
    return {
        "schemaVersion": "alphapilot_live_release_v1",
        "liveReleaseId": record.liveReleaseId,
        "liveReleaseHash": record.contentHash,
        "status": record.status,
        "createdAt": record.createdAt,
        "release": record.release,
        "executionBoundary": {
            "liveCanaryOnly": True,
            "runtimeGatesStillRequired": True,
            "withdrawAllowed": False,
            "rawCredentialStorageAllowed": False,
        },
    }
