from __future__ import annotations

import json
from pathlib import Path

from alphapilot.scripts.run_qlib_preflight import main


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_qlib_cli_is_plan_only_without_run(tmp_path: Path, capsys) -> None:
    assert main(["--repo-root", str(tmp_path)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "plan_only"
    assert payload["modelCampaignRun"] is False
    assert not (tmp_path / "reports" / "v13_27_1_12").exists()


def test_qlib_cli_writes_blocked_preflight_without_running_model(tmp_path: Path, capsys) -> None:
    report_root = tmp_path / "reports" / "v13_27_1_12"
    _write_json(
        report_root / "pit_universe_audit.json",
        {
            "status": "unavailable",
            "medianInvestableContracts": 0,
            "freshHoldoutReady": False,
        },
    )
    _write_json(
        report_root / "snapshot_manifest.json",
        {
            "snapshot": {
                "snapshotId": "snapshot_abc",
                "snapshotHash": "sha256:abc",
                "hashVerified": True,
                "containsStrategyResults": False,
                "containsHoldoutResults": False,
            }
        },
    )
    _write_json(
        tmp_path / "reports" / "reproducibility" / "environment_manifest.json",
        {"dockerVersion": None, "dockerImageDigest": None},
    )

    assert main(["--repo-root", str(tmp_path), "--run"]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["qlibCampaignMayRun"] is False
    assert payload["modelCampaignRun"] is False
    assert (report_root / "qlib_preflight.json").is_file()
    assert (report_root / "qlib_readiness_gate.json").is_file()
