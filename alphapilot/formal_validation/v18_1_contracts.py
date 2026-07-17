"""Immutable contracts for the V18.1 formal-parity correction campaign."""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash


V18_CAMPAIGN_ID = "advisory_r_v18_s01_capital_policy_correction_7ec0b57a7093dc7a"
V18_CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"
V18_PREREGISTRATION_PATH = Path(
    "research/preregistrations"
) / f"{V18_CAMPAIGN_ID}.json"
V18_FAILURE_LEDGER_PATH = (
    Path("reports/formal_validation")
    / V18_CAMPAIGN_ID
    / V18_CANDIDATE_ID
    / "formal_run_ledger.json"
)
V18_1_CAMPAIGN_PREFIX = "advisory_r_v18_1_s01_formal_parity_runtime_correction_"
V18_1_PREREGISTRATION_HASH_PREFIX = (
    "s01_v18_1_formal_parity_runtime_correction_preregistration"
)
V18_1_ADAPTER_CONTRACT_VERSION = "2"
V18_1_ADAPTER_CONTRACT_SCHEMA = "formal_candidate_adapter_contract_v2"


SIGNAL_IDENTITY_CONTRACT: dict[str, Any] = {
    "schemaVersion": "formal_signal_identity_contract_v2",
    "authority": "candidate_adapter",
    "requiredInputs": [
        "candidateId",
        "symbol",
        "direction",
        "signalTimestamp",
        "expectedEntryTimestamp",
    ],
    "candidateNeutralCore": True,
    "missingContractPolicy": "fail_closed",
    "algorithmChangeAllowed": False,
}
SIGNAL_IDENTITY_CONTRACT_HASH = stable_hash(
    SIGNAL_IDENTITY_CONTRACT,
    prefix="formal_signal_identity_contract_v2",
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


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


def _bear_definition_hash(candidate_id: str) -> str:
    candidate = next(
        (
            row
            for row in build_candidate_inventory()
            if row.get("candidateId") == candidate_id
        ),
        None,
    )
    if not candidate:
        raise ValueError(f"Candidate definition is unavailable: {candidate_id}")
    feature_definition = candidate.get("featureDefinition")
    if not isinstance(feature_definition, Mapping):
        raise ValueError("Candidate feature definition is unavailable")
    definition = {"marketRegime": feature_definition.get("marketRegime")}
    return stable_hash(definition, prefix="s01_bear_definition")


def _frozen_contract_hashes(v18: Mapping[str, Any]) -> dict[str, str]:
    exact_keys = (
        "strategyDefinitionHash",
        "exitPolicyHash",
        "formalPortfolioPolicyV2Hash",
        "capacityModelHash",
        "correlationClusterPolicyHash",
        "portfolioBetaPolicyHash",
        "signalRankingPolicyHash",
        "capitalAcceptanceSequenceHash",
        "coreUniverseHash",
        "splitPolicyHash",
        "costModelHash",
        "benchmarkHash",
        "runtimeHash",
        "ioGuardHash",
        "dataSnapshotHash",
    )
    hashes = {key: str(v18[key]) for key in exact_keys}
    hashes.update(
        {
            "BearDefinitionHash": _bear_definition_hash(
                str(v18["sourceCandidateId"])
            ),
            "capacityPolicyHash": str(v18["capacityModelHash"]),
            "statisticalPolicyHash": stable_hash(
                v18["statisticalPolicy"], prefix="s01_v18_statistical_policy"
            ),
            "GateHash": stable_hash(v18["gates"], prefix="s01_v18_gate"),
        }
    )
    return hashes


def _campaign_id(
    *,
    predecessor_campaign_id: str,
    implementation_commit: str,
) -> str:
    digest = stable_hash(
        {
            "correctionOfCampaignId": predecessor_campaign_id,
            "correctionReason": "undefined_signal_identity_helper_before_result",
            "correctionImplementationCommit": implementation_commit,
            "SignalIdentityContractHash": SIGNAL_IDENTITY_CONTRACT_HASH,
        }
    )
    return f"{V18_1_CAMPAIGN_PREFIX}{digest[:16]}"


def build_v18_1_preregistration(
    repo_root: Path,
    *,
    implementation_commit: str,
    frozen_at: str,
) -> dict[str, Any]:
    """Clone the frozen V18 contract and change only correction identities."""

    root = Path(repo_root).resolve()
    implementation = str(implementation_commit).strip()
    if len(implementation) != 40:
        raise ValueError("A full correction implementation commit is required")
    _parse_utc(frozen_at)
    v18_path = root / V18_PREREGISTRATION_PATH
    failure_path = root / V18_FAILURE_LEDGER_PATH
    v18 = _read_json(v18_path)
    failure = _read_json(failure_path)
    if failure.get("state") != "failed" or int(failure.get("attemptCount", 0)) != 1:
        raise ValueError("The predecessor V18 terminal failure ledger is invalid")
    hashes = _frozen_contract_hashes(v18)
    formal_parity_path = root / "alphapilot/formal_validation/formal_parity.py"

    payload = deepcopy(v18)
    payload.pop("preregistrationHash", None)
    payload.update(
        {
            "schemaVersion": "s01_v18_1_formal_parity_correction_preregistration_v1",
            "campaignId": _campaign_id(
                predecessor_campaign_id=str(v18["campaignId"]),
                implementation_commit=implementation,
            ),
            "frozenAt": _utc_iso(_parse_utc(frozen_at)),
            "parentCampaignId": str(v18["campaignId"]),
            "parentPreregistrationHash": str(v18["preregistrationHash"]),
            "correctionOfCampaignId": str(v18["campaignId"]),
            "correctionReason": "undefined_signal_identity_helper_before_result",
            "correctionScope": "candidate_adapter_signal_identity_invocation_only",
            "predecessorV18PreregistrationHash": sha256_file(v18_path),
            "predecessorV18PreregistrationLogicalHash": str(
                v18["preregistrationHash"]
            ),
            "predecessorV18FailureLedgerHash": sha256_file(failure_path),
            "correctionImplementationCommit": implementation,
            "implementationCommit": implementation,
            "candidateAdapter": {
                "adapterId": "s01_freqtrade_formal_adapter",
                "adapterVersion": V18_1_ADAPTER_CONTRACT_VERSION,
                "candidateId": str(v18["sourceCandidateId"]),
                "contractSchemaVersion": V18_1_ADAPTER_CONTRACT_SCHEMA,
            },
            "CandidateAdapterContractVersion": V18_1_ADAPTER_CONTRACT_VERSION,
            "SignalIdentityContract": deepcopy(SIGNAL_IDENTITY_CONTRACT),
            "SignalIdentityContractHash": SIGNAL_IDENTITY_CONTRACT_HASH,
            "FormalParitySourceHash": sha256_file(formal_parity_path),
            "frozenContractHashes": hashes,
            **hashes,
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
            "signalIdentityInvocationRepair": 1,
            "CandidateAdapterContractVersionChange": 1,
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
            "identityCreationStage": "after_v18_1_remote_preregistration_freeze",
            "identityMayContainPerformanceData": False,
        }
    )
    payload["lockedOosPolicy"] = locked_oos
    payload["preregistrationHash"] = stable_hash(
        payload,
        prefix=V18_1_PREREGISTRATION_HASH_PREFIX,
    )
    return payload


def verify_v18_1_preregistration(payload: Mapping[str, Any]) -> bool:
    try:
        core = {
            key: value for key, value in payload.items() if key != "preregistrationHash"
        }
        if payload.get("preregistrationHash") != stable_hash(
            core, prefix=V18_1_PREREGISTRATION_HASH_PREFIX
        ):
            return False
        if not str(payload.get("campaignId", "")).startswith(
            V18_1_CAMPAIGN_PREFIX
        ):
            return False
        if payload.get("correctionOfCampaignId") != V18_CAMPAIGN_ID:
            return False
        if payload.get("strategyParameterChanges") != 0:
            return False
        if payload.get("resultDrivenChanges") != 0:
            return False
        if payload.get("formalRunClaimBudget") != 1:
            return False
        if payload.get("CandidateAdapterContractVersion") != "2":
            return False
        if payload.get("SignalIdentityContractHash") != SIGNAL_IDENTITY_CONTRACT_HASH:
            return False
        hashes = payload.get("frozenContractHashes")
        if not isinstance(hashes, Mapping):
            return False
        if any(payload.get(key) != value for key, value in hashes.items()):
            return False
        safety = payload.get("safetyBoundary")
        if not isinstance(safety, Mapping):
            return False
        numeric_zero = (
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
        return all(int(safety.get(key, -1)) == 0 for key in numeric_zero) and (
            safety.get("demoArm") is False
        )
    except (KeyError, TypeError, ValueError):
        return False


def v18_1_preregistration_path(payload: Mapping[str, Any]) -> Path:
    campaign_id = str(payload.get("campaignId") or "")
    if not campaign_id.startswith(V18_1_CAMPAIGN_PREFIX):
        raise ValueError("Unexpected V18.1 campaign id")
    return Path("research/preregistrations") / f"{campaign_id}.json"


def write_v18_1_preregistration(
    payload: Mapping[str, Any], repo_root: Path
) -> Path:
    if not verify_v18_1_preregistration(payload):
        raise ValueError("V18.1 preregistration is invalid")
    path = Path(repo_root).resolve() / v18_1_preregistration_path(payload)
    write_json_atomic(path, dict(payload))
    return path


def build_v18_1_future_locked_oos_identity(
    preregistration: Mapping[str, Any],
    *,
    remote_freeze_commit: str,
    remote_verified_at: str,
) -> dict[str, Any]:
    if not verify_v18_1_preregistration(preregistration):
        raise ValueError("V18.1 preregistration is invalid")
    start = _next_strict_four_hour_boundary(remote_verified_at)
    core = {
        "schemaVersion": "s01_v18_1_future_locked_oos_identity_v1",
        "campaignId": str(preregistration["campaignId"]),
        "candidateId": str(preregistration["sourceCandidateId"]),
        "strategyDefinitionHash": str(preregistration["strategyDefinitionHash"]),
        "exitPolicyHash": str(preregistration["exitPolicyHash"]),
        "formalPortfolioPolicyV2Hash": str(
            preregistration["formalPortfolioPolicyV2Hash"]
        ),
        "signalIdentityContractHash": str(
            preregistration["SignalIdentityContractHash"]
        ),
        "preregistrationHash": str(preregistration["preregistrationHash"]),
        "remoteFreezeCommit": str(remote_freeze_commit),
        "remoteVerifiedAt": _utc_iso(_parse_utc(remote_verified_at)),
        "startInclusive": start,
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
    future_id = stable_hash(core, prefix="s01_v18_1_future_locked_oos")
    return {
        **core,
        "futureLockedOosId": future_id,
        "identityHash": stable_hash(
            {**core, "futureLockedOosId": future_id},
            prefix="s01_v18_1_future_locked_oos_identity",
        ),
    }


def _audit_future_locked_oos(
    identity_path: Path, ledger_path: Path
) -> dict[str, Any]:
    identity = _read_json(identity_path)
    events = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    access = sum(int(row.get("accessCountDelta", 0)) for row in events)
    content = sum(int(row.get("contentReadCountDelta", 0)) for row in events)
    metrics = sum(int(row.get("strategyMetricReadCountDelta", 0)) for row in events)
    expected_identity_hash = stable_hash(
        {key: value for key, value in identity.items() if key != "identityHash"},
        prefix="s01_v18_1_future_locked_oos_identity",
    )
    expected_previous: str | None = None
    chain_valid = True
    for event in events:
        core = {key: value for key, value in event.items() if key != "eventHash"}
        if event.get("previousEventHash") != expected_previous or event.get(
            "eventHash"
        ) != stable_hash(core, prefix="s01_v18_1_future_oos_ledger_event"):
            chain_valid = False
        expected_previous = str(event.get("eventHash"))
    passed = (
        identity.get("identityHash") == expected_identity_hash
        and chain_valid
        and access == 0
        and content == 0
        and metrics == 0
    )
    return {
        "schemaVersion": "s01_v18_1_future_locked_oos_access_audit_v1",
        "status": "passed" if passed else "failed",
        "futureLockedOosId": identity.get("futureLockedOosId"),
        "identityHash": identity.get("identityHash"),
        "identityHashValid": identity.get("identityHash") == expected_identity_hash,
        "hashChainValid": chain_valid,
        "ledgerEventCount": len(events),
        "lockedOosAccessCount": access,
        "contentReadCount": content,
        "strategyMetricReadCount": metrics,
    }


def write_v18_1_future_locked_oos_metadata(
    identity: Mapping[str, Any],
    *,
    repo_root: Path,
) -> tuple[Path, Path, dict[str, Any]]:
    root = Path(repo_root).resolve() / "research/locked_oos"
    root.mkdir(parents=True, exist_ok=True)
    campaign_id = str(identity.get("campaignId") or "")
    if not campaign_id.startswith(V18_1_CAMPAIGN_PREFIX):
        raise ValueError("Future OOS identity has an invalid campaign")
    identity_path = root / f"{campaign_id}_future_locked_oos_identity.json"
    ledger_path = root / f"{campaign_id}_future_locked_oos_access_ledger.jsonl"
    if identity_path.exists():
        if _read_json(identity_path) != dict(identity):
            raise ValueError("Existing Future OOS identity differs")
    else:
        write_json_atomic(identity_path, dict(identity))
    if not ledger_path.exists():
        event_core = {
            "schemaVersion": "s01_v18_1_future_oos_ledger_event_v1",
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
            "eventHash": stable_hash(
                event_core, prefix="s01_v18_1_future_oos_ledger_event"
            ),
        }
        ledger_path.write_text(
            json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    return identity_path, ledger_path, _audit_future_locked_oos(
        identity_path, ledger_path
    )


def build_v18_1_formal_run_authorization(
    preregistration: Mapping[str, Any],
    *,
    implementation_commit: str,
    remote_implementation_commit: str,
    remote_preregistration_commit: str,
    future_locked_oos_identity: Mapping[str, Any],
    checks: Mapping[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    boolean_requirements = {
        "oldV18ArtifactsModified": (False, "predecessor_v18_artifacts_modified"),
        "oldV18LedgerModified": (False, "predecessor_v18_ledger_modified"),
        "realSignalBranchFixturePassed": (True, "real_signal_branch_fixture_failed"),
        "syntheticSecondCandidatePassed": (
            True,
            "synthetic_second_candidate_fixture_failed",
        ),
        "candidateNeutralImportPassed": (
            True,
            "candidate_neutral_import_audit_failed",
        ),
        "undefinedNameCheckPassed": (True, "undefined_name_check_failed"),
        "correctionCodePushed": (True, "correction_code_not_published"),
        "correctionPreregistrationPushed": (
            True,
            "correction_preregistration_not_published",
        ),
    }
    for key, (expected, blocker) in boolean_requirements.items():
        if checks.get(key) is not expected:
            blockers.append(blocker)
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
        "schemaVersion": "s01_v18_1_formal_run_authorization_v1",
        "authorizationStatus": "authorized" if not blockers else "blocked",
        "blockers": blockers,
        "campaignId": str(preregistration["campaignId"]),
        "candidateId": str(preregistration["sourceCandidateId"]),
        "implementationCommit": str(implementation_commit),
        "remoteImplementationCommit": str(remote_implementation_commit),
        "preregistrationHash": str(preregistration["preregistrationHash"]),
        "remotePreregistrationCommit": str(remote_preregistration_commit),
        **dict(preregistration["frozenContractHashes"]),
        "signalIdentityContractHash": str(
            preregistration["SignalIdentityContractHash"]
        ),
        "futureLockedOosId": str(
            future_locked_oos_identity["futureLockedOosId"]
        ),
        "futureLockedOosAccessCount": int(
            future_locked_oos_identity["accessCount"]
        ),
        "formalRunClaimBudget": 1,
        "checks": dict(checks),
    }
    return {
        **core,
        "authorizationHash": stable_hash(
            core, prefix="s01_v18_1_formal_run_authorization"
        ),
    }


def verify_v18_1_formal_run_authorization(
    authorization: Mapping[str, Any],
    *,
    preregistration: Mapping[str, Any],
) -> bool:
    if not verify_v18_1_preregistration(preregistration):
        return False
    if authorization.get("authorizationStatus") != "authorized":
        return False
    core = {
        key: value for key, value in authorization.items() if key != "authorizationHash"
    }
    if authorization.get("authorizationHash") != stable_hash(
        core, prefix="s01_v18_1_formal_run_authorization"
    ):
        return False
    return (
        authorization.get("campaignId") == preregistration.get("campaignId")
        and authorization.get("candidateId")
        == preregistration.get("sourceCandidateId")
        and authorization.get("preregistrationHash")
        == preregistration.get("preregistrationHash")
        and authorization.get("signalIdentityContractHash")
        == preregistration.get("SignalIdentityContractHash")
        and authorization.get("formalRunClaimBudget") == 1
        and authorization.get("futureLockedOosAccessCount") == 0
        and authorization.get("blockers") == []
    )

