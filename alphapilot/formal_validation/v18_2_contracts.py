"""Immutable contracts for the V18.2 formal evidence-chain correction."""

from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash


V18_1_CAMPAIGN_ID = (
    "advisory_r_v18_1_s01_formal_parity_runtime_correction_72ec6d1a8bf0fb71"
)
V18_1_CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"
V18_1_PREREGISTRATION_PATH = (
    Path("research/preregistrations") / f"{V18_1_CAMPAIGN_ID}.json"
)
V18_1_RESULT_ROOT = (
    Path("reports/formal_validation") / V18_1_CAMPAIGN_ID / V18_1_CANDIDATE_ID
)
V18_2_CAMPAIGN_PREFIX = (
    "advisory_r_v18_2_s01_formal_evidence_chain_correction_"
)
V18_2_PREREGISTRATION_HASH_PREFIX = (
    "s01_v18_2_formal_evidence_chain_correction_preregistration"
)
V18_2_TAG = "v13.27.1.18.2"
CORRECTION_REASON = (
    "formal_runtime_identity_fold_ranking_pit_capacity_funding_evidence_incomplete"
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
            "formalEvidenceChainCertificationHash": certification_hash,
        },
        prefix="s01_v18_2_formal_evidence_chain_campaign",
    )
    return f"{V18_2_CAMPAIGN_PREFIX}{digest[:16]}"


