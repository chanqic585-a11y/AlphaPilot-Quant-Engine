from __future__ import annotations

import json
from pathlib import Path

from alphapilot.scripts.build_historical_pit_universe import main


def test_pit_cli_is_plan_only_without_run(tmp_path: Path, capsys) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"

    assert main(["--repo-root", str(repo_root), "--data-root", str(data_root)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "plan_only"
    assert payload["networkAccessAttempted"] is False
    assert payload["writeAttempted"] is False
    assert not (repo_root / "reports" / "v13_27_1_12").exists()


def test_pit_cli_run_writes_canonical_stage3_reports(tmp_path: Path, capsys) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"

    assert (
        main(
            [
                "--repo-root",
                str(repo_root),
                "--data-root",
                str(data_root),
                "--checked-at",
                "2026-07-16T00:00:00Z",
                "--run",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    output_root = repo_root / "reports" / "v13_27_1_12"
    assert payload["mode"] == "run"
    assert payload["status"] == "data_not_ready"
    for name in (
        "family_b_data_chain.json",
        "pit_universe_audit.json",
        "pit_universe_manifest.json",
        "pit_universe_coverage.csv",
        "pit_universe_coverage.json",
        "data_quality_by_source.json",
        "data_quality_by_instrument.csv",
        "data_quality_by_instrument.json",
    ):
        assert (output_root / name).is_file(), name
    assert (output_root / "pit_universe_coverage.csv").read_text(
        encoding="utf-8"
    ).startswith("snapshotTimeUtc,")
