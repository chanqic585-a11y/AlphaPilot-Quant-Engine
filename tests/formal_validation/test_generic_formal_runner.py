from __future__ import annotations

import json
from pathlib import Path

from alphapilot.scripts.run_formal_walk_forward import run


REPO_ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = (
    REPO_ROOT
    / "research"
    / "preregistrations"
    / "advisory_r_v18_s01_capital_policy_correction_7ec0b57a7093dc7a.json"
)
CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"


def test_blocked_generic_run_uses_dynamic_artifact_path_without_reading_input(
    tmp_path: Path,
) -> None:
    calls = {"input": 0, "execute": 0}

    def input_loader(**_: object) -> object:
        calls["input"] += 1
        raise AssertionError("formal input must remain unopened")

    def executor(**_: object) -> object:
        calls["execute"] += 1
        raise AssertionError("formal execution must remain stopped")

    route = run(
        REPO_ROOT,
        preregistration_path=PREREGISTRATION,
        candidate_id=CANDIDATE_ID,
        output_root=tmp_path,
        freeze_auditor=lambda **_: {
            "status": "blocked",
            "route": "blocked_remote_freeze",
            "blockers": ["preregistration_not_published"],
        },
        adapter_resolver=lambda _: object(),
        input_loader=input_loader,
        executor=executor,
    )

    leaf = (
        tmp_path
        / "advisory_r_v18_s01_capital_policy_correction_7ec0b57a7093dc7a"
        / CANDIDATE_ID
    )
    assert route["route"] == "blocked_remote_freeze"
    assert json.loads((leaf / "formal_run_route.json").read_text(encoding="utf-8"))[
        "formalRunCount"
    ] == 0
    assert not (tmp_path / "formal_run_route.json").exists()
    assert calls == {"input": 0, "execute": 0}


def test_custom_preregistration_validator_is_passed_to_input_loader(
    tmp_path: Path,
) -> None:
    preregistration = json.loads(PREREGISTRATION.read_text(encoding="utf-8"))
    custom_path = tmp_path / "custom-preregistration.json"
    custom_path.write_text(
        json.dumps(preregistration, ensure_ascii=False), encoding="utf-8"
    )
    calls: dict[str, object] = {}

    class Adapter:
        adapter_id = "fixture-adapter"
        adapter_version = "2"

    def validator(payload: object) -> bool:
        calls["validated"] = payload
        return True

    def input_loader(**kwargs: object) -> object:
        calls["input_validator"] = kwargs["preregistration_validator"]
        return object()

    route = run(
        REPO_ROOT,
        preregistration_path=custom_path,
        candidate_id=CANDIDATE_ID,
        output_root=tmp_path / "output",
        preregistration_validator=validator,
        freeze_auditor=lambda **_: {
            "status": "passed",
            "route": "remote_freeze_verified",
            "headCommit": "commit-a",
            "blockers": [],
        },
        adapter_resolver=lambda _: Adapter(),
        input_loader=input_loader,
        executor=lambda **_: {
            "route": "formal_run_completed",
            "resultManifestHash": "manifest-hash",
        },
    )

    assert route["formalRunCount"] == 1
    assert calls["validated"] == preregistration
    assert calls["input_validator"] is validator


def test_authorization_gate_precedes_adapter_and_formal_input_read(
    tmp_path: Path,
) -> None:
    calls = {"adapter": 0, "input": 0, "execute": 0}
    authorization_path = tmp_path / "authorization.json"
    authorization_path.write_text(
        json.dumps({"authorizationStatus": "blocked"}), encoding="utf-8"
    )

    def adapter_resolver(_: str) -> object:
        calls["adapter"] += 1
        return object()

    def input_loader(**_: object) -> object:
        calls["input"] += 1
        return object()

    def executor(**_: object) -> object:
        calls["execute"] += 1
        return object()

    route = run(
        REPO_ROOT,
        preregistration_path=PREREGISTRATION,
        candidate_id=CANDIDATE_ID,
        output_root=tmp_path / "output",
        freeze_auditor=lambda **_: {
            "status": "passed",
            "route": "remote_freeze_verified",
            "headCommit": "commit-a",
            "blockers": [],
        },
        authorization_path=authorization_path,
        authorization_validator=lambda *_: False,
        adapter_resolver=adapter_resolver,
        input_loader=input_loader,
        executor=executor,
    )

    assert route["route"] == "blocked_formal_run_authorization"
    assert route["formalRunCount"] == 0
    assert calls == {"adapter": 0, "input": 0, "execute": 0}


def test_generic_runner_passes_candidate_neutral_executor_context(
    tmp_path: Path,
) -> None:
    captured: dict[str, object] = {}

    class Adapter:
        adapter_id = "fixture-adapter"
        adapter_version = "2"

    def executor(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "route": "formal_run_completed",
            "resultManifestHash": "manifest-hash",
        }

    run(
        REPO_ROOT,
        preregistration_path=PREREGISTRATION,
        candidate_id=CANDIDATE_ID,
        output_root=tmp_path / "output",
        freeze_auditor=lambda **_: {
            "status": "passed",
            "route": "remote_freeze_verified",
            "headCommit": "commit-a",
            "blockers": [],
        },
        adapter_resolver=lambda _: Adapter(),
        input_loader=lambda **_: object(),
        executor=executor,
        executor_context={
            "formal_evidence_chain": {"enabled": True},
            "campaign_runtime": "digest-pinned",
        },
    )

    assert captured["formal_evidence_chain"] == {"enabled": True}
    assert captured["campaign_runtime"] == "digest-pinned"
