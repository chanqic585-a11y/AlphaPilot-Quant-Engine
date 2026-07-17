from __future__ import annotations

import hashlib
import json
from pathlib import Path

from alphapilot.formal_validation.v18_1_contracts import (
    build_v18_1_formal_run_authorization,
    build_v18_1_future_locked_oos_identity,
    build_v18_1_preregistration,
    verify_v18_1_formal_run_authorization,
    verify_v18_1_preregistration,
    v18_1_preregistration_path,
    write_v18_1_future_locked_oos_metadata,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
V18_PREREGISTRATION = (
    REPO_ROOT
    / "research"
    / "preregistrations"
    / "advisory_r_v18_s01_capital_policy_correction_7ec0b57a7093dc7a.json"
)
V18_FAILURE_LEDGER = (
    REPO_ROOT
    / "reports"
    / "formal_validation"
    / "advisory_r_v18_s01_capital_policy_correction_7ec0b57a7093dc7a"
    / "s01_bear_idiosyncratic_selloff_recovery_4h"
    / "formal_run_ledger.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _preregistration() -> dict[str, object]:
    return build_v18_1_preregistration(
        REPO_ROOT,
        implementation_commit="c" * 40,
        frozen_at="2026-07-18T02:30:00Z",
    )


def test_v18_1_preregistration_binds_the_predecessor_without_mutating_it() -> None:
    preregistration_before = V18_PREREGISTRATION.read_bytes()
    ledger_before = V18_FAILURE_LEDGER.read_bytes()
    v18 = json.loads(preregistration_before.decode("utf-8"))

    payload = _preregistration()

    assert V18_PREREGISTRATION.read_bytes() == preregistration_before
    assert V18_FAILURE_LEDGER.read_bytes() == ledger_before
    assert payload["campaignId"].startswith(
        "advisory_r_v18_1_s01_formal_parity_runtime_correction_"
    )
    assert payload["correctionOfCampaignId"] == v18["campaignId"]
    assert payload["correctionReason"] == (
        "undefined_signal_identity_helper_before_result"
    )
    assert payload["predecessorV18PreregistrationHash"] == _sha256(
        V18_PREREGISTRATION
    )
    assert payload["predecessorV18FailureLedgerHash"] == _sha256(
        V18_FAILURE_LEDGER
    )
    assert payload["correctionImplementationCommit"] == "c" * 40
    assert payload["candidateAdapter"] == {
        "adapterId": "s01_freqtrade_formal_adapter",
        "adapterVersion": "2",
        "candidateId": "s01_bear_idiosyncratic_selloff_recovery_4h",
        "contractSchemaVersion": "formal_candidate_adapter_contract_v2",
    }
    assert payload["CandidateAdapterContractVersion"] == "2"
    assert payload["SignalIdentityContractHash"]
    assert payload["FormalParitySourceHash"]
    assert payload["strategyParameterChanges"] == 0
    assert payload["resultDrivenChanges"] == 0
    assert payload["formalRunClaimBudget"] == 1
    assert payload["safetyBoundary"] == {
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
    }
    for key in (
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
    ):
        assert payload[key] == v18[key]
    assert payload["capacityPolicyHash"] == v18["capacityModelHash"]
    assert payload["BearDefinitionHash"]
    assert payload["statisticalPolicyHash"]
    assert payload["GateHash"]
    assert verify_v18_1_preregistration(payload) is True


def test_v18_1_campaign_and_preregistration_hash_are_deterministic() -> None:
    first = _preregistration()
    second = _preregistration()

    assert first == second
    assert v18_1_preregistration_path(first) == Path(
        "research/preregistrations"
    ) / f"{first['campaignId']}.json"


def test_v18_1_future_oos_starts_at_the_next_strict_four_hour_boundary(
    tmp_path: Path,
) -> None:
    preregistration = _preregistration()
    identity = build_v18_1_future_locked_oos_identity(
        preregistration,
        remote_freeze_commit="d" * 40,
        remote_verified_at="2026-07-18T04:00:00Z",
    )

    assert identity["campaignId"] == preregistration["campaignId"]
    assert identity["startInclusive"] == "2026-07-18T08:00:00Z"
    assert identity["timeframe"] == "4h"
    assert identity["strategyDefinitionHash"] == preregistration[
        "strategyDefinitionHash"
    ]
    assert identity["exitPolicyHash"] == preregistration["exitPolicyHash"]
    assert identity["formalPortfolioPolicyV2Hash"] == preregistration[
        "formalPortfolioPolicyV2Hash"
    ]
    assert identity["signalIdentityContractHash"] == preregistration[
        "SignalIdentityContractHash"
    ]
    assert identity["preregistrationHash"] == preregistration[
        "preregistrationHash"
    ]
    assert identity["remoteFreezeCommit"] == "d" * 40
    assert identity["accessCount"] == 0
    assert identity["contentReadCount"] == 0
    assert identity["strategyMetricReadCount"] == 0

    identity_path, ledger_path, audit = write_v18_1_future_locked_oos_metadata(
        identity,
        repo_root=tmp_path,
    )

    assert identity_path.name.endswith("_future_locked_oos_identity.json")
    assert ledger_path.name.endswith("_future_locked_oos_access_ledger.jsonl")
    assert audit["status"] == "passed"
    assert audit["lockedOosAccessCount"] == 0
    assert audit["contentReadCount"] == 0
    assert audit["strategyMetricReadCount"] == 0


def test_v18_1_authorization_fails_closed_until_all_pre_result_gates_pass() -> None:
    preregistration = _preregistration()
    identity = build_v18_1_future_locked_oos_identity(
        preregistration,
        remote_freeze_commit="d" * 40,
        remote_verified_at="2026-07-18T02:30:00Z",
    )
    checks = {
        "oldV18ArtifactsModified": False,
        "oldV18LedgerModified": False,
        "realSignalBranchFixturePassed": True,
        "syntheticSecondCandidatePassed": True,
        "candidateNeutralImportPassed": True,
        "undefinedNameCheckPassed": True,
        "correctionCodePushed": True,
        "correctionPreregistrationPushed": True,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
    }

    authorized = build_v18_1_formal_run_authorization(
        preregistration,
        implementation_commit="c" * 40,
        remote_implementation_commit="c" * 40,
        remote_preregistration_commit="d" * 40,
        future_locked_oos_identity=identity,
        checks=checks,
    )
    blocked = build_v18_1_formal_run_authorization(
        preregistration,
        implementation_commit="c" * 40,
        remote_implementation_commit="c" * 40,
        remote_preregistration_commit="d" * 40,
        future_locked_oos_identity=identity,
        checks={**checks, "realSignalBranchFixturePassed": False},
    )

    assert authorized["authorizationStatus"] == "authorized"
    assert authorized["blockers"] == []
    assert authorized["formalRunClaimBudget"] == 1
    assert authorized["futureLockedOosAccessCount"] == 0
    assert verify_v18_1_formal_run_authorization(
        authorized, preregistration=preregistration
    ) is True
    assert blocked["authorizationStatus"] == "blocked"
    assert "real_signal_branch_fixture_failed" in blocked["blockers"]
    assert verify_v18_1_formal_run_authorization(
        blocked, preregistration=preregistration
    ) is False
