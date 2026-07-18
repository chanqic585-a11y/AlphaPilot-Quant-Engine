from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from alphapilot.scripts import run_v18_2_formal_walk_forward as runner


CAMPAIGN_ID = "advisory_r_v18_2_s01_formal_evidence_chain_correction_fixture"
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


def test_v18_2_runner_requires_exact_runtime_and_injects_evidence_chain(
    tmp_path: Path, monkeypatch,
) -> None:
    preregistration = tmp_path / "preregistration.json"
    preregistration.write_text(
        json.dumps({"campaignId": CAMPAIGN_ID, "sourceCandidateId": CANDIDATE_ID}),
        encoding="utf-8",
    )
    authorization = tmp_path / "authorization.json"
    authorization.write_text("{}", encoding="utf-8")
    freeze_audit = tmp_path / "freeze.json"
    freeze_audit.write_text("{}", encoding="utf-8")
    runtime = tmp_path / "runtime.json"
    runtime.write_text(json.dumps({"runtimeHash": "runtime-hash"}), encoding="utf-8")
    certification = tmp_path / "certification.json"
    certification.write_text(
        json.dumps({"formalEvidenceChainCertificationHash": "cert-hash"}),
        encoding="utf-8",
    )
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(runner, "verify_v18_2_preregistration", lambda _: True)
    monkeypatch.setattr(
        runner, "verify_v18_2_formal_run_authorization", lambda *_args, **_kwargs: True
    )
    monkeypatch.setattr(runner, "assert_exact_inprocess_runtime", lambda **_: None)
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
        authorization_path=authorization,
        freeze_audit_path=freeze_audit,
        runtime_binding_path=runtime,
        certification_path=certification,
        output_root=tmp_path / "reports",
        data_root=tmp_path / "data",
    )

    assert route["formalRunCount"] == 1
    assert calls[0]["candidate_id"] == CANDIDATE_ID
    assert calls[0]["executor_context"] == {
        "formal_evidence_chain": {
            "enabled": True,
            "runtimeBinding": {"runtimeHash": "runtime-hash"},
            "certification": {"formalEvidenceChainCertificationHash": "cert-hash"},
        }
    }


def test_v18_2_runner_stops_before_generic_run_without_exact_runtime(
    tmp_path: Path, monkeypatch,
) -> None:
    preregistration = tmp_path / "preregistration.json"
    preregistration.write_text(
        json.dumps({"campaignId": CAMPAIGN_ID, "sourceCandidateId": CANDIDATE_ID}),
        encoding="utf-8",
    )
    monkeypatch.setattr(runner, "verify_v18_2_preregistration", lambda _: True)
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
            certification_path=tmp_path / "certification.json",
            output_root=tmp_path / "reports",
            data_root=tmp_path / "data",
        )
    except RuntimeError as error:
        assert str(error) == "blocked_freqtrade_runtime"
    else:
        raise AssertionError("missing exact runtime must fail closed")
