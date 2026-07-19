"""Immutable V36 TSMOM Formal handoff contracts."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from alphapilot.evolution.evaluation.purged_walk_forward import (
    build_purged_walk_forward,
)
from alphapilot.evolution.registry.hashing import stable_hash


V36_PREREGISTRATION_HASH_PREFIX = "v36_tsmom_formal_preregistration"
V36_SNAPSHOT_HASH_PREFIX = "v36_tsmom_formal_data_snapshot"
V36_AUTHORIZATION_HASH_PREFIX = "v36_tsmom_formal_run_authorization"
V36_FORMAL_FOLD_COUNT = 5
V36_MINIMUM_TEST_BARS = 60
_TIMEFRAME_HOURS = {"4h": 4, "1dutc": 24}


def _utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _without(value: Mapping[str, Any], *keys: str) -> dict[str, Any]:
    return {key: deepcopy(item) for key, item in value.items() if key not in keys}


def _core_universe(universe: Sequence[str]) -> tuple[list[str], str]:
    instruments = sorted({str(value).strip() for value in universe if str(value).strip()})
    if len(instruments) != len(universe) or not instruments:
        raise ValueError("core_universe_invalid")
    digest = stable_hash(
        {"instrumentIds": instruments, "provider": "okx", "exchange": "okx"},
        prefix="v36_tsmom_core_universe",
    )
    return instruments, digest


def build_v36_data_snapshot(
    *,
    candidate_id: str,
    timeframe: str,
    universe: Sequence[str],
    common_start: str,
    common_cutoff_exclusive: str,
    dataset_references: Sequence[Mapping[str, Any]],
    funding_references: Sequence[Mapping[str, Any]],
    source_snapshot_id: str,
) -> dict[str, Any]:
    """Freeze exact same-exchange OHLCV and funding references."""

    instruments, core_hash = _core_universe(universe)
    if timeframe not in _TIMEFRAME_HOURS:
        raise ValueError("timeframe_unsupported")
    dataset = sorted(
        (deepcopy(dict(row)) for row in dataset_references),
        key=lambda row: (str(row.get("timeframe")), str(row.get("instrumentId"))),
    )
    funding = sorted(
        (deepcopy(dict(row)) for row in funding_references),
        key=lambda row: str(row.get("instrumentId")),
    )
    dataset_ids = [str(row.get("instrumentId") or "") for row in dataset]
    funding_ids = [str(row.get("instrumentId") or "") for row in funding]
    if dataset_ids != instruments or funding_ids != instruments:
        raise ValueError("snapshot_universe_mismatch")
    for row in dataset:
        if (
            str(row.get("timeframe")) != timeframe
            or str(row.get("provider") or "").lower() != "okx"
            or str(row.get("exchange") or "okx").lower() != "okx"
            or not str(row.get("path") or "")
            or not str(row.get("sha256") or "")
        ):
            raise ValueError("ohlcv_reference_invalid")
    for row in funding:
        if (
            str(row.get("provider") or "").lower() != "okx"
            or str(row.get("exchange") or "").lower() != "okx"
            or float(row.get("maximumGapHours") or 0) != 8.0
            or not str(row.get("sourceEndpointContains") or "")
            or not list(row.get("partitions") or [])
        ):
            raise ValueError("funding_reference_invalid")
    core = {
        "schemaVersion": "v36_tsmom_formal_data_snapshot_v1",
        "candidateId": str(candidate_id),
        "timeframe": timeframe,
        "sourceSnapshotId": str(source_snapshot_id),
        "commonStart": _iso(_utc(common_start)),
        "commonCutoffExclusive": _iso(_utc(common_cutoff_exclusive)),
        "coreUniverse": {"instrumentIds": instruments, "provider": "okx", "exchange": "okx"},
        "coreUniverseHash": core_hash,
        "datasetReferences": dataset,
        "fundingDatasetReferences": funding,
        "fundingRequired": True,
        "sameExchangeFundingRequired": True,
        "missingFundingMayBeFilledWithZero": False,
        "lockedOosContentRead": False,
        "lockedOosAccessCount": 0,
    }
    identity = stable_hash(core, prefix="v36_tsmom_snapshot_identity")
    payload = {**core, "snapshotId": f"v36_tsmom_formal_snapshot_{identity[-16:]}"}
    payload["snapshotHash"] = stable_hash(payload, prefix=V36_SNAPSHOT_HASH_PREFIX)
    return payload


def verify_v36_data_snapshot(payload: Mapping[str, Any]) -> bool:
    try:
        instruments, core_hash = _core_universe(
            list(dict(payload["coreUniverse"])["instrumentIds"])
        )
        if payload.get("coreUniverseHash") != core_hash:
            return False
        if payload.get("fundingRequired") is not True:
            return False
        if payload.get("missingFundingMayBeFilledWithZero") is not False:
            return False
        if payload.get("lockedOosContentRead") is not False:
            return False
        if int(payload.get("lockedOosAccessCount", -1)) != 0:
            return False
        if [str(row.get("instrumentId")) for row in payload["datasetReferences"]] != instruments:
            return False
        funding = list(payload["fundingDatasetReferences"])
        if [str(row.get("instrumentId")) for row in funding] != instruments:
            return False
        if any(
            str(row.get("provider") or "").lower() != "okx"
            or str(row.get("exchange") or "").lower() != "okx"
            or not list(row.get("partitions") or [])
            for row in funding
        ):
            return False
        expected = stable_hash(
            _without(payload, "snapshotHash"), prefix=V36_SNAPSHOT_HASH_PREFIX
        )
        return payload.get("snapshotHash") == expected
    except (KeyError, TypeError, ValueError):
        return False


def build_v36_split_policy(
    *,
    timeframe: str,
    sample_count: int,
    common_start: str,
    common_cutoff_exclusive: str,
    maximum_hold_bars: int,
    fold_count: int = V36_FORMAL_FOLD_COUNT,
    minimum_test_bars: int = V36_MINIMUM_TEST_BARS,
) -> dict[str, Any]:
    """Build the unchanged five-fold Formal split on a frozen common index."""

    bar_hours = _TIMEFRAME_HOURS.get(str(timeframe))
    if bar_hours is None or sample_count <= 0 or maximum_hold_bars <= 0:
        raise ValueError("split_policy_invalid")
    start = _utc(common_start)
    cutoff = _utc(common_cutoff_exclusive)
    expected_cutoff = start + timedelta(hours=bar_hours * sample_count)
    if cutoff != expected_cutoff:
        raise ValueError("split_window_sample_count_mismatch")
    minimum_train = int(sample_count * 0.4)
    gap = maximum_hold_bars * 2
    remaining = sample_count - minimum_train - gap
    test_size = remaining // fold_count
    if test_size < minimum_test_bars:
        raise ValueError("walk_forward_capacity_insufficient")
    manifest = build_purged_walk_forward(
        sample_count=sample_count,
        min_train_size=minimum_train,
        test_size=test_size,
        step_size=test_size,
        label_horizon=maximum_hold_bars,
        embargo_size=maximum_hold_bars,
        max_holding_period=maximum_hold_bars,
        min_folds=fold_count,
        mode="expanding",
    )
    folds = [fold.to_dict() for fold in manifest.folds]
    if len(folds) != fold_count:
        raise ValueError("unexpected_walk_forward_fold_count")
    boundary_fields = (
        "trainStart",
        "trainEndExclusive",
        "purgeStart",
        "purgeEndExclusive",
        "embargoStart",
        "embargoEndExclusive",
        "testStart",
        "testEndExclusive",
    )
    for fold in folds:
        for field in boundary_fields:
            fold[f"{field}Timestamp"] = _iso(
                start + timedelta(hours=bar_hours * int(fold[field]))
            )
    core = {
        "schemaVersion": "v36_tsmom_purged_walk_forward_split_v1",
        "timeframe": timeframe,
        "barHours": bar_hours,
        "commonStart": _iso(start),
        "commonCutoffExclusive": _iso(cutoff),
        "sampleCount": sample_count,
        "minimumTrainFraction": 0.4,
        "minimumTrainBars": minimum_train,
        "testBarsPerFold": test_size,
        "foldCount": fold_count,
        "purgeBars": maximum_hold_bars,
        "embargoBars": maximum_hold_bars,
        "maximumHoldBars": maximum_hold_bars,
        "mode": "expanding",
        "ordering": "chronological_utc",
        "eventMayCrossFoldBoundary": False,
        "unusedTailBars": sample_count - int(folds[-1]["testEndExclusive"]),
        "folds": folds,
    }
    core["splitPolicyHash"] = stable_hash(core, prefix="v36_tsmom_split_policy")
    return core


def _candidate_readiness(
    readiness: Mapping[str, Any], candidate_id: str
) -> dict[str, Any]:
    rows = [
        dict(row)
        for row in readiness.get("candidates", [])
        if isinstance(row, Mapping) and str(row.get("candidateId")) == candidate_id
    ]
    if len(rows) != 1:
        raise ValueError("candidate_readiness_missing")
    row = rows[0]
    if row.get("status") != "ready" or list(row.get("blockers") or []):
        raise ValueError("candidate_not_formal_ready")
    return row


def build_v36_preregistration(
    *,
    implementation_commit: str,
    readiness: Mapping[str, Any],
    candidate_id: str,
    snapshot: Mapping[str, Any],
    split_policy: Mapping[str, Any],
    policy_template: Mapping[str, Any],
    remote_freeze_tag: str,
) -> dict[str, Any]:
    """Bind one ready TSMOM identity to unchanged Formal policy objects."""

    if len(str(implementation_commit)) != 40:
        raise ValueError("implementation_commit_invalid")
    if not verify_v36_data_snapshot(snapshot):
        raise ValueError("snapshot_invalid")
    candidate = _candidate_readiness(readiness, candidate_id)
    if str(snapshot.get("candidateId")) != candidate_id:
        raise ValueError("snapshot_candidate_mismatch")
    if str(snapshot.get("timeframe")) != str(candidate.get("timeframe")):
        raise ValueError("snapshot_timeframe_mismatch")
    split = deepcopy(dict(split_policy))
    split_hash = str(split.get("splitPolicyHash") or "")
    if not split_hash or split_hash != stable_hash(
        _without(split, "splitPolicyHash"), prefix="v36_tsmom_split_policy"
    ):
        raise ValueError("split_policy_hash_mismatch")
    if int(split.get("foldCount", 0)) != V36_FORMAL_FOLD_COUNT:
        raise ValueError("formal_fold_count_mismatch")

    template = deepcopy(dict(policy_template))
    copied_keys = (
        "costModel",
        "costModelHash",
        "gates",
        "GateHash",
        "capitalCompetitionPolicy",
        "capitalCompetitionPolicyHash",
        "capacityModelHash",
        "correlationClusterPolicyHash",
        "portfolioBetaPolicyHash",
        "signalRankingPolicyHash",
        "formalPortfolioPolicyV2Hash",
        "formalPolicyObjects",
        "benchmarkPolicy",
        "statisticalPolicy",
        "stoppingRules",
        "trialLineagePolicy",
    )
    policies = {key: deepcopy(template[key]) for key in copied_keys if key in template}
    if int(dict(policies.get("gates") or {}).get("economic", {}).get("completeFoldCount", 0)) != V36_FORMAL_FOLD_COUNT:
        raise ValueError("formal_gate_fold_count_mismatch")
    cost_model = dict(policies.get("costModel") or {})
    if cost_model.get("missingFundingMayBeFilledWithZero") is True:
        raise ValueError("funding_zero_fill_forbidden")
    universe = deepcopy(dict(snapshot["coreUniverse"]))
    campaign_seed = {
        "candidateId": candidate_id,
        "selectedTrialId": candidate["selectedTrialId"],
        "strategyDefinitionHash": candidate["strategyDefinitionHash"],
        "exitPolicyHash": candidate["exitPolicyHash"],
        "dataSnapshotHash": snapshot["snapshotHash"],
        "splitPolicyHash": split_hash,
        "implementationCommit": implementation_commit,
        "capitalCompetitionPolicyHash": policies.get("capitalCompetitionPolicyHash"),
        "signalRankingPolicyHash": policies.get("signalRankingPolicyHash"),
    }
    campaign_hash = stable_hash(campaign_seed)
    core: dict[str, Any] = {
        "schemaVersion": "v36_tsmom_formal_preregistration_v1",
        "campaignId": f"v36_tsmom_formal_{candidate_id}_{campaign_hash[:16]}",
        "sourceCampaignId": readiness.get("campaignId"),
        "sourceReadinessHash": readiness.get("readinessHash"),
        "sourceCandidateId": candidate_id,
        "candidateCount": 1,
        "selectedTrialId": candidate["selectedTrialId"],
        "strategyDefinitionHash": candidate["strategyDefinitionHash"],
        "exitPolicyHash": candidate["exitPolicyHash"],
        "implementationCommit": implementation_commit,
        "implementationConformanceHash": stable_hash(
            {
                "implementationCommit": implementation_commit,
                "candidateId": candidate_id,
                "adapterId": "canonical_replication:crypto_tsmom_turtle_v1",
                "adapterVersion": "v36.0",
            },
            prefix="v36_tsmom_implementation_conformance",
        ),
        "candidateAdapter": {
            "adapterId": "canonical_replication:crypto_tsmom_turtle_v1",
            "adapterVersion": "v36.0",
            "candidateId": candidate_id,
            "contractSchemaVersion": "formal_candidate_adapter_contract_v2",
        },
        "coreUniverse": universe,
        "coreUniverseHash": snapshot["coreUniverseHash"],
        "dataSnapshotId": snapshot["snapshotId"],
        "dataSnapshotHash": snapshot["snapshotHash"],
        "splitPolicy": split,
        "splitPolicyHash": split_hash,
        "parameterChanges": 0,
        "strategyParameterChanges": 0,
        "exitPolicyChanges": 0,
        "splitPolicyChanges": 0,
        "universeChanges": 0,
        "costChanges": 0,
        "capitalPolicyNumericChanges": 0,
        "GateChanges": 0,
        "benchmarkChanges": 0,
        "fundingChanges": 0,
        "resultDrivenChanges": 0,
        "formalRunClaimBudget": 1,
        "formalRunPolicy": {
            "researchOnly": True,
            "maximumRunClaims": 1,
            "claimBoundary": "before_first_formal_input_content_read",
            "postResultRerunAllowed": False,
            "concurrentRunPolicy": "atomic_single_writer_claim",
        },
        "runLedgerPolicy": {
            "states": ["not_started", "running", "completed", "failed"],
            "attemptCountIncrementsAt": "first_formal_input_content_read",
            "resumeDoesNotCreateNewAttempt": True,
        },
        "lockedOosPolicy": {
            "contentRead": False,
            "accessCount": 0,
            "cleanLockedOosAvailable": False,
            "identityMetadataOnly": True,
            "identityMayContainPerformanceData": False,
        },
        "remoteFreezePolicy": {
            "preregistrationMustExistOnUpstreamBeforeRun": True,
            "snapshotMustExistOnUpstreamBeforeRun": True,
            "exactRemoteBytesRequired": True,
            "tagRequiredBeforeRun": True,
            "tag": str(remote_freeze_tag),
        },
        "fundingInputPolicy": {
            "required": True,
            "sameExchangeRequired": True,
            "maximumGapHours": 8,
            "missingValueMayBeFilledWithZero": False,
            "snapshotFundingHash": stable_hash(
                snapshot["fundingDatasetReferences"],
                prefix="v36_tsmom_funding_references",
            ),
        },
        "safetyBoundary": {
            "formalRunCount": 0,
            "formalInputReadCount": 0,
            "resultReadCount": 0,
            "lockedOosAccessCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
            "withdrawIntegration": False,
            "liveTradingIntegration": False,
        },
        **policies,
    }
    core["preregistrationHash"] = stable_hash(
        core, prefix=V36_PREREGISTRATION_HASH_PREFIX
    )
    return core


def verify_v36_preregistration(payload: Mapping[str, Any]) -> bool:
    try:
        if payload.get("schemaVersion") != "v36_tsmom_formal_preregistration_v1":
            return False
        if int(payload.get("candidateCount", 0)) != 1:
            return False
        if any(
            int(payload.get(key, -1)) != 0
            for key in ("parameterChanges", "exitPolicyChanges", "universeChanges", "costChanges")
        ):
            return False
        if int(payload.get("formalRunClaimBudget", 0)) != 1:
            return False
        locked = dict(payload.get("lockedOosPolicy") or {})
        if locked.get("contentRead") is not False or int(locked.get("accessCount", -1)) != 0:
            return False
        split = dict(payload.get("splitPolicy") or {})
        if split.get("splitPolicyHash") != stable_hash(
            _without(split, "splitPolicyHash"), prefix="v36_tsmom_split_policy"
        ):
            return False
        if int(split.get("foldCount", 0)) != V36_FORMAL_FOLD_COUNT:
            return False
        expected = stable_hash(
            _without(payload, "preregistrationHash"),
            prefix=V36_PREREGISTRATION_HASH_PREFIX,
        )
        return payload.get("preregistrationHash") == expected
    except (KeyError, TypeError, ValueError):
        return False


def build_v36_formal_run_authorization(
    *,
    preregistration: Mapping[str, Any],
    readiness: Mapping[str, Any],
    remote_freeze_audit: Mapping[str, Any],
) -> dict[str, Any]:
    blockers: list[str] = []
    if not verify_v36_preregistration(preregistration):
        blockers.append("preregistration_invalid")
    try:
        _candidate_readiness(readiness, str(preregistration.get("sourceCandidateId") or ""))
    except ValueError as error:
        blockers.append(str(error))
    if remote_freeze_audit.get("status") != "passed":
        blockers.extend(str(value) for value in remote_freeze_audit.get("blockers", []))
    for key in (
        "formalRunCount",
        "formalInputReadCount",
        "resultReadCount",
        "lockedOosAccessCount",
        "releaseCount",
        "orderCount",
    ):
        if int(readiness.get(key, -1)) != 0:
            blockers.append(f"nonzero_{key}")
    if readiness.get("demoArm") is not False:
        blockers.append("demo_arm_not_false")
    blockers = sorted(set(blockers))
    core = {
        "schemaVersion": "v36_tsmom_formal_run_authorization_v1",
        "authorizationStatus": "authorized" if not blockers else "blocked",
        "campaignId": preregistration.get("campaignId"),
        "candidateId": preregistration.get("sourceCandidateId"),
        "preregistrationHash": preregistration.get("preregistrationHash"),
        "dataSnapshotHash": preregistration.get("dataSnapshotHash"),
        "implementationCommit": preregistration.get("implementationCommit"),
        "remoteFreezeCommit": remote_freeze_audit.get("headCommit"),
        "formalRunClaimBudget": 1,
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "blockers": blockers,
    }
    core["authorizationHash"] = stable_hash(
        core, prefix=V36_AUTHORIZATION_HASH_PREFIX
    )
    return core


def verify_v36_formal_run_authorization(
    authorization: Mapping[str, Any], *, preregistration: Mapping[str, Any]
) -> bool:
    if authorization.get("authorizationStatus") != "authorized":
        return False
    if list(authorization.get("blockers") or []):
        return False
    expected = stable_hash(
        _without(authorization, "authorizationHash"),
        prefix=V36_AUTHORIZATION_HASH_PREFIX,
    )
    return bool(
        authorization.get("authorizationHash") == expected
        and authorization.get("campaignId") == preregistration.get("campaignId")
        and authorization.get("candidateId") == preregistration.get("sourceCandidateId")
        and authorization.get("preregistrationHash") == preregistration.get("preregistrationHash")
        and authorization.get("dataSnapshotHash") == preregistration.get("dataSnapshotHash")
        and authorization.get("formalRunClaimBudget") == 1
        and authorization.get("formalRunCount") == 0
        and authorization.get("lockedOosAccessCount") == 0
    )
