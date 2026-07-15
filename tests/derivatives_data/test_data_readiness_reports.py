from __future__ import annotations

import hashlib
import json
from pathlib import Path

from alphapilot.derivatives_data.data_readiness_reports import (
    generate_data_readiness_reports,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_report_bundle_is_fail_closed_and_preserves_source_evidence(tmp_path) -> None:
    repo = tmp_path / "repo"
    external = tmp_path / "external"
    (repo / "reports").mkdir(parents=True)
    (repo / "research" / "data_snapshots").mkdir(parents=True)
    (external / "manifests").mkdir(parents=True)
    source = external / "funding.json"
    source.write_text('[{"fundingTime":1,"fundingRate":"0.1"}]\n', encoding="utf-8")
    catalog = {
        "dataManifestHash": "catalog-hash",
        "datasets": [
            {
                "datasetId": "funding-btc",
                "exchange": "binance",
                "provider": "binance_public_rest",
                "dataType": "funding",
                "sourcePath": str(source),
                "contentHash": _sha256(source),
                "rowCount": 1,
                "symbols": ["BTCUSDT"],
                "timeframe": None,
                "startTime": "2026-01-01T00:00:00Z",
                "endTime": "2026-01-01T08:00:00Z",
                "isProxy": False,
                "isPointInTime": True,
            }
        ],
    }
    (external / "manifests" / "phase3b_dataset_catalog.json").write_text(
        json.dumps(catalog), encoding="utf-8"
    )
    (external / "manifests" / "phase3b_data_source_audit.json").write_text(
        json.dumps({"schemaVersion": "fixture", "sources": []}), encoding="utf-8"
    )
    lock = repo / "requirements-data.txt"
    lock.write_text("pandas==3.0.1\nnumpy==2.3.5\npyarrow==24.0.0\n", encoding="utf-8")

    def command_output(command: str, _cwd=None) -> str:
        return {
            "git rev-parse HEAD": "abc123",
            "docker --version": "Docker version 29.6.1",
            "docker image inspect freqtradeorg/freqtrade:stable --format {{.Id}}": "sha256:image",
            "python -m pip freeze --all": "numpy==2.3.5\npandas==3.0.1\npyarrow==24.0.0",
            "python -m freqtrade --version": "freqtrade 2026.6",
        }[command]

    result = generate_data_readiness_reports(
        repo_root=repo,
        external_data_root=external,
        checked_at="2026-07-16T00:00:00Z",
        command_output=command_output,
        python_executable="python",
        public_probe=lambda url: {"url": url, "ok": True, "statusCode": 200},
        free_disk_bytes=50_000_000_000,
    )

    assert result["status"] == "data_not_ready"
    assert result["campaignMayRun"] is False
    assert result["formalReadyDirectionCount"] == 0
    assert result["sourceFileCount"] == 1
    assert result["sourceHashMismatchCount"] == 0
    assert (repo / "reports" / "derivatives_data" / "api_capability_audit.json").exists()
    assert (repo / "reports" / "derivatives_data" / "api_capability_audit.csv").exists()
    assert (repo / "reports" / "derivatives_data" / "api_capability_audit.parquet").exists()
    assert (repo / "reports" / "derivatives_data" / "data_readiness.json.sha256").exists()
    assert (repo / "reports" / "derivatives_data" / "exchange_alignment.json").exists()
    assert (repo / "reports" / "derivatives_data" / "pit_universe_manifest.json").exists()
    assert (repo / "reports" / "research_factory_repair" / "campaign_stop_decision.json").exists()
    stop_decision = json.loads(
        (
            repo
            / "reports"
            / "research_factory_repair"
            / "campaign_stop_decision.json"
        ).read_text(encoding="utf-8")
    )
    assert stop_decision["campaignStarted"] is False
    assert stop_decision["holdoutUnlocked"] is False
    assert stop_decision["reason"] == "fewer_than_two_formal_data_ready_directions"
    artifact_manifest = json.loads(
        (repo / "reports" / "derivatives_data" / "artifact_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert {
        "apiCapabilityAudit",
        "dataSourceRegistry",
        "dataManifest",
        "dataReadiness",
        "dataReadinessSummary",
        "deduplicationReport",
        "gapRepairReport",
        "downloadResumeManifest",
        "environmentLimitAudit",
        "dataAudit",
        "exchangeAlignment",
        "pitUniverseManifest",
        "environmentManifest",
        "dataSnapshot",
        "campaignStopDecision",
    } <= artifact_manifest["artifacts"].keys()
    assert (repo / "reports" / "reproducibility" / "environment_manifest.json").exists()
    snapshot = Path(result["dataSnapshotPath"])
    assert snapshot.exists()
    snapshot_payload = json.loads(snapshot.read_text(encoding="utf-8"))
    assert snapshot_payload["immutable"] is True
    assert snapshot_payload["campaignEligible"] is False
