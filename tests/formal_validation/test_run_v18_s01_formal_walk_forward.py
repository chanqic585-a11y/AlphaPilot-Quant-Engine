from __future__ import annotations

from pathlib import Path

import json
import pytest

from alphapilot.scripts import run_formal_walk_forward as runner
from alphapilot.scripts.run_formal_walk_forward import run


REPO_ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION = (
    REPO_ROOT
    / "research"
    / "preregistrations"
    / "advisory_r_v18_s01_capital_policy_correction_7ec0b57a7093dc7a.json"
)
CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"


class _FakeAdapter:
    candidate_id = CANDIDATE_ID
    adapter_id = "fake-adapter"
    adapter_version = "1"


def _leaf(tmp_path: Path) -> Path:
    return (
        tmp_path
        / "advisory_r_v18_s01_capital_policy_correction_7ec0b57a7093dc7a"
        / CANDIDATE_ID
    )


def test_remote_freeze_blocker_precedes_formal_input_read(tmp_path: Path) -> None:
    calls = {"input": 0, "execute": 0}

    def input_loader(**_: object) -> object:
        calls["input"] += 1
        raise AssertionError("formal input must not be read")

    def executor(**_: object) -> object:
        calls["execute"] += 1
        raise AssertionError("formal execution must not start")

    route = run(
        REPO_ROOT,
        preregistration_path=PREREGISTRATION,
        candidate_id=CANDIDATE_ID,
        output_root=tmp_path,
        freeze_auditor=lambda **_: {
            "status": "blocked",
            "route": "blocked_remote_freeze",
            "blockers": ["remote_v18_tag_missing"],
            "formalInputReadCount": 0,
        },
        input_loader=input_loader,
        executor=executor,
    )

    assert route["route"] == "blocked_remote_freeze"
    assert route["formalRunCount"] == 0
    assert route["formalInputReadCount"] == 0
    assert route["lockedOosAccessCount"] == 0
    assert route["releaseCount"] == 0
    assert route["demoArm"] is False
    assert route["orderCount"] == 0
    assert calls == {"input": 0, "execute": 0}


def test_claim_uses_deterministic_checkpoint_and_executor_failure_is_terminal(
    tmp_path: Path,
) -> None:
    class Bundle:
        pass

    with pytest.raises(RuntimeError, match="formal executor failed"):
        run(
            REPO_ROOT,
            preregistration_path=PREREGISTRATION,
            candidate_id=CANDIDATE_ID,
            output_root=tmp_path,
            freeze_auditor=lambda **_: {
                "status": "passed",
                "route": "remote_freeze_verified",
                "headCommit": "commit-a",
                "blockers": [],
            },
            input_loader=lambda **_: Bundle(),
            adapter_resolver=lambda _: _FakeAdapter(),
            executor=lambda **_: (_ for _ in ()).throw(
                RuntimeError("formal executor failed")
            ),
        )

    ledger = json.loads(
        (_leaf(tmp_path) / "formal_run_ledger.json").read_text(encoding="utf-8")
    )
    assert ledger["state"] == "failed"
    assert ledger["checkpoint"] == {
        "checkpointId": "before_formal_input_read",
        "deterministic": True,
    }
    assert ledger["failureReason"] == "RuntimeError"


def test_default_executor_delegates_to_atomic_formal_reporting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bundle = object()
    calls: list[dict[str, object]] = []

    def execute(**kwargs: object) -> dict[str, object]:
        calls.append(dict(kwargs))
        return {
            "route": "implementation_invalid_requires_new_campaign",
            "resultManifestHash": "manifest-hash",
        }

    monkeypatch.setattr(runner, "execute_v18_formal_campaign", execute)
    adapter = _FakeAdapter()

    result = runner._default_executor(
        bundle=bundle,
        repo_root=tmp_path,
        output_root=tmp_path / "formal",
        candidate_adapter=adapter,
    )

    assert result["resultManifestHash"] == "manifest-hash"
    assert calls == [
        {
            "bundle": bundle,
            "repo_root": tmp_path,
            "output_root": tmp_path / "formal",
            "candidate_adapter": adapter,
        }
    ]
