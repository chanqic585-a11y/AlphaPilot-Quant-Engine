from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import numpy as np
import pandas as pd

from alphapilot.reference_strategy_research.candidates import build_selected_candidates
from alphapilot.scripts.run_v37c_reference_strategy_parity_audit import (
    run_v37c_reference_strategy_parity_audit,
)


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _canonical_hash(value: dict, excluded: str) -> str:
    payload = {key: item for key, item in value.items() if key != excluded}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _package(tmp_path: Path) -> Path:
    candidates = [
        {
            "schemaVersion": "alphapilot_reference_candidate_v1",
            "candidateId": "ref_utc_session_range_breakout_1h_v1",
            "familyId": "utc_session_range_breakout",
            "timeframe": "1h",
            "directions": ["long", "short"],
            "implementationReadiness": "ready_for_bounded_prefilter",
            "marketHypothesis": "UTC range repricing.",
            "initialStopMayWiden": False,
            "derivation": {
                "type": "source_backed_clean_room_port",
                "sourceFiles": ["source_ea.mq4"],
            },
        },
        {
            "schemaVersion": "alphapilot_reference_candidate_v1",
            "candidateId": "ref_pa_breakout_failure_second_entry_4h_v1",
            "familyId": "price_action_breakout_failure_second_entry",
            "timeframe": "4h",
            "directions": ["long", "short"],
            "implementationReadiness": "ready_after_deterministic_normalization",
            "marketHypothesis": "Second failed breakout.",
            "initialStopMayWiden": False,
            "derivation": {
                "type": "documentation_normalization",
                "sourceFiles": ["second_entry.txt", "breakout_failure.txt"],
            },
        },
    ]
    for candidate in candidates:
        candidate["candidateSpecHash"] = _canonical_hash(candidate, "candidateSpecHash")
    candidate_set = {
        "schemaVersion": "alphapilot_reference_strategy_candidate_set_v1",
        "sourceArchiveSha256": "a" * 64,
        "candidateCount": len(candidates),
        "candidates": candidates,
    }
    payloads = {
        "candidates/candidate_specs.json": json.dumps(
            candidate_set, ensure_ascii=False, indent=2
        ).encode("utf-8"),
        "references/mql_sources/source_ea.mq4": (
            b"extern int LookBackHrs=2; extern int BreakEven=20; "
            b"OrderSend(Symbol(),OP_BUYSTOP,1,1,1,1,1); "
            b"OrderSend(Symbol(),OP_SELLSTOP,1,1,1,1,1);"
        ),
        "references/price_action_docs/second_entry.txt": b"contextual second entry",
        "references/price_action_docs/breakout_failure.txt": b"contextual failure",
    }
    files = [
        {
            "path": name,
            "sizeBytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for name, payload in payloads.items()
    ]
    manifest = {
        "schemaVersion": "alphapilot_reference_strategy_package_manifest_v1",
        "sourceArchive": "source.zip",
        "sourceArchiveSha256": "a" * 64,
        "candidateCount": len(candidates),
        "fileCount": len(files),
        "files": files,
    }
    manifest["manifestHash"] = _canonical_hash(manifest, "manifestHash")
    output = tmp_path / "reference.zip"
    root = "AlphaPilot_Reference_Strategy_Extraction_Package"
    with zipfile.ZipFile(output, "w") as archive:
        for name, payload in payloads.items():
            archive.writestr(f"{root}/{name}", payload)
        archive.writestr(
            f"{root}/package_manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    return output


def _frame(timeframe: str) -> pd.DataFrame:
    periods = 72 if timeframe == "1h" else 60
    return pd.DataFrame(
        {
            "date": pd.date_range(
                "2024-01-01T00:00:00Z",
                periods=periods,
                freq="1h" if timeframe == "1h" else "4h",
            ),
            "open": np.full(periods, 100.0),
            "high": np.full(periods, 101.0),
            "low": np.full(periods, 99.0),
            "close": np.full(periods, 100.0),
            "volume": np.full(periods, 1000.0),
        }
    )


def _prepare_frozen_inputs(repo: Path, package: Path) -> Path:
    source_repo = Path(__file__).resolve().parents[2]
    prereg = json.loads(
        (
            source_repo
            / "research/preregistrations/phase3c_campaign_0771c65b9b280dafdc0f6d835a92e8f96f1059e121d262ca0000b6b3f0513980.json"
        ).read_text(encoding="utf-8")
    )
    campaign_id = prereg["campaignId"]
    prereg_path = repo / "research" / "preregistrations" / f"{campaign_id}.json"
    _write_json(prereg_path, prereg)

    data_rows = []
    for timeframe in ("1h", "4h"):
        data_path = repo / "data" / f"BTC-USDT-SWAP-{timeframe}.parquet"
        data_path.parent.mkdir(parents=True, exist_ok=True)
        _frame(timeframe).to_parquet(data_path, index=False)
        data_rows.append(
            {
                "datasetId": f"fixture_BTC-USDT-SWAP_{timeframe}",
                "dataType": "ohlcv",
                "timeframe": timeframe,
                "symbols": ["BTC-USDT-SWAP"],
                "sourcePath": str(data_path),
                "contentHash": _hash(data_path),
                "provider": "test_fixture",
                "exchange": "test_fixture",
                "isProxy": True,
                "isPointInTime": False,
            }
        )
    _write_json(
        repo / "reports/backtest_screening/data_readiness/dataset_catalog.json",
        {"dataManifestHash": "fixture_catalog", "datasets": data_rows},
    )

    package_candidates = json.loads(
        zipfile.ZipFile(package).read(
            "AlphaPilot_Reference_Strategy_Extraction_Package/candidates/candidate_specs.json"
        )
    )["candidates"]
    selected = [row.to_dict() for row in build_selected_candidates(package_candidates)]
    run_dir = repo / "reports/backtest_screening/reference_strategy_research/v37b-fixture"
    selected_path = run_dir / "selected_candidates.json"
    _write_json(selected_path, {"candidates": selected})
    _write_json(
        run_dir / "source_verification.json",
        {"archiveSha256": _hash(package), "runId": "v37b-fixture"},
    )
    implementation = {
        "codeCommit": "f" * 40,
        "selectedCandidatesSha256": _hash(selected_path),
        "sourceHashes": prereg["implementationSourceHashes"],
    }
    _write_json(run_dir / "implementation_evidence.json", implementation)
    _write_json(run_dir / "campaign_start.json", {"campaignId": campaign_id})
    manifest_rows = []
    for name in (
        "source_verification.json",
        "selected_candidates.json",
        "implementation_evidence.json",
        "campaign_start.json",
    ):
        path = run_dir / name
        manifest_rows.append(
            {"path": str(path.relative_to(repo)).replace("\\", "/"), "sha256": _hash(path)}
        )
    _write_json(run_dir / "workflow_artifact_manifest.json", {"artifacts": manifest_rows})

    campaign = repo / "reports" / "backtest_screening" / campaign_id
    candidate_results = pd.DataFrame(
        [
            {
                "candidateId": selected[0]["candidateId"],
                "prescreenPassed": True,
                "basePassed": False,
                "formalPassed": False,
                "freqtradeTranslationPassed": False,
                "gates": json.dumps({"basePassed": False}),
                "failureLabels": json.dumps(["freqtrade_translation_not_executed"]),
            }
        ]
    )
    campaign.mkdir(parents=True, exist_ok=True)
    candidate_results.to_parquet(campaign / "candidate_results.parquet", index=False)
    _write_json(
        campaign / "campaign_summary.json",
        {"candidateCount": 4, "prescreenPassCount": 1, "basePassCount": 0, "formalPassCount": 0},
    )
    _write_json(campaign / "gate_matrix.json", {"candidates": {}})
    _write_json(campaign / "failure_attribution.json", {"failures": []})
    campaign_manifest = []
    for path in sorted(campaign.iterdir()):
        if path.name != "artifact_manifest.json":
            campaign_manifest.append({"path": path.name, "sha256": _hash(path)})
    _write_json(campaign / "artifact_manifest.json", {"artifacts": campaign_manifest})
    return run_dir


def test_v37c_runner_builds_hash_checked_offline_audit_bundle(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    package = _package(tmp_path)
    run_dir = _prepare_frozen_inputs(repo, package)

    result = run_v37c_reference_strategy_parity_audit(
        repo_root=repo,
        package_path=package,
        v37b_run_dir=run_dir,
    )

    output = Path(result["output"])
    signal_report = json.loads((output / "signal_parity_report.json").read_text("utf-8"))
    gate_report = json.loads((output / "gate_reachability_report.json").read_text("utf-8"))
    reassessment = json.loads((output / "v37b_reassessment.json").read_text("utf-8"))
    manifest = json.loads((output / "artifact_manifest.json").read_text("utf-8"))

    assert result["status"] == "completed"
    assert signal_report["allParityPassed"] is True
    assert len(signal_report["syntheticFixtures"]) == 4
    assert len(signal_report["registeredRealFixtures"]) == 4
    assert gate_report["allGatesReachable"] is True
    assert reassessment["forcedWinner"] is False
    assert reassessment["candidates"][0]["correctedFailureLabels"] == [
        "freqtrade_translation_not_executed",
        "out_of_sample_failed",
    ]
    for row in manifest["artifacts"]:
        assert _hash(output / row["path"]) == row["sha256"]
