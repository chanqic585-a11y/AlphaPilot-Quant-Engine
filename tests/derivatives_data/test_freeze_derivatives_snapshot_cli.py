from __future__ import annotations

import json
from pathlib import Path

from alphapilot.scripts.freeze_derivatives_snapshot import main


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_audits(repo_root: Path) -> None:
    report_root = repo_root / "reports" / "v13_27_1_12"
    _write_json(report_root / "api_capability_audit.json", {"status": "completed"})
    _write_json(
        report_root / "data_quality_by_instrument.json",
        [{"contentHash": "sha256:normalized"}],
    )
    _write_json(report_root / "pit_universe_audit.json", {"historicalFormalReady": False})
    _write_json(report_root / "pit_universe_manifest.json", {"status": "not_built"})
    _write_json(report_root / "family_b_data_chain.json", {"status": "diagnostic_ready"})


def test_freeze_cli_is_plan_only_without_run(tmp_path: Path, capsys) -> None:
    assert main(["--repo-root", str(tmp_path)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "plan_only"
    assert payload["writeAttempted"] is False
    assert not (tmp_path / "research" / "data_snapshots").exists()


def test_freeze_cli_writes_data_only_snapshot_and_manifest(tmp_path: Path, capsys) -> None:
    _write_audits(tmp_path)

    assert (
        main(
            [
                "--repo-root",
                str(tmp_path),
                "--git-commit",
                "abc123",
                "--environment-hash",
                "sha256:environment",
                "--created-at",
                "2026-07-16T00:00:00Z",
                "--run",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    snapshot = tmp_path / "research" / "data_snapshots" / f"{payload['snapshotId']}.json"
    manifest = tmp_path / "reports" / "v13_27_1_12" / "snapshot_manifest.json"
    assert snapshot.is_file()
    assert manifest.is_file()
    frozen = json.loads(snapshot.read_text(encoding="utf-8"))
    assert frozen["containsStrategyResults"] is False
    assert frozen["containsHoldoutResults"] is False
