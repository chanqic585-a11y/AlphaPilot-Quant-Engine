from __future__ import annotations

from pathlib import Path

import pytest

from alphapilot.advisory_r_campaign.corrected_reporting import (
    REQUIRED_REPORT_NAMES,
    build_correction_manifest,
    build_corrected_trial_ledger,
    verify_immutable_artifacts,
)


def test_corrected_report_contract_is_complete() -> None:
    assert REQUIRED_REPORT_NAMES == {
        "benchmark_comparison.json",
        "campaign_summary.json",
        "campaign_summary.md",
        "candidate_events.parquet",
        "conformance_matrix.csv",
        "conformance_matrix.json",
        "corrected_vs_v15_comparison.json",
        "correction_manifest.json",
        "event_schema.json",
        "exit_leg_parity.json",
        "exit_policy_attribution.json",
        "failure_attribution.json",
        "implementation_parity.json",
        "novelty_audit.json",
        "prefilter_gate_matrix.json",
        "prefilter_results.json",
        "route_decision.json",
        "simple_benchmarks.json",
        "strategy_inventory.json",
        "trial_ledger.csv",
        "trial_ledger.json",
    }


def test_immutable_artifact_verifier_fails_closed(tmp_path: Path) -> None:
    artifact = tmp_path / "frozen.json"
    artifact.write_text('{"frozen": true}\n', encoding="utf-8")
    baseline = verify_immutable_artifacts([artifact])
    artifact.write_text('{"frozen": false}\n', encoding="utf-8")

    with pytest.raises(RuntimeError, match="immutable V15 artifact hash mismatch"):
        verify_immutable_artifacts([artifact], baseline=baseline)


def test_correction_manifest_keeps_every_frozen_delta_at_zero() -> None:
    manifest = build_correction_manifest(
        correction_campaign_id="correction-1",
        original_campaign_id="v15",
        original_preregistration_hash="pre-hash",
        original_artifact_hashes={"a": "hash-a"},
        implementation_conformance_hash="implementation-hash",
        code_commit="abc123",
    )

    assert manifest["parameterChanges"] == 0
    assert manifest["candidateChanges"] == 0
    assert manifest["gateChanges"] == 0
    assert manifest["universeChanges"] == 0
    assert manifest["costChanges"] == 0
    assert manifest["safetyBoundary"] == {
        "lockedOosAccessCount": 0,
        "formalEvidenceCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def test_corrected_trial_ledger_preserves_original_attempts() -> None:
    original = {
        "trialLedgerHash": "old-hash",
        "trials": [
            {
                "trialId": "trial-1",
                "candidateId": "candidate-1",
                "resultsRead": True,
            }
        ],
    }
    corrected = build_corrected_trial_ledger(
        original,
        correction_campaign_id="correction-1",
    )

    assert corrected["originalTrialLedgerHash"] == "old-hash"
    assert corrected["trialCount"] == 2
    assert corrected["trials"][0]["trialId"] == "trial-1"
    assert corrected["trials"][1]["attemptType"] == "implementation_correction"
    assert corrected["trials"][1]["parentTrialId"] == "trial-1"
