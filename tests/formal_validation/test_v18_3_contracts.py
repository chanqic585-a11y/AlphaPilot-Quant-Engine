from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pytest

from alphapilot.formal_validation.v18_3_contracts import (
    V18_2_CAMPAIGN_ID,
    build_v18_3_formal_run_authorization,
    build_v18_3_future_locked_oos_identity,
    build_v18_3_preregistration,
    verify_v18_3_formal_run_authorization,
    verify_v18_3_preregistration,
    v18_3_preregistration_path,
    write_v18_3_future_locked_oos_metadata,
    write_v18_3_preregistration,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
CERTIFICATION_ROOT = (
    REPO_ROOT / "reports/formal_validation/v18_3_pre_result_certification"
)
IMPLEMENTATION_COMMIT = "60ead957b247b99a5cf25d5a367dddc1adc72f39"


def _preregistration() -> dict[str, object]:
    return build_v18_3_preregistration(
        REPO_ROOT,
        implementation_commit=IMPLEMENTATION_COMMIT,
        frozen_at="2026-07-18T04:00:00Z",
        certification_root=CERTIFICATION_ROOT,
    )


def test_v18_3_preregistration_changes_only_evidence_identity() -> None:
    payload = _preregistration()
    predecessor = __import__("json").loads(
        (
            REPO_ROOT
            / "research/preregistrations"
            / f"{V18_2_CAMPAIGN_ID}.json"
        ).read_text(encoding="utf-8")
    )

    assert verify_v18_3_preregistration(payload) is True
    assert payload["correctionOfCampaignId"] == V18_2_CAMPAIGN_ID
    assert payload["frozenContractHashes"] == predecessor["frozenContractHashes"]
    assert payload["strategyDefinitionHash"] == predecessor["strategyDefinitionHash"]
    assert payload["exitPolicyHash"] == predecessor["exitPolicyHash"]
    assert payload["formalPortfolioPolicyV2Hash"] == predecessor["formalPortfolioPolicyV2Hash"]
    assert payload["GateHash"] == predecessor["GateHash"]
    assert payload["formalRunClaimBudget"] == 1
    assert payload["evidenceRecordVersion"] == "v18_3"
    assert payload["signalEvidenceStructuralCertificationStatus"] == "certified"
    assert payload["formalEventDispositionConservationPassed"] is True
    assert payload["rankingEvidenceRecordCoveragePercent"] == 100.0
    assert payload["rankingEvidenceStatusCoveragePercent"] == 100.0
    assert payload["rankingEvidenceParityPercent"] == 100.0
    assert payload["safetyBoundary"]["formalResultRunCount"] == 0
    assert payload["safetyBoundary"]["lockedOosAccessCount"] == 0
    assert payload["safetyBoundary"]["releaseCount"] == 0
    assert payload["safetyBoundary"]["demoArm"] is False
    assert v18_3_preregistration_path(payload).name == f"{payload['campaignId']}.json"


@pytest.mark.parametrize(
    "key",
    [
        "strategyDefinitionHash",
        "exitPolicyHash",
        "formalPortfolioPolicyV2Hash",
        "GateHash",
        "coreUniverseHash",
        "splitPolicyHash",
        "costModelHash",
        "statisticalPolicyHash",
    ],
)
def test_v18_3_preregistration_rejects_changed_frozen_policy(key: str) -> None:
    payload = _preregistration()
    payload[key] = "changed"
    assert verify_v18_3_preregistration(payload) is False


def test_v18_3_future_oos_and_authorization_fail_closed() -> None:
    preregistration = _preregistration()
    identity = build_v18_3_future_locked_oos_identity(
        preregistration,
        remote_freeze_commit="f" * 40,
        remote_verified_at="2026-07-18T04:10:00Z",
    )
    checks = {
        "predecessorV18_2ArtifactsModified": False,
        "structuralCertificationPassed": True,
        "dispositionConservationPassed": True,
        "rankingRecordCoveragePassed": True,
        "rankingStatusCoveragePassed": True,
        "rankingParityPassed": True,
        "postEntryDataUseZero": True,
        "economicMetricReadsZero": True,
        "exitReplayZero": True,
        "candidateNeutralImportPassed": True,
        "syntheticSecondCandidatePassed": True,
        "correctionCodePushed": True,
        "correctionPreregistrationPushed": True,
        "formalResultRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
    }
    authorized = build_v18_3_formal_run_authorization(
        preregistration,
        implementation_commit=IMPLEMENTATION_COMMIT,
        remote_implementation_commit=IMPLEMENTATION_COMMIT,
        remote_preregistration_commit="f" * 40,
        future_locked_oos_identity=identity,
        checks=checks,
    )
    blocked = build_v18_3_formal_run_authorization(
        preregistration,
        implementation_commit=IMPLEMENTATION_COMMIT,
        remote_implementation_commit=IMPLEMENTATION_COMMIT,
        remote_preregistration_commit="f" * 40,
        future_locked_oos_identity=identity,
        checks={**checks, "rankingParityPassed": False},
    )

    assert identity["startInclusive"] == "2026-07-18T08:00:00Z"
    assert identity["accessCount"] == 0
    assert authorized["authorizationStatus"] == "authorized"
    assert verify_v18_3_formal_run_authorization(
        authorized, preregistration=preregistration
    ) is True
    assert blocked["authorizationStatus"] == "blocked"


def test_v18_3_immutable_writes(tmp_path: Path) -> None:
    preregistration = _preregistration()
    path = write_v18_3_preregistration(preregistration, tmp_path)
    assert write_v18_3_preregistration(preregistration, tmp_path) == path

    changed = deepcopy(preregistration)
    changed["frozenAt"] = "2026-07-18T04:00:01Z"
    with pytest.raises(ValueError, match="invalid"):
        write_v18_3_preregistration(changed, tmp_path)

    identity = build_v18_3_future_locked_oos_identity(
        preregistration,
        remote_freeze_commit="f" * 40,
        remote_verified_at="2026-07-18T04:10:00Z",
    )
    identity_path, ledger_path, audit = write_v18_3_future_locked_oos_metadata(
        identity, repo_root=tmp_path
    )
    assert identity_path.exists()
    assert ledger_path.exists()
    assert audit["lockedOosAccessCount"] == 0
    assert write_v18_3_future_locked_oos_metadata(
        identity, repo_root=tmp_path
    )[0] == identity_path
