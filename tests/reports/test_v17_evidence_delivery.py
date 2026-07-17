from __future__ import annotations

import csv
import json
import zipfile
from pathlib import Path

from alphapilot.reports.v17_evidence_delivery import build_evidence_delivery
from alphapilot.scripts.run_s01_formal_walk_forward import run


REPO_ROOT = Path(__file__).resolve().parents[2]


def _build(tmp_path: Path) -> Path:
    route_root = tmp_path / "formal_route"
    run(REPO_ROOT, output_root=route_root)
    output_root = tmp_path / "delivery"
    build_evidence_delivery(REPO_ROOT, output_root, route_root=route_root)
    return output_root


def test_not_run_formal_metrics_are_null_not_zero(tmp_path: Path) -> None:
    output = _build(tmp_path)
    metrics = json.loads((output / "s01_formal_metric_summary.json").read_text("utf-8"))

    assert metrics["formalResultStatus"] == "not_run"
    assert metrics["exactReason"] == "implementation_invalid_requires_new_campaign"
    assert metrics["profitFactor"] is None
    assert metrics["averageNetR"] is None
    assert metrics["tradeCount"] is None


def test_delivery_has_required_ledgers_and_parseable_tables(tmp_path: Path) -> None:
    output = _build(tmp_path)
    required = {
        "v17_stage_inventory.json",
        "v17_stage_issue_ledger.json",
        "v17_patch_candidate_matrix.json",
        "route_decision.json",
        "gate_matrix.json",
        "failure_attribution.json",
        "campaign_summary.json",
        "final_self_check.json",
        "evidence_manifest.json",
        "integrity_verification.json",
        "sensitive_information_scan.json",
    }
    assert required.issubset({path.name for path in output.iterdir()})

    for path in output.glob("*.json"):
        json.loads(path.read_text(encoding="utf-8"))
    for path in output.glob("*.csv"):
        list(csv.reader(path.read_text(encoding="utf-8").splitlines()))


def test_delivery_zips_pass_crc_without_fabricated_event_parquet(tmp_path: Path) -> None:
    output = _build(tmp_path)
    expected = {
        "AlphaPilot-V13.27.1.17-core-evidence.zip",
        "AlphaPilot-V13.27.1.17-event-and-return-evidence.zip",
        "AlphaPilot-V13.27.1.17-source-runtime-evidence.zip",
    }
    assert expected.issubset({path.name for path in output.glob("*.zip")})
    for path in output.glob("*.zip"):
        with zipfile.ZipFile(path) as archive:
            assert archive.testzip() is None
    with zipfile.ZipFile(
        output / "AlphaPilot-V13.27.1.17-event-and-return-evidence.zip"
    ) as archive:
        assert "not_run_manifest.json" in archive.namelist()
        assert not any(name.endswith(".parquet") for name in archive.namelist())

    scan = json.loads((output / "sensitive_information_scan.json").read_text("utf-8"))
    assert scan["sensitiveHitCount"] == 0


def test_delivery_text_artifacts_use_canonical_lf_line_endings(tmp_path: Path) -> None:
    output = _build(tmp_path)

    crlf_files = [
        path.relative_to(output).as_posix()
        for path in output.rglob("*")
        if path.is_file()
        and path.suffix.lower() not in {".zip", ".parquet", ".feather"}
        and b"\r\n" in path.read_bytes()
    ]
    integrity = json.loads((output / "integrity_verification.json").read_text("utf-8"))

    assert crlf_files == []
    assert integrity["crlfFiles"] == []
    assert integrity["passed"] is True
