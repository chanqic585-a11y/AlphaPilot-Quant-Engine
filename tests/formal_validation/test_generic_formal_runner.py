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
