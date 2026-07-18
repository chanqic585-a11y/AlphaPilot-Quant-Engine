from __future__ import annotations

from pathlib import Path

from alphapilot.reports.generate_exit_policy_migration_inventory import (
    scan_exit_policy_references,
    summarize_inventory,
    write_inventory,
)


def _write(root: Path, relative: str, text: str) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_inventory_classifies_active_historical_test_and_documentation_hits(
    tmp_path: Path,
) -> None:
    quant = tmp_path / "quant"
    console = tmp_path / "console"
    _write(
        quant,
        "alphapilot/research_screening/campaign_contract.py",
        'raise ValueError("targetR must be at least 2R")\n',
    )
    _write(
        quant,
        "reports/old_campaign.json",
        '{"minimumTargetR": 2.0}\n',
    )
    _write(
        quant,
        "tests/research_screening/test_contract.py",
        "assert payload['targetR'] == 2\n",
    )
    _write(
        console,
        "alphapilot_control_console/demo_evidence.py",
        'target=">= 2R"\n',
    )
    _write(
        console,
        "README.md",
        "Demo historically required 2R.\n",
    )

    rows = scan_exit_policy_references({"quant": quant, "console": console})
    by_path = {row["relativePath"]: row for row in rows}

    assert by_path["alphapilot/research_screening/campaign_contract.py"]["classification"] == "active_logic"
    assert by_path["alphapilot/research_screening/campaign_contract.py"]["action"] == "migrate"
    assert by_path["reports/old_campaign.json"]["classification"] == "historical_evidence"
    assert by_path["reports/old_campaign.json"]["action"] == "preserve_bytes"
    assert by_path["tests/research_screening/test_contract.py"]["classification"] == "test_contract"
    assert by_path["alphapilot_control_console/demo_evidence.py"]["classification"] == "active_logic"
    assert by_path["README.md"]["classification"] == "documentation"

    summary = summarize_inventory(rows)
    assert summary["activeHardGateHits"] == 2
    assert summary["historicalHitsPreserved"] == 1


def test_inventory_ignores_worktrees_virtualenvs_and_binary_files(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root, ".worktrees/other/active.py", "targetR >= 2\n")
    _write(root, ".venv/lib/site.py", "targetR >= 2\n")
    binary = root / "reports" / "blob.parquet"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(b"targetR >= 2")

    rows = scan_exit_policy_references({"repo": root})

    assert rows == []


def test_inventory_writes_required_markdown_filename(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root, "README.md", "Historical 2R note.\n")

    json_path, markdown_path, _payload = write_inventory(
        {"repo": root}, tmp_path / "reports"
    )

    assert json_path.name == "migration_inventory.json"
    assert markdown_path.name == "migration_inventory.md"
    assert markdown_path.exists()


def test_inventory_does_not_rescan_its_generated_outputs(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    _write(root, "reports/exit_policy/migration_inventory.json", '{"targetR": 2}\n')
    _write(root, "reports/exit_policy/migration_inventory.md", "minimumTargetR\n")
    _write(root, "reports/exit_policy/migration_summary.md", ">=2R\n")
    _write(root, "reports/old_campaign.json", '{"targetR": 2}\n')

    rows = scan_exit_policy_references({"repo": root})

    assert [row["relativePath"] for row in rows] == ["reports/old_campaign.json"]
