from __future__ import annotations

import json
from pathlib import Path

from alphapilot.scripts.run_v36_tsmom_formal_walk_forward import run


def test_v36_zero_budget_preflight_never_resolves_adapter_or_reads_input(
    tmp_path: Path,
) -> None:
    preregistration = {
        "schemaVersion": "v36_tsmom_formal_preregistration_v1",
        "campaignId": "v36-campaign",
        "sourceCandidateId": "v35_tsmom_crypto_adaptation",
        "preregistrationHash": "hash",
    }
    preregistration_path = tmp_path / "preregistration.json"
    preregistration_path.write_text(json.dumps(preregistration), encoding="utf-8")
    calls = {"adapter": 0, "input": 0}

    def adapter_resolver(candidate_id: str) -> object:
        calls["adapter"] += 1
        raise AssertionError(candidate_id)

    def input_loader(**kwargs: object) -> object:
        calls["input"] += 1
        raise AssertionError(kwargs)

    route = run(
        tmp_path,
        preregistration_path=preregistration_path,
        candidate_id="v35_tsmom_crypto_adaptation",
        authorization_path=None,
        output_root=tmp_path / "out",
        preregistration_validator=lambda payload: True,
        freeze_auditor=lambda **kwargs: {
            "status": "blocked",
            "blockers": ["preregistration_not_published"],
        },
        adapter_resolver=adapter_resolver,
        input_loader=input_loader,
    )

    assert route["route"] == "blocked_remote_freeze"
    assert route["formalRunCount"] == 0
    assert route["formalInputReadCount"] == 0
    assert calls == {"adapter": 0, "input": 0}
