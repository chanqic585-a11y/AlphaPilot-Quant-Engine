from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphapilot.formal_validation.v18_2_contracts import (
    build_v18_2_formal_run_authorization,
    build_v18_2_future_locked_oos_identity,
    build_v18_2_preregistration,
    verify_v18_2_formal_run_authorization,
    verify_v18_2_preregistration,
    v18_2_preregistration_path,
    write_v18_2_future_locked_oos_metadata,
    write_v18_2_preregistration,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
V18_1_CAMPAIGN = (
    "advisory_r_v18_1_s01_formal_parity_runtime_correction_72ec6d1a8bf0fb71"
)
V18_1_PREREGISTRATION = (
    REPO_ROOT / "research" / "preregistrations" / f"{V18_1_CAMPAIGN}.json"
)
V18_1_RESULT_ROOT = (
    REPO_ROOT
    / "reports"
    / "formal_validation"
    / V18_1_CAMPAIGN
    / "s01_bear_idiosyncratic_selloff_recovery_4h"
)
CERTIFICATION_ROOT = (
    REPO_ROOT / "reports" / "formal_validation" / "v18_2_pre_result_certification"
)


def _preregistration() -> dict[str, object]:
    return build_v18_2_preregistration(
        REPO_ROOT,
        implementation_commit="e" * 40,
        frozen_at="2026-07-18T08:15:00Z",
        certification_root=CERTIFICATION_ROOT,
    )


def test_v18_2_preregistration_changes_only_evidence_chain_identity() -> None:
    predecessor = json.loads(V18_1_PREREGISTRATION.read_text(encoding="utf-8"))
    payload = _preregistration()

    assert payload["campaignId"].startswith(
        "advisory_r_v18_2_s01_formal_evidence_chain_correction_"
    )
    assert payload["correctionOfCampaignId"] == V18_1_CAMPAIGN
    assert payload["correctionReason"] == (
        "formal_runtime_identity_fold_ranking_pit_capacity_funding_evidence_incomplete"
    )
    assert payload["correctionImplementationCommit"] == "e" * 40
    assert payload["predecessorV18_1FormalRunLedgerHash"]
    assert payload["predecessorV18_1ArtifactManifestHash"]
    assert payload["formalEvidenceChainCertificationHash"]
    assert payload["formalRuntimeHash"]
    assert payload["formalEvidenceChainFixtureHash"]
    for key in (
        "runtimeLoaderHash",
        "canonicalEventIdentityContractHash",
        "foldAssignmentContractHash",
        "rankingEvidenceContractHash",
        "pitPortfolioContextContractHash",
        "capacityDataSemanticsContractHash",
        "fundingInputContractHash",
    ):
        assert len(str(payload[key])) == 64
    assert payload["strategyParameterChanges"] == 0
    assert payload["resultDrivenChanges"] == 0
    assert payload["formalRunClaimBudget"] == 1
    assert payload["safetyBoundary"]["formalResultRunCount"] == 0
    assert payload["safetyBoundary"]["releaseCount"] == 0
    assert payload["safetyBoundary"]["demoArm"] is False
    for key, value in predecessor["frozenContractHashes"].items():
        assert payload["frozenContractHashes"][key] == value
        assert payload[key] == value
    assert verify_v18_2_preregistration(payload) is True
    assert v18_2_preregistration_path(payload).name == f"{payload['campaignId']}.json"


def test_v18_2_preregistration_rejects_changed_frozen_policy() -> None:
    payload = _preregistration()
    payload["exitPolicyHash"] = "changed"

    assert verify_v18_2_preregistration(payload) is False


def test_v18_2_future_oos_and_authorization_fail_closed() -> None:
    preregistration = _preregistration()
    identity = build_v18_2_future_locked_oos_identity(
        preregistration,
        remote_freeze_commit="f" * 40,
        remote_verified_at="2026-07-18T08:00:00Z",
    )
    assert identity["startInclusive"] == "2026-07-18T12:00:00Z"
    assert identity["contentReadCount"] == 0

    checks = {
        "oldV18ArtifactsModified": False,
        "oldV18_1ArtifactsModified": False,
        "evidenceChainFixtureCertified": True,
        "runtimeBindingCertified": True,
        "canonicalIdentityFixturePassed": True,
        "foldAssignmentFixturePassed": True,
        "rankingEvidenceFixturePassed": True,
        "pitContextFixturePassed": True,
        "capacitySemanticsFixturePassed": True,
        "fundingRegistryFixturePassed": True,
        "candidateNeutralImportPassed": True,
        "syntheticSecondCandidatePassed": True,
        "correctionCodePushed": True,
        "correctionPreregistrationPushed": True,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
    }
    authorized = build_v18_2_formal_run_authorization(
        preregistration,
        implementation_commit="e" * 40,
        remote_implementation_commit="e" * 40,
        remote_preregistration_commit="f" * 40,
        future_locked_oos_identity=identity,
        checks=checks,
    )
    blocked = build_v18_2_formal_run_authorization(
        preregistration,
        implementation_commit="e" * 40,
        remote_implementation_commit="e" * 40,
        remote_preregistration_commit="f" * 40,
        future_locked_oos_identity=identity,
        checks={**checks, "rankingEvidenceFixturePassed": False},
    )

    assert authorized["authorizationStatus"] == "authorized"
    assert verify_v18_2_formal_run_authorization(
        authorized, preregistration=preregistration
    ) is True
    assert blocked["authorizationStatus"] == "blocked"
    assert "ranking_evidence_fixture_failed" in blocked["blockers"]


def test_v18_2_preregistration_is_write_once(tmp_path: Path) -> None:
    preregistration = _preregistration()
    path = write_v18_2_preregistration(preregistration, tmp_path)

    assert write_v18_2_preregistration(preregistration, tmp_path) == path
    changed = build_v18_2_preregistration(
        REPO_ROOT,
        implementation_commit="e" * 40,
        frozen_at="2026-07-18T09:15:00Z",
        certification_root=CERTIFICATION_ROOT,
    )
    with pytest.raises(RuntimeError, match="immutable_preregistration_conflict"):
        write_v18_2_preregistration(changed, tmp_path)


def test_v18_2_future_oos_identity_is_write_once(tmp_path: Path) -> None:
    preregistration = _preregistration()
    identity = build_v18_2_future_locked_oos_identity(
        preregistration,
        remote_freeze_commit="f" * 40,
        remote_verified_at="2026-07-18T08:00:00Z",
    )
    identity_path, ledger_path, _ = write_v18_2_future_locked_oos_metadata(
        identity, repo_root=tmp_path
    )

    assert write_v18_2_future_locked_oos_metadata(
        identity, repo_root=tmp_path
    )[:2] == (identity_path, ledger_path)
    changed = {**identity, "startInclusive": "2026-07-18T16:00:00Z"}
    with pytest.raises(RuntimeError, match="immutable_future_oos_identity_conflict"):
        write_v18_2_future_locked_oos_metadata(changed, repo_root=tmp_path)
