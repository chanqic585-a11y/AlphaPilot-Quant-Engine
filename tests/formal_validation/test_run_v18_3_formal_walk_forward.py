from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from alphapilot.scripts import run_v18_3_formal_walk_forward as runner


CAMPAIGN_ID = "advisory_r_v18_3_s01_fold_ranking_evidence_correction_fixture"
CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"


def test_observed_runtime_versions_include_python(monkeypatch) -> None:
    monkeypatch.setattr(runner.platform, "python_version", lambda: "3.14.6")
    module = SimpleNamespace(__version__="fixture")
    observed = runner._observed_runtime_versions(
        freqtrade=module,
        ccxt=module,
        pandas=module,
        numpy=module,
        pyarrow=module,
    )
    assert observed["pythonVersion"] == "3.14.6"


def test_v18_3_runner_injects_frozen_evidence_record_version(
    tmp_path: Path, monkeypatch,
) -> None:
    preregistration = tmp_path / "preregistration.json"
    preregistration.write_text(
        json.dumps({"campaignId": CAMPAIGN_ID, "sourceCandidateId": CANDIDATE_ID}),
        encoding="utf-8",
    )
    paths = {}
    for name, payload in {
        "authorization": {},
        "freeze": {},
        "runtime": {"runtimeHash": "runtime-hash"},
        "evidence_chain_certification": {
            "status": "certified",
            "formalEvidenceChainCertificationHash": "cert-hash",
        },
        "structural_certification": {
            "status": "certified",
            "signalEvidenceStructuralCertificationHash": "structural-cert-hash",
            "economicResultComputationDisabled": True,
            "exitReplayDisabled": True,
            "resultMetricWriterDisabled": True,
        },
    }.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(runner, "verify_v18_3_preregistration", lambda _: True)
    monkeypatch.setattr(
        runner, "verify_v18_3_formal_run_authorization", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(runner, "assert_exact_inprocess_runtime", lambda **_: None)
    monkeypatch.setattr(
        runner,
        "validate_evidence_chain_configuration",
        lambda configuration: (
            dict(configuration["runtimeBinding"]),
            dict(configuration["certification"]),
        ),
    )
    monkeypatch.setattr(
        runner,
        "run_generic",
        lambda *args, **kwargs: calls.append(dict(kwargs))
        or {"formalRunCount": 1, "route": "archive_s01_current_version"},
    )

    route = runner.run(
        tmp_path,
        preregistration_path=preregistration,
        candidate_id=CANDIDATE_ID,
        authorization_path=paths["authorization"],
        freeze_audit_path=paths["freeze"],
        runtime_binding_path=paths["runtime"],
        evidence_chain_certification_path=paths["evidence_chain_certification"],
        structural_certification_path=paths["structural_certification"],
        output_root=tmp_path / "reports",
        data_root=tmp_path / "data",
    )

    assert route["formalRunCount"] == 1
    assert calls[0]["run_id"] == f"{CANDIDATE_ID}-v18-3-formal-001"
    assert calls[0]["executor_context"] == {
        "formal_evidence_chain": {
            "enabled": True,
            "evidenceRecordVersion": "v18_3",
            "runtimeBinding": {"runtimeHash": "runtime-hash"},
            "certification": {
                "status": "certified",
                "formalEvidenceChainCertificationHash": "cert-hash",
            },
            "structuralCertification": {
                "status": "certified",
                "signalEvidenceStructuralCertificationHash": "structural-cert-hash",
                "economicResultComputationDisabled": True,
                "exitReplayDisabled": True,
                "resultMetricWriterDisabled": True,
            },
        }
    }


def test_v18_3_runner_rejects_invalid_evidence_chain_before_claim(
    tmp_path: Path, monkeypatch,
) -> None:
    preregistration = tmp_path / "preregistration.json"
    preregistration.write_text(
        json.dumps({"campaignId": CAMPAIGN_ID, "sourceCandidateId": CANDIDATE_ID}),
        encoding="utf-8",
    )
    paths = {}
    for name, payload in {
        "authorization": {},
        "freeze": {},
        "runtime": {
            "runtimeHash": "runtime-hash",
            "runtimeRequested": True,
            "runtimeLoaded": True,
            "strategyLoaded": True,
            "configLoaded": True,
            "dataRootValidated": True,
            "timerangeValidated": True,
            "networkAccessCount": 0,
            "lockedOosReadCount": 0,
        },
        "evidence_chain_certification": {"status": "blocked"},
        "structural_certification": {
            "status": "certified",
            "signalEvidenceStructuralCertificationHash": "structural-cert-hash",
            "economicResultComputationDisabled": True,
            "exitReplayDisabled": True,
            "resultMetricWriterDisabled": True,
        },
    }.items():
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        paths[name] = path
    monkeypatch.setattr(runner, "verify_v18_3_preregistration", lambda _: True)
    monkeypatch.setattr(runner, "assert_exact_inprocess_runtime", lambda **_: None)
    monkeypatch.setattr(
        runner,
        "run_generic",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generic runner must remain unopened")
        ),
    )

    try:
        runner.run(
            tmp_path,
            preregistration_path=preregistration,
            candidate_id=CANDIDATE_ID,
            authorization_path=paths["authorization"],
            freeze_audit_path=paths["freeze"],
            runtime_binding_path=paths["runtime"],
            evidence_chain_certification_path=paths[
                "evidence_chain_certification"
            ],
            structural_certification_path=paths["structural_certification"],
            output_root=tmp_path / "reports",
            data_root=tmp_path / "data",
        )
    except RuntimeError as error:
        assert str(error) == "formal_evidence_chain_fixture_not_certified"
    else:
        raise AssertionError("invalid evidence chain must fail before claim")


def test_v18_3_runner_stops_before_generic_run_without_exact_runtime(
    tmp_path: Path, monkeypatch,
) -> None:
    preregistration = tmp_path / "preregistration.json"
    preregistration.write_text(
        json.dumps({"campaignId": CAMPAIGN_ID, "sourceCandidateId": CANDIDATE_ID}),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "verify_v18_3_preregistration", lambda _: True)
    monkeypatch.setattr(
        runner,
        "assert_exact_inprocess_runtime",
        lambda **_: (_ for _ in ()).throw(RuntimeError("blocked_freqtrade_runtime")),
    )
    monkeypatch.setattr(
        runner,
        "run_generic",
        lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("generic runner must remain unopened")
        ),
    )

    try:
        runner.run(
            tmp_path,
            preregistration_path=preregistration,
            candidate_id=CANDIDATE_ID,
            authorization_path=tmp_path / "authorization.json",
            freeze_audit_path=tmp_path / "freeze.json",
            runtime_binding_path=tmp_path / "runtime.json",
            evidence_chain_certification_path=(
                tmp_path / "evidence_chain_certification.json"
            ),
            structural_certification_path=tmp_path / "structural_certification.json",
            output_root=tmp_path / "reports",
            data_root=tmp_path / "data",
        )
    except RuntimeError as error:
        assert str(error) == "blocked_freqtrade_runtime"
    else:
        raise AssertionError("missing exact runtime must fail closed")