def build_v18_2_preregistration(
    repo_root: Path,
    *,
    implementation_commit: str,
    frozen_at: str,
    certification_root: Path,
) -> dict[str, Any]:
    """Derive V18.2 from V18.1 while preserving every frozen policy value."""

    root = Path(repo_root).resolve()
    implementation = str(implementation_commit).strip()
    if len(implementation) != 40:
        raise ValueError("A full correction implementation commit is required")
    frozen = _utc_iso(_parse_utc(frozen_at))
    predecessor_path = root / V18_1_PREREGISTRATION_PATH
    predecessor = _read_json(predecessor_path)
    result_root = root / V18_1_RESULT_ROOT
    ledger_path = result_root / "formal_run_ledger.json"
    manifest_path = result_root / "artifact_manifest.json"
    ledger = _read_json(ledger_path)
    if ledger.get("state") != "completed" or int(ledger.get("attemptCount", 0)) != 1:
        raise ValueError("The predecessor V18.1 formal ledger is not terminal")

    certification_dir = Path(certification_root).resolve()
    runtime_path = certification_dir / "freqtrade_runtime_binding.json"
    fixture_path = certification_dir / "formal_evidence_chain_fixture_v1.json"
    certification_path = certification_dir / "formal_evidence_chain_certification.json"
    runtime = _read_json(runtime_path)
    fixture = _read_json(fixture_path)
    certification = _read_json(certification_path)
    if certification.get("status") != "certified":
        raise ValueError("Formal evidence-chain certification is not certified")
    if fixture.get("status") != "certified" or fixture.get("fixtureCertified") is not True:
        raise ValueError("Formal evidence-chain fixture did not pass")

    certification_hash = str(
        certification.get("formalEvidenceChainCertificationHash") or ""
    )
    runtime_hash = str(runtime.get("runtimeHash") or "")
    fixture_hash = str(fixture.get("fixtureHash") or "")
    if not certification_hash or not runtime_hash or not fixture_hash:
        raise ValueError("Formal evidence-chain hashes are incomplete")

    contract_root = root / "alphapilot" / "formal_validation"
    evidence_contract_hashes = {
        "runtimeLoaderHash": sha256_file(contract_root / "freqtrade_runtime_loader.py"),
        "canonicalEventIdentityContractHash": sha256_file(
            contract_root / "canonical_event_identity.py"
        ),
        "foldAssignmentContractHash": sha256_file(
            contract_root / "formal_fold_assignment.py"
        ),
        "rankingEvidenceContractHash": sha256_file(
            contract_root / "ranking_evidence.py"
        ),
        "pitPortfolioContextContractHash": sha256_file(
            contract_root / "pit_portfolio_context.py"
        ),
        "capacityDataSemanticsContractHash": sha256_file(
            contract_root / "capacity_data_semantics.py"
        ),
        "fundingInputContractHash": sha256_file(
            contract_root / "funding_input_registry.py"
        ),
    }

    payload = deepcopy(predecessor)
    payload.pop("preregistrationHash", None)
    payload.update(
        {
            "schemaVersion": "s01_v18_2_formal_evidence_chain_preregistration_v1",
            "campaignId": _campaign_id(
                predecessor_campaign_id=V18_1_CAMPAIGN_ID,
                implementation_commit=implementation,
                certification_hash=certification_hash,
            ),
            "frozenAt": frozen,
            "parentCampaignId": V18_1_CAMPAIGN_ID,
            "parentPreregistrationHash": str(predecessor["preregistrationHash"]),
            "correctionOfCampaignId": V18_1_CAMPAIGN_ID,
            "correctionReason": CORRECTION_REASON,
            "correctionScope": (
                "formal_runtime_identity_fold_ranking_pit_capacity_funding_evidence_only"
            ),
            "correctionImplementationCommit": implementation,
            "implementationCommit": implementation,
            "predecessorV18_1PreregistrationHash": sha256_file(predecessor_path),
            "predecessorV18_1FormalRunLedgerHash": sha256_file(ledger_path),
            "predecessorV18_1ArtifactManifestHash": sha256_file(manifest_path),
            "formalEvidenceChainCertificationHash": certification_hash,
            "formalRuntimeHash": runtime_hash,
            "formalEvidenceChainFixtureHash": fixture_hash,
            **evidence_contract_hashes,
            "formalEvidenceChainCertificationFileHash": sha256_file(
                certification_path
            ),
            "formalRuntimeBindingFileHash": sha256_file(runtime_path),
            "formalEvidenceChainFixtureFileHash": sha256_file(fixture_path),
            "formalEvidenceChainCertificationPath": certification_path.relative_to(
                root
            ).as_posix(),
            "formalRuntimeBindingPath": runtime_path.relative_to(root).as_posix(),
            "formalEvidenceChainFixturePath": fixture_path.relative_to(root).as_posix(),
            "strategyParameterChanges": 0,
            "resultDrivenChanges": 0,
            "BearDefinitionChanges": 0,
            "exitPolicyChanges": 0,
            "capitalPolicyNumericChanges": 0,
            "capitalPolicySemanticChanges": 0,
            "GateChanges": 0,
            "universeChanges": 0,
            "splitPolicyChanges": 0,
            "costChanges": 0,
            "benchmarkChanges": 0,
            "statisticalPolicyChanges": 0,
            "formalEvidenceChainChanges": 1,
            "implementationCommitChange": 1,
            "campaignIdentityChange": 1,
            "preregistrationIdentityChange": 1,
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
            "identityCreationStage": "after_v18_2_remote_preregistration_freeze",
            "identityMayContainPerformanceData": False,
        }
    )
    payload["lockedOosPolicy"] = locked_oos
    payload["preregistrationHash"] = stable_hash(
        payload, prefix=V18_2_PREREGISTRATION_HASH_PREFIX
    )
    return payload


def verify_v18_2_preregistration(payload: Mapping[str, Any]) -> bool:
    try:
        core = {k: v for k, v in payload.items() if k != "preregistrationHash"}
        if payload.get("preregistrationHash") != stable_hash(
            core, prefix=V18_2_PREREGISTRATION_HASH_PREFIX
        ):
            return False
        if not str(payload.get("campaignId") or "").startswith(V18_2_CAMPAIGN_PREFIX):
            return False
        if payload.get("correctionOfCampaignId") != V18_1_CAMPAIGN_ID:
            return False
        if payload.get("correctionReason") != CORRECTION_REASON:
            return False
        for key in (
            "strategyParameterChanges",
            "resultDrivenChanges",
            "BearDefinitionChanges",
            "exitPolicyChanges",
            "capitalPolicyNumericChanges",
            "capitalPolicySemanticChanges",
            "GateChanges",
            "universeChanges",
            "splitPolicyChanges",
            "costChanges",
            "benchmarkChanges",
            "statisticalPolicyChanges",
        ):
            if int(payload.get(key, -1)) != 0:
                return False
        if int(payload.get("formalRunClaimBudget", 0)) != 1:
            return False
        hashes = payload.get("frozenContractHashes")
        if not isinstance(hashes, Mapping) or any(
            payload.get(key) != value for key, value in hashes.items()
        ):
            return False
        if not all(
            payload.get(key)
            for key in (
                "formalEvidenceChainCertificationHash",
                "formalRuntimeHash",
                "formalEvidenceChainFixtureHash",
                "runtimeLoaderHash",
                "canonicalEventIdentityContractHash",
                "foldAssignmentContractHash",
                "rankingEvidenceContractHash",
                "pitPortfolioContextContractHash",
                "capacityDataSemanticsContractHash",
                "fundingInputContractHash",
            )
        ):
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


