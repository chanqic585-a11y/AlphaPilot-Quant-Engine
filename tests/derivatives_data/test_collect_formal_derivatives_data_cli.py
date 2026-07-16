from __future__ import annotations

import json
from pathlib import Path

from alphapilot.scripts.collect_formal_derivatives_data import main


def test_collection_cli_is_plan_only_without_run(tmp_path: Path, capsys) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"

    assert main(["--repo-root", str(repo_root), "--data-root", str(data_root)]) == 0

    payload = json.loads(capsys.readouterr().out)
    assert payload["mode"] == "plan_only"
    assert payload["networkAccessAttempted"] is False
    assert not (repo_root / "reports" / "v13_27_1_12").exists()


def test_collection_cli_run_scans_existing_data_and_writes_budgeted_manifests(
    tmp_path: Path,
    capsys,
) -> None:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    partition = data_root / "normalized" / "OKX" / "funding" / "BTC.json"
    partition.parent.mkdir(parents=True)
    partition.write_text("[]", encoding="utf-8")

    assert (
        main(
            [
                "--repo-root",
                str(repo_root),
                "--data-root",
                str(data_root),
                "--run",
            ]
        )
        == 0
    )

    payload = json.loads(capsys.readouterr().out)
    output_root = repo_root / "reports" / "v13_27_1_12"
    assert payload["mode"] == "run"
    assert payload["networkRequestCount"] == 0
    assert payload["existingFormalPartitionCount"] == 1
    assert (output_root / "download_budget.json").is_file()
    assert (output_root / "download_resume_manifest.json").is_file()
    assert (output_root / "deduplication_report.json").is_file()
    assert (output_root / "gap_repair_report.json").is_file()
