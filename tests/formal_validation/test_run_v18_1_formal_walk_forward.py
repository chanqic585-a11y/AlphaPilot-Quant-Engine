from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphapilot.scripts import run_v18_1_formal_walk_forward as runner


CAMPAIGN_ID = "advisory_r_v18_1_s01_formal_parity_runtime_correction_fixture"
CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"


def _preregistration(path: Path) -> Path:
    payload = {
        "campaignId": CAMPAIGN_ID,
        "sourceCandidateId": CANDIDATE_ID,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_v18_1_runner_injects_correction_contracts_and_records_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, object]] = []

    def generic_run(*args: object, **kwargs: object) -> dict[str, object]:
        calls.append({"args": args, **kwargs})
        return {
            "route": "walk_forward_research_pass_no_clean_holdout",
            "formalRunCount": 1,
            "resultManifestHash": "manifest-hash",
        }

    monkeypatch.setattr(runner, "run_generic", generic_run)
    preregistration = _preregistration(tmp_path / "preregistration.json")
    authorization = tmp_path / "authorization.json"
    authorization.write_text("{}", encoding="utf-8")

    route = runner.run(
        tmp_path,
        preregistration_path=preregistration,
        candidate_id=CANDIDATE_ID,
        authorization_path=authorization,
        output_root=tmp_path / "reports",
    )

    assert route["formalRunClaimCount"] == 1
    assert route["formalRunAttemptCount"] == 1
    assert route["formalResultRunCount"] == 1
    assert route["resultReadCount"] == 1
    assert calls[0]["preregistration_validator"] is runner.verify_v18_1_preregistration
    assert calls[0]["freeze_auditor"] is runner.audit_v18_1_preregistration_freeze
    leaf = tmp_path / "reports" / CAMPAIGN_ID / CANDIDATE_ID
    attempt = json.loads((leaf / "operational_attempt_ledger.json").read_text())
    exposure = json.loads((leaf / "result_exposure_ledger.json").read_text())
    assert attempt["operationalAttemptCount"] == 1
    assert attempt["trialClassification"] == "formal_result_generated"
    assert exposure["resultReadCount"] == 1
    assert exposure["resultExposed"] is True


def test_v18_1_runner_records_pre_result_failure_without_result_exposure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def generic_run(*_: object, **kwargs: object) -> dict[str, object]:
        leaf = Path(kwargs["output_root"]) / CAMPAIGN_ID / CANDIDATE_ID
        leaf.mkdir(parents=True, exist_ok=True)
        (leaf / "formal_run_ledger.json").write_text(
            json.dumps({"state": "failed", "attemptCount": 1}),
            encoding="utf-8",
        )
        raise RuntimeError("pre-result failure")

    monkeypatch.setattr(runner, "run_generic", generic_run)
    preregistration = _preregistration(tmp_path / "preregistration.json")
    authorization = tmp_path / "authorization.json"
    authorization.write_text("{}", encoding="utf-8")

    with pytest.raises(RuntimeError, match="pre-result failure"):
        runner.run(
            tmp_path,
            preregistration_path=preregistration,
            candidate_id=CANDIDATE_ID,
            authorization_path=authorization,
            output_root=tmp_path / "reports",
        )

    leaf = tmp_path / "reports" / CAMPAIGN_ID / CANDIDATE_ID
    attempt = json.loads((leaf / "operational_attempt_ledger.json").read_text())
    exposure = json.loads((leaf / "result_exposure_ledger.json").read_text())
    assert attempt["operationalAttemptCount"] == 1
    assert attempt["trialClassification"] == "implementation_failed_before_result"
    assert attempt["validComparableTrial"] is False
    assert exposure["resultReadCount"] == 0
    assert exposure["resultExposed"] is False
