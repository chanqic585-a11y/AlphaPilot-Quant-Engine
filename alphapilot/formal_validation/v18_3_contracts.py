"""Immutable contracts for V18.3 fold and ranking evidence closure."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .v18_2_contracts import verify_v18_2_preregistration


V18_2_CAMPAIGN_ID = (
    "advisory_r_v18_2_s01_formal_evidence_chain_correction_e100fc1eafa9abd0"
)
V18_2_CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"
V18_2_PREREGISTRATION_PATH = (
    Path("research/preregistrations") / f"{V18_2_CAMPAIGN_ID}.json"
)
V18_2_RESULT_ROOT = (
    Path("reports/formal_validation") / V18_2_CAMPAIGN_ID / V18_2_CANDIDATE_ID
)
V18_3_CAMPAIGN_PREFIX = (
    "advisory_r_v18_3_s01_fold_ranking_evidence_correction_"
)
V18_3_PREREGISTRATION_HASH_PREFIX = (
    "s01_v18_3_fold_ranking_evidence_correction_preregistration"
)
V18_3_TAG = "v13.27.1.18.3"
CORRECTION_REASON = (
    "formal_event_disposition_and_frozen_ranking_evidence_record_incomplete"
)
V18_2_FROZEN_CONTRACT_HASHES_HASH = (
    "v18_2_frozen_contract_hashes_"
    "f0eecb5ebe81e5e39350921c2e5cd65618ead89a851f6c4e96a117d69b51e903"
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _write_json_once(
    path: Path, payload: Mapping[str, Any], *, conflict_code: str
) -> None:
    expected = dict(payload)
    if path.exists():
        if _read_json(path) != expected:
            raise RuntimeError(conflict_code)
        return
    write_json_atomic(path, expected)


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _next_strict_four_hour_boundary(value: str) -> str:
    parsed = _parse_utc(value)
    floor = parsed.replace(
        hour=(parsed.hour // 4) * 4,
        minute=0,
        second=0,
        microsecond=0,
    )
    return _utc_iso(floor + timedelta(hours=4))


def _campaign_id(
    *, predecessor_campaign_id: str, implementation_commit: str, certification_hash: str
) -> str:
    digest = stable_hash(
        {
            "correctionOfCampaignId": predecessor_campaign_id,
            "correctionReason": CORRECTION_REASON,
            "correctionImplementationCommit": implementation_commit,
            "signalEvidenceStructuralCertificationHash": certification_hash,
        }
    )
    return f"{V18_3_CAMPAIGN_PREFIX}{digest[:16]}"


def _certification_fields(certification: Mapping[str, Any]) -> dict[str, Any]:
    disposition = certification.get("eventDispositionAudit")
    ranking = certification.get("rankingEvidenceAudit")
    access = certification.get("accessAudit")
    if not isinstance(disposition, Mapping):
        raise ValueError("Structural certification lacks disposition evidence")
    if not isinstance(ranking, Mapping):
        raise ValueError("Structural certification lacks ranking evidence")
    if not isinstance(access, Mapping):
        raise ValueError("Structural certification lacks access evidence")
    return {
        "signalEvidenceStructuralCertificationStatus": certification.get("status"),
        "signalEvidenceStructuralCertificationHash": certification.get(
            "signalEvidenceStructuralCertificationHash"
        ),
        "formalEventDispositionContractHash": certification.get(
            "dispositionContractHash"
        ),
        "frozenRankingEvidenceRecordContractHash": certification.get(
            "rankingEvidenceContractHash"
        ),
        "formalEventDispositionConservationPassed": bool(
            disposition.get("rawEqualsAssignedPlusExcluded")
            and int(disposition.get("unclassifiedEventCount", -1)) == 0
            and int(disposition.get("multiAssignedEventCount", -1)) == 0
            and int(disposition.get("duplicateDispositionCount", -1)) == 0
            and int(disposition.get("unknownDispositionCount", -1)) == 0
            and int(disposition.get("crossBoundaryLeakageCount", -1)) == 0
        ),
        "rawEventCount": int(certification.get("rawEventCount", 0)),
        "assignedValidationEventCount": int(
            certification.get("assignedValidationEventCount", 0)
        ),
        "explicitlyExcludedEventCount": int(
            certification.get("explicitlyExcludedEventCount", 0)
        ),
        "rankingEvidenceRecordCount": int(
            certification.get("rankingEvidenceRecordCount", 0)
        ),
        "rankingEvidenceRecordMissingCount": int(
            certification.get("rankingEvidenceRecordMissingCount", -1)
        ),
        "rankingEvidenceStatusMissingCount": int(
            certification.get("rankingEvidenceStatusMissingCount", -1)
        ),
        "rankingEvidenceRecordCoveragePercent": float(
            certification.get("rankingEvidenceRecordCoveragePct", 0.0)
        ),
        "rankingEvidenceStatusCoveragePercent": float(
            certification.get("rankingEvidenceStatusCoveragePct", 0.0)
        ),
        "rankingEvidenceParityPercent": float(
            certification.get("rankingEvidenceParityPct", 0.0)
        ),
        "rankingEvidenceUnavailableCount": int(
            certification.get("rankingEvidenceUnavailableCount", 0)
        ),
        "postEntryDataUseCount": int(certification.get("postEntryDataUseCount", -1)),
        "economicMetricReadCount": int(
            certification.get("economicMetricReadCount", -1)
        ),
        "exitReplayCount": int(certification.get("exitReplayCount", -1)),
        "structuralCertificationFormalRunClaimCount": int(
            certification.get("formalRunClaimCount", -1)
        ),
        "structuralCertificationLockedOosAccessCount": int(
            certification.get("lockedOosAccessCount", -1)
        ),
        "structuralCertificationResultReadCount": int(
            certification.get("resultReadCount", -1)
        ),
        "structuralCertificationReleaseCount": int(
            certification.get("releaseCount", -1)
        ),
        "structuralCertificationDemoArm": certification.get("demoArm"),
        "structuralCertificationOrderCount": int(
            certification.get("orderCount", -1)
        ),
        "economicResultComputationDisabled": access.get(
            "economicResultComputationDisabled"
        ),
        "exitReplayDisabled": access.get("exitReplayDisabled"),
        "resultMetricWriterDisabled": access.get("resultMetricWriterDisabled"),
    }


def build_v18_3_preregistration(
    repo_root: Path,
    *,
    implementation_commit: str,
    frozen_at: str,
    certification_root: Path,
) -> dict[str, Any]:
    """Derive V18.3 from terminal V18.2 without changing frozen policy values."""

    root = Path(repo_root).resolve()
    implementation = str(implementation_commit).strip()
    if len(implementation) != 40:
        raise ValueError("A full correction implementation commit is required")
    predecessor_path = root / V18_2_PREREGISTRATION_PATH
    predecessor = _read_json(predecessor_path)
    if not verify_v18_2_preregistration(predecessor):
        raise ValueError("The predecessor V18.2 preregistration is invalid")
    result_root = root / V18_2_RESULT_ROOT
    ledger_path = result_root / "formal_run_ledger.json"
    manifest_path = result_root / "artifact_manifest.json"
    ledger = _read_json(ledger_path)
    if ledger.get("state") != "completed" or int(ledger.get("attemptCount", 0)) != 1:
        raise ValueError("The predecessor V18.2 formal ledger is not terminal")

    certification_dir = Path(certification_root).resolve()
    certification_path = (
        certification_dir / "signal_evidence_structural_certification.json"
    )
    contract_path = (
        certification_dir / "signal_evidence_structural_certification_contract.json"
    )
    access_path = certification_dir / "signal_evidence_access_audit.json"
    certification = _read_json(certification_path)
    contract = _read_json(contract_path)
    access = _read_json(access_path)
    if certification.get("status") != "certified" or certification.get("blockers") != []:
        raise ValueError("Signal evidence structural certification is not certified")
    fields = _certification_fields(certification)
    required_true = (
        fields["formalEventDispositionConservationPassed"],
        fields["rankingEvidenceRecordCoveragePercent"] == 100.0,
        fields["rankingEvidenceStatusCoveragePercent"] == 100.0,
        fields["rankingEvidenceParityPercent"] == 100.0,
        fields["postEntryDataUseCount"] == 0,
        fields["economicMetricReadCount"] == 0,
        fields["exitReplayCount"] == 0,
        fields["structuralCertificationFormalRunClaimCount"] == 0,
        fields["structuralCertificationLockedOosAccessCount"] == 0,
        fields["structuralCertificationResultReadCount"] == 0,
        fields["structuralCertificationReleaseCount"] == 0,
        fields["structuralCertificationDemoArm"] is False,
        fields["structuralCertificationOrderCount"] == 0,
        fields["economicResultComputationDisabled"] is True,
        fields["exitReplayDisabled"] is True,
        fields["resultMetricWriterDisabled"] is True,
    )
    if not all(required_true):
        raise ValueError("Signal evidence structural certification gates failed")

    payload = deepcopy(predecessor)
    payload.pop("preregistrationHash", None)
    certification_hash = str(fields["signalEvidenceStructuralCertificationHash"] or "")
    payload.update(
        {
            "schemaVersion": "s01_v18_3_fold_ranking_evidence_preregistration_v1",
            "campaignId": _campaign_id(
                predecessor_campaign_id=V18_2_CAMPAIGN_ID,
                implementation_commit=implementation,
                certification_hash=certification_hash,
            ),
            "frozenAt": _utc_iso(_parse_utc(frozen_at)),
            "parentCampaignId": V18_2_CAMPAIGN_ID,
            "parentPreregistrationHash": str(predecessor["preregistrationHash"]),
            "correctionOfCampaignId": V18_2_CAMPAIGN_ID,
            "correctionReason": CORRECTION_REASON,
            "correctionScope": "event_disposition_and_ranking_evidence_records_only",
            "correctionImplementationCommit": implementation,
            "implementationCommit": implementation,
            "predecessorV18_2PreregistrationHash": sha256_file(predecessor_path),
            "predecessorV18_2FormalRunLedgerHash": sha256_file(ledger_path),
            "predecessorV18_2ArtifactManifestHash": sha256_file(manifest_path),
            "predecessorV18_2FrozenContractHashesHash": stable_hash(
                predecessor["frozenContractHashes"],
                prefix="v18_2_frozen_contract_hashes",
            ),
            "evidenceRecordVersion": "v18_3",
            **fields,
            "signalEvidenceStructuralCertificationFileHash": sha256_file(
                certification_path
            ),
            "signalEvidenceStructuralCertificationContractHash": contract.get(
                "contractHash"
            ),
            "signalEvidenceStructuralCertificationContractFileHash": sha256_file(
                contract_path
            ),
            "signalEvidenceAccessAuditFileHash": sha256_file(access_path),
            "signalEvidenceStructuralCertificationPath": certification_path.relative_to(
                root
            ).as_posix(),
            "signalEvidenceStructuralCertificationContractPath": contract_path.relative_to(
                root
            ).as_posix(),
            "signalEvidenceAccessAuditPath": access_path.relative_to(root).as_posix(),
            "v18_3FoldAssignmentImplementationHash": sha256_file(
                root / "alphapilot/formal_validation/formal_fold_assignment.py"
            ),
            "v18_3RankingEvidenceImplementationHash": sha256_file(
                root / "alphapilot/formal_validation/ranking_evidence.py"
            ),
            "strategyParameterChangesV18_3": 0,
            "BearDefinitionChangesV18_3": 0,
            "exitPolicyChangesV18_3": 0,
            "capitalPolicyNumericChangesV18_3": 0,
            "capitalPolicySemanticChangesV18_3": 0,
            "GateChangesV18_3": 0,
            "universeChangesV18_3": 0,
            "splitPolicyChangesV18_3": 0,
            "costChangesV18_3": 0,
            "fundingChangesV18_3": 0,
            "benchmarkChangesV18_3": 0,
            "statisticalPolicyChangesV18_3": 0,
            "resultDrivenChangesV18_3": 0,
            "formalRunClaimBudget": 1,
            "safetyBoundary": {
                "formalRunClaimCount": 0,
                "formalRunAttemptCount": 0,
                "formalResultRunCount": 0,
                "resultReadCount": 0,
                "formalResultArtifactCount": 0,
                "lockedOosAccessCount": 0,
                "formalEvidenceCount": 0,
                "releaseCount": 0,
                "demoArm": False,
                "orderCount": 0,
            },
        }
    )
    locked_oos = deepcopy(payload.get("lockedOosPolicy", {}))
    locked_oos.update(
        {
            "contentRead": False,
            "accessCount": 0,
            "identityStatus": "pending_creation_after_remote_preregistration_freeze",
            "identityCreationStage": "after_v18_3_remote_preregistration_freeze",
            "identityMayContainPerformanceData": False,
        }
    )
    payload["lockedOosPolicy"] = locked_oos
    payload["preregistrationHash"] = stable_hash(
        payload, prefix=V18_3_PREREGISTRATION_HASH_PREFIX
    )
    return payload


def verify_v18_3_preregistration(payload: Mapping[str, Any]) -> bool:
    try:
        core = {key: value for key, value in payload.items() if key != "preregistrationHash"}
        if payload.get("preregistrationHash") != stable_hash(
            core, prefix=V18_3_PREREGISTRATION_HASH_PREFIX
        ):
            return False
        if not str(payload.get("campaignId") or "").startswith(V18_3_CAMPAIGN_PREFIX):
            return False
        if payload.get("correctionOfCampaignId") != V18_2_CAMPAIGN_ID:
            return False
        if payload.get("correctionReason") != CORRECTION_REASON:
            return False
        if payload.get("evidenceRecordVersion") != "v18_3":
            return False
        if stable_hash(
            payload.get("frozenContractHashes", {}),
            prefix="v18_2_frozen_contract_hashes",
        ) != V18_2_FROZEN_CONTRACT_HASHES_HASH:
            return False
        hashes = payload.get("frozenContractHashes")
        if not isinstance(hashes, Mapping) or any(
            payload.get(key) != value for key, value in hashes.items()
        ):
            return False
        for key in (
            "strategyParameterChangesV18_3",
            "BearDefinitionChangesV18_3",
            "exitPolicyChangesV18_3",
            "capitalPolicyNumericChangesV18_3",
            "capitalPolicySemanticChangesV18_3",
            "GateChangesV18_3",
            "universeChangesV18_3",
            "splitPolicyChangesV18_3",
            "costChangesV18_3",
            "fundingChangesV18_3",
            "benchmarkChangesV18_3",
            "statisticalPolicyChangesV18_3",
            "resultDrivenChangesV18_3",
        ):
            if int(payload.get(key, -1)) != 0:
                return False
        if payload.get("signalEvidenceStructuralCertificationStatus") != "certified":
            return False
        if payload.get("formalEventDispositionConservationPassed") is not True:
            return False
        if int(payload.get("rawEventCount", 0)) <= 0:
            return False
        if int(payload.get("assignedValidationEventCount", 0)) <= 0:
            return False
        if int(payload.get("rankingEvidenceRecordMissingCount", -1)) != 0:
            return False
        if int(payload.get("rankingEvidenceStatusMissingCount", -1)) != 0:
            return False
        for key in (
            "rankingEvidenceRecordCoveragePercent",
            "rankingEvidenceStatusCoveragePercent",
            "rankingEvidenceParityPercent",
        ):
            if float(payload.get(key, 0.0)) != 100.0:
                return False
        for key in (
            "postEntryDataUseCount",
            "economicMetricReadCount",
            "exitReplayCount",
            "structuralCertificationFormalRunClaimCount",
            "structuralCertificationLockedOosAccessCount",
            "structuralCertificationResultReadCount",
            "structuralCertificationReleaseCount",
            "structuralCertificationOrderCount",
        ):
            if int(payload.get(key, -1)) != 0:
                return False
        if payload.get("structuralCertificationDemoArm") is not False:
            return False
        if int(payload.get("formalRunClaimBudget", 0)) != 1:
            return False
        safety = payload.get("safetyBoundary")
        if not isinstance(safety, Mapping):
            return False
        zero_keys = (
            "formalRunClaimCount",
            "formalRunAttemptCount",
            "formalResultRunCount",
            "resultReadCount",
            "formalResultArtifactCount",
            "lockedOosAccessCount",
            "formalEvidenceCount",
            "releaseCount",
            "orderCount",
        )
        return all(int(safety.get(key, -1)) == 0 for key in zero_keys) and (
            safety.get("demoArm") is False
        )
    except (KeyError, TypeError, ValueError):
        return False


def v18_3_preregistration_path(payload: Mapping[str, Any]) -> Path:
    campaign_id = str(payload.get("campaignId") or "")
    if not campaign_id.startswith(V18_3_CAMPAIGN_PREFIX):
        raise ValueError("Unexpected V18.3 campaign id")
    return Path("research/preregistrations") / f"{campaign_id}.json"


def write_v18_3_preregistration(payload: Mapping[str, Any], repo_root: Path) -> Path:
    if not verify_v18_3_preregistration(payload):
        raise ValueError("V18.3 preregistration is invalid")
    path = Path(repo_root).resolve() / v18_3_preregistration_path(payload)
    _write_json_once(path, payload, conflict_code="immutable_preregistration_conflict")
    return path


def build_v18_3_future_locked_oos_identity(
    preregistration: Mapping[str, Any],
    *,
    remote_freeze_commit: str,
    remote_verified_at: str,
) -> dict[str, Any]:
    if not verify_v18_3_preregistration(preregistration):
        raise ValueError("V18.3 preregistration is invalid")
    core = {
        "schemaVersion": "s01_v18_3_future_locked_oos_identity_v1",
        "campaignId": str(preregistration["campaignId"]),
        "candidateId": str(preregistration["sourceCandidateId"]),
        "strategyDefinitionHash": str(preregistration["strategyDefinitionHash"]),
        "exitPolicyHash": str(preregistration["exitPolicyHash"]),
        "formalPortfolioPolicyV2Hash": str(
            preregistration["formalPortfolioPolicyV2Hash"]
        ),
        "preregistrationHash": str(preregistration["preregistrationHash"]),
        "signalEvidenceStructuralCertificationHash": str(
            preregistration["signalEvidenceStructuralCertificationHash"]
        ),
        "remoteFreezeCommit": str(remote_freeze_commit),
        "remoteVerifiedAt": _utc_iso(_parse_utc(remote_verified_at)),
        "startInclusive": _next_strict_four_hour_boundary(remote_verified_at),
        "timeframe": "4h",
        "coreUniverseHash": str(preregistration["coreUniverseHash"]),
        "metadataOnly": True,
        "accessCount": 0,
        "contentReadCount": 0,
        "strategyMetricReadCount": 0,
        "formalWalkForwardResultHash": None,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    future_id = stable_hash(core, prefix="s01_v18_3_future_locked_oos")
    return {
        **core,
        "futureLockedOosId": future_id,
        "identityHash": stable_hash(
            {**core, "futureLockedOosId": future_id},
            prefix="s01_v18_3_future_locked_oos_identity",
        ),
    }


def write_v18_3_future_locked_oos_metadata(
    identity: Mapping[str, Any], *, repo_root: Path
) -> tuple[Path, Path, dict[str, Any]]:
    root = Path(repo_root).resolve() / "research/locked_oos"
    root.mkdir(parents=True, exist_ok=True)
    campaign_id = str(identity.get("campaignId") or "")
    if not campaign_id.startswith(V18_3_CAMPAIGN_PREFIX):
        raise ValueError("Future OOS identity has an invalid campaign")
    identity_path = root / f"{campaign_id}_future_locked_oos_identity.json"
    ledger_path = root / f"{campaign_id}_future_locked_oos_access_ledger.jsonl"
    _write_json_once(
        identity_path,
        identity,
        conflict_code="immutable_future_oos_identity_conflict",
    )
    event_core = {
        "schemaVersion": "s01_v18_3_future_oos_ledger_event_v1",
        "eventType": "identity_registered",
        "recordedAt": identity["remoteVerifiedAt"],
        "futureLockedOosId": identity["futureLockedOosId"],
        "identityHash": identity["identityHash"],
        "accessCountDelta": 0,
        "contentReadCountDelta": 0,
        "strategyMetricReadCountDelta": 0,
        "previousEventHash": None,
    }
    event = {
        **event_core,
        "eventHash": stable_hash(event_core, prefix="s01_v18_3_future_oos_event"),
    }
    if not ledger_path.exists():
        ledger_path.write_text(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    audit = {
        "schemaVersion": "s01_v18_3_future_locked_oos_access_audit_v1",
        "status": "passed",
        "futureLockedOosId": identity["futureLockedOosId"],
        "lockedOosAccessCount": 0,
        "contentReadCount": 0,
        "strategyMetricReadCount": 0,
    }
    return identity_path, ledger_path, audit


def build_v18_3_formal_run_authorization(
    preregistration: Mapping[str, Any],
    *,
    implementation_commit: str,
    remote_implementation_commit: str,
    remote_preregistration_commit: str,
    future_locked_oos_identity: Mapping[str, Any],
    checks: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "predecessorV18_2ArtifactsModified": (
            False,
            "predecessor_v18_2_artifacts_modified",
        ),
        "structuralCertificationPassed": (
            True,
            "structural_certification_not_passed",
        ),
        "dispositionConservationPassed": (
            True,
            "event_disposition_conservation_failed",
        ),
        "rankingRecordCoveragePassed": (True, "ranking_record_coverage_failed"),
        "rankingStatusCoveragePassed": (True, "ranking_status_coverage_failed"),
        "rankingParityPassed": (True, "ranking_parity_failed"),
        "postEntryDataUseZero": (True, "post_entry_data_use_not_zero"),
        "economicMetricReadsZero": (True, "economic_metric_reads_not_zero"),
        "exitReplayZero": (True, "exit_replay_not_zero"),
        "candidateNeutralImportPassed": (True, "candidate_neutral_import_failed"),
        "syntheticSecondCandidatePassed": (
            True,
            "synthetic_second_candidate_failed",
        ),
        "correctionCodePushed": (True, "correction_code_not_published"),
        "correctionPreregistrationPushed": (
            True,
            "correction_preregistration_not_published",
        ),
    }
    blockers = [
        blocker
        for key, (expected, blocker) in required.items()
        if checks.get(key) is not expected
    ]
    for key in ("formalResultRunCount", "resultReadCount", "lockedOosAccessCount"):
        if int(checks.get(key, -1)) != 0:
            blockers.append(f"{key}_not_zero")
    if str(implementation_commit) != str(remote_implementation_commit):
        blockers.append("implementation_commit_remote_mismatch")
    if str(preregistration.get("correctionImplementationCommit")) != str(
        implementation_commit
    ):
        blockers.append("implementation_commit_preregistration_mismatch")
    if future_locked_oos_identity.get("preregistrationHash") != preregistration.get(
        "preregistrationHash"
    ):
        blockers.append("future_oos_preregistration_mismatch")
    if int(future_locked_oos_identity.get("accessCount", -1)) != 0:
        blockers.append("future_oos_access_not_zero")
    core = {
        "schemaVersion": "s01_v18_3_formal_run_authorization_v1",
        "authorizationStatus": "authorized" if not blockers else "blocked",
        "blockers": blockers,
        "campaignId": str(preregistration["campaignId"]),
        "candidateId": str(preregistration["sourceCandidateId"]),
        "implementationCommit": str(implementation_commit),
        "remoteImplementationCommit": str(remote_implementation_commit),
        "preregistrationHash": str(preregistration["preregistrationHash"]),
        "remotePreregistrationCommit": str(remote_preregistration_commit),
        "signalEvidenceStructuralCertificationHash": str(
            preregistration["signalEvidenceStructuralCertificationHash"]
        ),
        "futureLockedOosId": str(future_locked_oos_identity["futureLockedOosId"]),
        "futureLockedOosAccessCount": int(future_locked_oos_identity["accessCount"]),
        "formalRunClaimBudget": 1,
        "checks": dict(checks),
    }
    return {
        **core,
        "authorizationHash": stable_hash(
            core, prefix="s01_v18_3_formal_run_authorization"
        ),
    }


def verify_v18_3_formal_run_authorization(
    authorization: Mapping[str, Any], *, preregistration: Mapping[str, Any]
) -> bool:
    if not verify_v18_3_preregistration(preregistration):
        return False
    if authorization.get("authorizationStatus") != "authorized":
        return False
    core = {key: value for key, value in authorization.items() if key != "authorizationHash"}
    if authorization.get("authorizationHash") != stable_hash(
        core, prefix="s01_v18_3_formal_run_authorization"
    ):
        return False
    return (
        authorization.get("campaignId") == preregistration.get("campaignId")
        and authorization.get("candidateId") == preregistration.get("sourceCandidateId")
        and authorization.get("preregistrationHash")
        == preregistration.get("preregistrationHash")
        and authorization.get("signalEvidenceStructuralCertificationHash")
        == preregistration.get("signalEvidenceStructuralCertificationHash")
        and authorization.get("formalRunClaimBudget") == 1
        and authorization.get("futureLockedOosAccessCount") == 0
        and authorization.get("blockers") == []
    )
