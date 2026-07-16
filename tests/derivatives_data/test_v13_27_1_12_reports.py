from __future__ import annotations

import hashlib
import json
from pathlib import Path

from alphapilot.derivatives_data.v13_27_1_12_reports import (
    generate_v13_27_1_12_reports,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_final_reports_fail_closed_without_running_research_or_execution(tmp_path) -> None:
    repo_root = tmp_path / "quant"
    data_root = tmp_path / "market-data"
    report_root = repo_root / "reports" / "v13_27_1_12"
    _write_json(
        report_root / "family_b_data_chain.json",
        {
            "status": "diagnostic_ready",
            "sameExchangeCoreChain": False,
            "missingDataTypes": ["basis", "open_interest", "perpetual_ohlcv"],
        },
    )
    _write_json(
        report_root / "pit_universe_audit.json",
        {
            "status": "unavailable",
            "historicalFormalReady": False,
            "medianInvestableContracts": 0,
            "freshHoldoutReady": False,
            "reason": "no_historical_point_in_time_membership_source",
        },
    )
    _write_json(
        report_root / "qlib_preflight.json",
        {
            "qlibCampaignMayRun": False,
            "modelCampaignRun": False,
            "blockers": [
                "c_formal_ready",
                "pit_median_at_least_30",
                "fresh_holdout_ready",
            ],
        },
    )
    _write_json(
        report_root / "snapshot_manifest.json",
        {
            "status": "frozen_data_only",
            "strategyTrialCount": 0,
            "holdoutAccessCount": 0,
            "snapshot": {
                "snapshotId": "derivatives_data_snapshot_test",
                "snapshotHash": "sha256:test",
                "containsStrategyResults": False,
                "containsHoldoutResults": False,
            },
        },
    )
    _write_json(
        report_root / "download_resume_manifest.json",
        {
            "status": "existing_data_scanned_no_download",
            "networkRequestCount": 0,
            "existingDataScan": {"partitionCount": 8},
        },
    )
    probes: list[str] = []

    def probe(url: str) -> dict[str, object]:
        probes.append(url)
        return {
            "url": url,
            "ok": True,
            "statusCode": 200,
            "responseBytes": 12,
            "responseSha256": "abc123",
        }

    result = generate_v13_27_1_12_reports(
        repo_root=repo_root,
        data_root=data_root,
        checked_at="2026-07-16T02:03:04Z",
        probe=probe,
    )

    assert probes
    assert result == {
        "status": "data_not_ready",
        "A1Status": "unavailable",
        "A2Status": "unavailable",
        "BStatus": "diagnostic_ready",
        "CStatus": "unavailable",
        "formalTopLevelDirectionCount": 0,
        "threeDirectionCampaignMayRun": False,
        "qlibCampaignMayRun": False,
        "strategyTrialCount": 0,
        "holdoutAccessCount": 0,
        "releaseCount": 0,
        "demoArmCount": 0,
        "orderCount": 0,
        "reportRoot": str(report_root),
    }

    readiness = json.loads((report_root / "data_readiness.json").read_text("utf-8"))
    campaign = json.loads(
        (report_root / "campaign_start_decision.json").read_text("utf-8")
    )
    qlib = json.loads((report_root / "qlib_start_decision.json").read_text("utf-8"))
    manifest = json.loads((report_root / "artifact_manifest.json").read_text("utf-8"))

    assert readiness["formalTopLevelDirectionCount"] == 0
    assert readiness["stressReversalFormalReady"] is False
    assert readiness["crossSectionalMomentumFormalReady"] is False
    assert campaign["campaignStarted"] is False
    assert campaign["strategyTrialCount"] == 0
    assert campaign["holdoutAccessCount"] == 0
    assert campaign["releaseCount"] == 0
    assert campaign["demoArmCount"] == 0
    assert campaign["orderCount"] == 0
    assert qlib["modelCampaignRun"] is False
    assert qlib["qlibCampaignMayRun"] is False
    assert manifest["artifactCount"] >= 8

    for path in sorted(report_root.glob("*")):
        if path.suffix not in {".json", ".csv", ".md"}:
            continue
        sidecar = path.with_name(path.name + ".sha256")
        assert sidecar.is_file(), path.name
        assert sidecar.read_text("ascii") == f"{_sha256(path)}  {path.name}\n"


def test_report_generation_rejects_missing_stage_evidence(tmp_path) -> None:
    repo_root = tmp_path / "quant"

    try:
        generate_v13_27_1_12_reports(
            repo_root=repo_root,
            data_root=tmp_path / "data",
            checked_at="2026-07-16T02:03:04Z",
            probe=lambda url: {"url": url, "ok": True},
        )
    except FileNotFoundError as exc:
        assert "family_b_data_chain.json" in str(exc)
    else:
        raise AssertionError("missing stage evidence must fail closed")


def test_report_generation_rejects_non_data_only_snapshot_before_writing(tmp_path) -> None:
    repo_root = tmp_path / "quant"
    report_root = repo_root / "reports" / "v13_27_1_12"
    _write_json(
        report_root / "family_b_data_chain.json",
        {"status": "diagnostic_ready", "sameExchangeCoreChain": False},
    )
    _write_json(
        report_root / "pit_universe_audit.json",
        {"status": "unavailable", "historicalFormalReady": False},
    )
    _write_json(
        report_root / "qlib_preflight.json",
        {"qlibCampaignMayRun": False, "blockers": []},
    )
    _write_json(
        report_root / "snapshot_manifest.json",
        {
            "snapshot": {
                "containsStrategyResults": True,
                "containsHoldoutResults": False,
            }
        },
    )
    _write_json(report_root / "download_resume_manifest.json", {})

    try:
        generate_v13_27_1_12_reports(
            repo_root=repo_root,
            data_root=tmp_path / "data",
            checked_at="2026-07-16T02:03:04Z",
            probe=lambda url: {"url": url, "ok": True},
        )
    except ValueError as exc:
        assert "not data-only" in str(exc)
    else:
        raise AssertionError("a non-data-only snapshot must fail closed")

    assert not (report_root / "data_readiness.json").exists()