def v18_2_preregistration_path(payload: Mapping[str, Any]) -> Path:
    campaign_id = str(payload.get("campaignId") or "")
    if not campaign_id.startswith(V18_2_CAMPAIGN_PREFIX):
        raise ValueError("Unexpected V18.2 campaign id")
    return Path("research/preregistrations") / f"{campaign_id}.json"


def write_v18_2_preregistration(payload: Mapping[str, Any], repo_root: Path) -> Path:
    if not verify_v18_2_preregistration(payload):
        raise ValueError("V18.2 preregistration is invalid")
    path = Path(repo_root).resolve() / v18_2_preregistration_path(payload)
    _write_json_once(
        path,
        payload,
        conflict_code="immutable_preregistration_conflict",
    )
    return path


def build_v18_2_future_locked_oos_identity(
    preregistration: Mapping[str, Any],
    *,
    remote_freeze_commit: str,
    remote_verified_at: str,
) -> dict[str, Any]:
    if not verify_v18_2_preregistration(preregistration):
        raise ValueError("V18.2 preregistration is invalid")
    core = {
        "schemaVersion": "s01_v18_2_future_locked_oos_identity_v1",
        "campaignId": str(preregistration["campaignId"]),
        "candidateId": str(preregistration["sourceCandidateId"]),
        "strategyDefinitionHash": str(preregistration["strategyDefinitionHash"]),
        "exitPolicyHash": str(preregistration["exitPolicyHash"]),
        "formalPortfolioPolicyV2Hash": str(
            preregistration["formalPortfolioPolicyV2Hash"]
        ),
        "preregistrationHash": str(preregistration["preregistrationHash"]),
        "formalEvidenceChainCertificationHash": str(
            preregistration["formalEvidenceChainCertificationHash"]
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
    future_id = stable_hash(core, prefix="s01_v18_2_future_locked_oos")
    return {
        **core,
        "futureLockedOosId": future_id,
        "identityHash": stable_hash(
            {**core, "futureLockedOosId": future_id},
            prefix="s01_v18_2_future_locked_oos_identity",
        ),
    }


def write_v18_2_future_locked_oos_metadata(
    identity: Mapping[str, Any], *, repo_root: Path
) -> tuple[Path, Path, dict[str, Any]]:
    root = Path(repo_root).resolve() / "research/locked_oos"
    root.mkdir(parents=True, exist_ok=True)
    campaign_id = str(identity.get("campaignId") or "")
    if not campaign_id.startswith(V18_2_CAMPAIGN_PREFIX):
        raise ValueError("Future OOS identity has an invalid campaign")
    identity_path = root / f"{campaign_id}_future_locked_oos_identity.json"
    ledger_path = root / f"{campaign_id}_future_locked_oos_access_ledger.jsonl"
    _write_json_once(
        identity_path,
        identity,
        conflict_code="immutable_future_oos_identity_conflict",
    )
    event_core = {
        "schemaVersion": "s01_v18_2_future_oos_ledger_event_v1",
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
        "eventHash": stable_hash(event_core, prefix="s01_v18_2_future_oos_event"),
    }
    if not ledger_path.exists():
        ledger_path.write_text(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    audit = {
        "schemaVersion": "s01_v18_2_future_locked_oos_access_audit_v1",
        "status": "passed",
        "futureLockedOosId": identity["futureLockedOosId"],
        "lockedOosAccessCount": 0,
        "contentReadCount": 0,
        "strategyMetricReadCount": 0,
    }
    return identity_path, ledger_path, audit


def build_v18_2_formal_run_authorization(
    preregistration: Mapping[str, Any],
    *,
    implementation_commit: str,
    remote_implementation_commit: str,
    remote_preregistration_commit: str,
    future_locked_oos_identity: Mapping[str, Any],
    checks: Mapping[str, Any],
) -> dict[str, Any]:
    required = {
        "oldV18ArtifactsModified": (False, "predecessor_v18_artifacts_modified"),
        "oldV18_1ArtifactsModified": (
            False,
            "predecessor_v18_1_artifacts_modified",
        ),
        "evidenceChainFixtureCertified": (
            True,
            "evidence_chain_fixture_not_certified",
        ),
        "runtimeBindingCertified": (True, "runtime_binding_not_certified"),
        "canonicalIdentityFixturePassed": (
            True,
            "canonical_identity_fixture_failed",
        ),
        "foldAssignmentFixturePassed": (True, "fold_assignment_fixture_failed"),
        "rankingEvidenceFixturePassed": (True, "ranking_evidence_fixture_failed"),
        "pitContextFixturePassed": (True, "pit_context_fixture_failed"),
        "capacitySemanticsFixturePassed": (
            True,
            "capacity_semantics_fixture_failed",
        ),
        "fundingRegistryFixturePassed": (True, "funding_registry_fixture_failed"),
        "candidateNeutralImportPassed": (
            True,
            "candidate_neutral_import_audit_failed",
        ),
        "syntheticSecondCandidatePassed": (
            True,
            "synthetic_second_candidate_fixture_failed",
        ),
        "correctionCodePushed": (True, "correction_code_not_published"),
        "correctionPreregistrationPushed": (
            True,
            "correction_preregistration_not_published",
        ),
    }
    blockers = [blocker for key, (expected, blocker) in required.items() if checks.get(key) is not expected]
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
        "schemaVersion": "s01_v18_2_formal_run_authorization_v1",
        "authorizationStatus": "authorized" if not blockers else "blocked",
        "blockers": blockers,
        "campaignId": str(preregistration["campaignId"]),
        "candidateId": str(preregistration["sourceCandidateId"]),
        "implementationCommit": str(implementation_commit),
        "remoteImplementationCommit": str(remote_implementation_commit),
        "preregistrationHash": str(preregistration["preregistrationHash"]),
        "remotePreregistrationCommit": str(remote_preregistration_commit),
        "formalEvidenceChainCertificationHash": str(
            preregistration["formalEvidenceChainCertificationHash"]
        ),
        "futureLockedOosId": str(future_locked_oos_identity["futureLockedOosId"]),
        "futureLockedOosAccessCount": int(future_locked_oos_identity["accessCount"]),
        "formalRunClaimBudget": 1,
        "checks": dict(checks),
    }
    return {
        **core,
        "authorizationHash": stable_hash(
            core, prefix="s01_v18_2_formal_run_authorization"
        ),
    }


def verify_v18_2_formal_run_authorization(
    authorization: Mapping[str, Any], *, preregistration: Mapping[str, Any]
) -> bool:
    if not verify_v18_2_preregistration(preregistration):
        return False
    if authorization.get("authorizationStatus") != "authorized":
        return False
    core = {k: v for k, v in authorization.items() if k != "authorizationHash"}
    if authorization.get("authorizationHash") != stable_hash(
        core, prefix="s01_v18_2_formal_run_authorization"
    ):
        return False
    return (
        authorization.get("campaignId") == preregistration.get("campaignId")
        and authorization.get("candidateId") == preregistration.get("sourceCandidateId")
        and authorization.get("preregistrationHash")
        == preregistration.get("preregistrationHash")
        and authorization.get("formalEvidenceChainCertificationHash")
        == preregistration.get("formalEvidenceChainCertificationHash")
        and authorization.get("formalRunClaimBudget") == 1
        and authorization.get("futureLockedOosAccessCount") == 0
        and authorization.get("blockers") == []
    )
