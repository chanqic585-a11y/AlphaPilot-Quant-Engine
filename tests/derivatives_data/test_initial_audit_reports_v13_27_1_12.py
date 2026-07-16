from __future__ import annotations

import json
from pathlib import Path

from alphapilot.derivatives_data.initial_audit_reports import (
    generate_initial_audit_reports,
)


def test_generate_initial_audit_reports_writes_mapping_and_capability_evidence(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    output_root = repo_root / "reports" / "v13_27_1_12"
    source = repo_root / "reports" / "baseline.json"
    source.parent.mkdir(parents=True)
    source.write_text('{"status":"data_not_ready"}', encoding="utf-8")

    result = generate_initial_audit_reports(
        repo_root=repo_root,
        output_root=output_root,
        checked_at="2026-07-16T00:00:00Z",
        role_candidates={"baselineReadiness": ["reports/baseline.json"]},
    )

    assert result["status"] == "completed"
    mapping = json.loads((output_root / "input_artifact_mapping.json").read_text("utf-8"))
    capability = json.loads((output_root / "api_capability_audit.json").read_text("utf-8"))
    assert mapping["status"] == "mapped"
    assert capability["publicDataOnly"] is True
    assert (output_root / "input_artifact_mapping.md").is_file()
    assert (output_root / "api_capability_summary.md").is_file()


def test_generate_initial_audit_reports_stops_when_required_mapping_is_missing(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"

    result = generate_initial_audit_reports(
        repo_root=repo_root,
        output_root=repo_root / "reports" / "v13_27_1_12",
        checked_at="2026-07-16T00:00:00Z",
        role_candidates={"missing": ["reports/missing.json"]},
    )

    assert result["status"] == "blocked_input_mapping"
    assert not (repo_root / "reports" / "v13_27_1_12" / "api_capability_audit.json").exists()
