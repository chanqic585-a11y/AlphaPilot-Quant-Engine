from __future__ import annotations

import json
from pathlib import Path

from alphapilot.reports.candidate_evidence_closure_schema import VALIDATION_OUTPUTS
from alphapilot.reports.generate_candidate_evidence_closure_report import (
    build_validation_artifacts,
    write_preregistration_prompt_aliases,
    write_generated_evidence_files,
    write_validation_artifacts,
)


def _candidate_result() -> dict:
    return {
        "strategyVersionId": "candidate-a",
        "strategyFamily": "family-a",
        "displayLabelZh": "候选 A",
        "tier": "A",
        "timeframe": "1h",
        "direction": "long",
        "prefilter": {"passed": True},
        "signalLayer": {
            "summary": {"tradeCount": 100, "profitFactor": 1.2, "averageNetR": 0.1},
            "bootstrap": {"probabilityAverageNetRPositive": 0.95},
            "multipleTestingRawP": 0.05,
            "multipleTestingAdjustedP": 0.05,
        },
        "lockedSample": {"diagnosticOnly": True, "sampleAssessment": {"passed": True}},
        "walkForward": {"positiveAverageNetRFoldCount": 1},
        "costStress": {"scenarios": {}},
        "riskModels": {"model_1": {"maximumDrawdownPct": 4.0}},
        "monteCarlo": {"model_1": {"maximumDrawdownPct": {"p95": 8.0}}},
        "baselines": {"noTrade": {"returnPct": 0.0}},
        "gates": {"cleanLockedSampleAvailable": False},
        "decision": {
            "status": "locked_sample_unavailable",
            "displayStatusZh": "锁定样本不可用",
            "hardPass": False,
        },
        "executionEligibility": {
            "executionEligible": False,
            "dryRunApproved": False,
            "demoApproved": False,
            "liveTradingApproved": False,
        },
    }


def test_artifact_writer_creates_complete_research_only_output_set(tmp_path: Path) -> None:
    preregistration = {
        "createdAt": "2026-07-15T00:00:00Z",
        "preRegistrationHash": "locked-hash",
        "costModel": {"id": "cost-model"},
        "riskModels": {"model_1": {"role": "primary_acceptance"}},
        "recommendationLimit": 2,
        "environmentFingerprint": {"python": "3.12"},
    }
    evidence = {
        "candidate-a": {
            "strategyVersionId": "candidate-a",
            "validationManifestHash": "manifest-hash",
            "reportSha256": "report-hash",
            "dataSnapshotHash": "snapshot-hash",
            "historicalPointInTimeUniverse": False,
            "cleanLockedSampleAvailable": False,
        }
    }
    artifacts = build_validation_artifacts(
        preregistration=preregistration,
        candidate_results=[_candidate_result()],
        evidence_records=evidence,
        portfolio_risk={"candidateCount": 1},
    )
    write_validation_artifacts(tmp_path, artifacts)

    assert set(VALIDATION_OUTPUTS).issubset(artifacts)
    for relative in VALIDATION_OUTPUTS.values():
        assert (tmp_path / relative).is_file(), relative
    closure = json.loads(
        (tmp_path / VALIDATION_OUTPUTS["closure"]).read_text(encoding="utf-8")
    )
    recommendations = json.loads(
        (tmp_path / VALIDATION_OUTPUTS["recommendations"]).read_text(encoding="utf-8")
    )
    assert closure["summary"]["passedCount"] == 0
    assert closure["safetyBoundary"]["executionEligibilityGranted"] is False
    assert recommendations["recommendationCount"] == 0
    assert "无候选通过" in (tmp_path / VALIDATION_OUTPUTS["summary"]).read_text(
        encoding="utf-8"
    )


def test_generated_evidence_writer_records_hashes_samples_and_rows(tmp_path: Path) -> None:
    preregistration = {
        "preRegistrationHash": "locked-hash",
        "resourceLimits": {"monteCarloDraws": 5},
        "seedRegistry": {"monteCarlo": 100},
        "riskModels": {
            "model_0": {"role": "signal_normalization_only"},
            "model_1": {
                "role": "primary_acceptance",
                "riskPerTradePct": 0.25,
                "drawdownResearchStopPct": 12.0,
            },
        },
        "candidates": [
            {
                "strategyVersionId": "candidate-a",
                "displayLabelZh": "候选 A",
            }
        ],
    }
    candidate_trades = {
        "candidate-a": [
            {
                "entryTimestampMs": 2,
                "exitTimestampMs": 3,
                "instrumentId": "ETH-USDT-SWAP",
                "netR": -0.5,
            },
            {
                "entryTimestampMs": 1,
                "exitTimestampMs": 2,
                "instrumentId": "BTC-USDT-SWAP",
                "netR": 1.0,
            },
        ]
    }
    candidate_results = [
        {
            "strategyVersionId": "candidate-a",
            "prefilter": {"passed": True},
            "monteCarlo": {"model_1": {"draws": 5}},
        }
    ]

    manifest = write_generated_evidence_files(
        tmp_path,
        preregistration=preregistration,
        candidate_trades=candidate_trades,
        candidate_results=candidate_results,
    )

    assert manifest["tradeRows"]["rowCount"] == 2
    assert manifest["monteCarloSamples"]["rowCount"] == 5
    assert len(manifest["tradeRows"]["sample"]) == 2
    assert len(manifest["monteCarloSamples"]["sample"]) == 3
    for key in ("tradeRows", "monteCarloSamples"):
        path = tmp_path / manifest[key]["path"]
        assert path.is_file()
        assert len(manifest[key]["sha256"]) == 64


def test_preregistration_prompt_aliases_preserve_locked_payloads(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    reports.mkdir()
    queue = {"schemaVersion": "queue-v1", "candidateVersionCount": 8}
    deduplication = {"canonical_representative_count": 7}
    (reports / "candidate_validation_queue.json").write_text(
        json.dumps(queue), encoding="utf-8"
    )
    (reports / "candidate_deduplication_report.json").write_text(
        json.dumps(deduplication), encoding="utf-8"
    )

    write_preregistration_prompt_aliases(tmp_path)

    assert json.loads(
        (reports / "candidate_evidence_closure_candidate_queue.json").read_text(
            encoding="utf-8"
        )
    ) == queue
    assert json.loads(
        (reports / "candidate_evidence_closure_deduplication.json").read_text(
            encoding="utf-8"
        )
    ) == deduplication
