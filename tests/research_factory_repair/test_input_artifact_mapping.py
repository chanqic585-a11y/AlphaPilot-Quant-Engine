from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphapilot.research_factory_repair.input_artifact_mapping import (
    InputArtifactMappingError,
    REQUIRED_LOGICAL_ROLES,
    build_input_artifact_mapping,
    default_phase34_role_specs,
    run_default_phase34_mapping,
    write_input_artifact_mapping_reports,
)


def _write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")
    return path


def test_explicit_path_wins_and_records_immutable_evidence(tmp_path: Path) -> None:
    explicit = _write_json(
        tmp_path / "explicit" / "campaign.json",
        {"schemaVersion": "campaign_v1", "campaignId": "campaign_a"},
    )
    _write_json(
        tmp_path / "other" / "campaign.json",
        {"schemaVersion": "campaign_v1", "campaignId": "campaign_b"},
    )

    result = build_input_artifact_mapping(
        role_specs={
            "phase3CampaignSummary": {
                "required": True,
                "explicitPaths": [explicit],
                "exactFileNames": ["campaign.json"],
            }
        },
        search_roots=[tmp_path],
    )

    record = result["mappings"]["phase3CampaignSummary"]
    assert result["status"] == "complete"
    assert record["actualPath"] == str(explicit.resolve())
    assert record["exists"] is True
    assert record["selectedBy"] == "explicit_user_path"
    assert record["contentHash"]
    assert record["schemaFingerprint"]
    assert record["ambiguousMatches"] == []


def test_unique_schema_fingerprint_is_used_before_exact_name(tmp_path: Path) -> None:
    selected = _write_json(
        tmp_path / "renamed.json",
        {"schemaVersion": "gate_v1", "candidates": {}, "campaignId": "c1"},
    )
    _write_json(tmp_path / "gate_matrix.json", {"schemaVersion": "other_v1"})

    result = build_input_artifact_mapping(
        role_specs={
            "phase3GateMatrix": {
                "required": True,
                "schemaFingerprints": ["json:gate_v1:campaignId,candidates,schemaVersion"],
                "exactFileNames": ["gate_matrix.json"],
            }
        },
        search_roots=[tmp_path],
    )

    record = result["mappings"]["phase3GateMatrix"]
    assert record["actualPath"] == str(selected.resolve())
    assert record["selectedBy"] == "unique_schema_fingerprint"


def test_required_ambiguous_schema_match_fails_closed(tmp_path: Path) -> None:
    payload = {"schemaVersion": "audit_v1", "datasets": []}
    _write_json(tmp_path / "a.json", payload)
    _write_json(tmp_path / "b.json", payload)

    with pytest.raises(InputArtifactMappingError, match="ambiguous"):
        build_input_artifact_mapping(
            role_specs={
                "phase3DataAudit": {
                    "required": True,
                    "schemaFingerprints": ["json:audit_v1:datasets,schemaVersion"],
                }
            },
            search_roots=[tmp_path],
        )


def test_required_missing_role_fails_closed_without_placeholder(tmp_path: Path) -> None:
    with pytest.raises(InputArtifactMappingError, match="missing"):
        build_input_artifact_mapping(
            role_specs={
                "phase4DemoStatus": {
                    "required": True,
                    "exactFileNames": ["demo_status.json"],
                }
            },
            search_roots=[tmp_path],
        )


def test_reports_include_json_and_readable_markdown(tmp_path: Path) -> None:
    source = _write_json(
        tmp_path / "summary.json",
        {"schemaVersion": "summary_v1", "status": "completed"},
    )
    mapping = build_input_artifact_mapping(
        role_specs={
            "phase3CampaignSummary": {
                "required": True,
                "explicitPaths": [source],
            }
        },
        search_roots=[tmp_path],
    )

    json_path, markdown_path = write_input_artifact_mapping_reports(
        mapping=mapping,
        output_dir=tmp_path / "reports",
    )

    saved = json.loads(json_path.read_text(encoding="utf-8"))
    assert saved["status"] == "complete"
    assert "phase3CampaignSummary" in markdown_path.read_text(encoding="utf-8")


def test_default_specs_cover_every_v2_required_logical_role(tmp_path: Path) -> None:
    specs = default_phase34_role_specs(
        repository_root=tmp_path,
        analysis_report_path=tmp_path / "analysis.md",
    )

    assert set(specs) == set(REQUIRED_LOGICAL_ROLES)
    assert all(spec["required"] is True for spec in specs.values())


def test_default_mapping_runner_writes_complete_reports(tmp_path: Path) -> None:
    analysis_report = tmp_path / "analysis.md"
    specs = default_phase34_role_specs(
        repository_root=tmp_path,
        analysis_report_path=analysis_report,
    )
    for spec in specs.values():
        path = Path(spec["explicitPaths"][0])
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            continue
        if path.suffix == ".json":
            path.write_text('{"schemaVersion":"fixture_v1"}', encoding="utf-8")
        elif path.suffix == ".parquet":
            path.write_bytes(b"PAR1")
        else:
            path.write_text("# Fixture\n", encoding="utf-8")

    mapping = run_default_phase34_mapping(
        repository_root=tmp_path,
        analysis_report_path=analysis_report,
        output_dir=tmp_path / "mapped",
    )

    assert mapping["status"] == "complete"
    assert len(mapping["mappings"]) == len(REQUIRED_LOGICAL_ROLES)
    assert (tmp_path / "mapped" / "input_artifact_mapping.json").is_file()
