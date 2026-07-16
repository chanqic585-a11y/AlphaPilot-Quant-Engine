from __future__ import annotations

import json

from alphapilot.derivatives_data.input_artifact_mapping import map_required_artifacts


def test_input_mapping_selects_one_exact_artifact_and_hashes_schema(tmp_path) -> None:
    artifact = tmp_path / "reports" / "data_readiness.json"
    artifact.parent.mkdir(parents=True)
    artifact.write_text(
        json.dumps({"status": "data_not_ready", "campaignMayRun": False}) + "\n",
        encoding="utf-8",
    )

    report = map_required_artifacts(
        repo_root=tmp_path,
        role_candidates={"v11DataReadiness": ["reports/data_readiness.json"]},
    )

    assert report["status"] == "mapped"
    row = report["artifacts"][0]
    assert row["logicalRole"] == "v11DataReadiness"
    assert row["actualPath"] == "reports/data_readiness.json"
    assert row["exists"] is True
    assert len(row["contentHash"]) == 64
    assert len(row["schemaFingerprint"]) == 64
    assert row["selectedBy"] == "single_existing_candidate"
    assert row["ambiguousCandidates"] == []


def test_input_mapping_fails_closed_for_missing_or_ambiguous_inputs(tmp_path) -> None:
    for name in ("a.json", "b.json"):
        (tmp_path / name).write_text('{"status":"x"}\n', encoding="utf-8")

    report = map_required_artifacts(
        repo_root=tmp_path,
        role_candidates={
            "missing": ["missing.json"],
            "ambiguous": ["a.json", "b.json"],
        },
    )

    assert report["status"] == "blocked_input_mapping"
    by_role = {row["logicalRole"]: row for row in report["artifacts"]}
    assert by_role["missing"]["exists"] is False
    assert by_role["ambiguous"]["actualPath"] is None
    assert by_role["ambiguous"]["ambiguousCandidates"] == ["a.json", "b.json"]

