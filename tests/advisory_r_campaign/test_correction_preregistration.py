from __future__ import annotations

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.advisory_r_campaign.correction_preregistration import (
    build_correction_preregistration,
)


def test_correction_preregistration_changes_code_identity_only() -> None:
    candidates = build_candidate_inventory()
    original = {
        "campaignId": "original-campaign",
        "preregistrationHash": "original-prereg-hash",
        "snapshotId": "snapshot-1",
        "snapshotHash": "snapshot-hash",
        "exitPolicyBoundsHash": "bounds-hash",
        "representativeUniverse": {"instrumentIds": ["BTC-USDT-SWAP"]},
        "prefilterGates": {"minimumEvents": 30},
        "portfolioPrefilterGates": {"minimumHistoryMonths": 24},
        "routing": {"maximumSurvivors": 6},
        "experimentBudget": {"prefilterRuns": 1},
        "candidates": [
            {
                key: row[key]
                for key in (
                    "candidateId",
                    "familyId",
                    "variantId",
                    "timeframe",
                    "strategyType",
                    "diagnosticOnly",
                    "semanticFingerprint",
                    "strategyDefinitionHash",
                    "exitPolicy",
                    "exitPolicyHash",
                )
            }
            for row in candidates
        ],
    }

    corrected = build_correction_preregistration(
        original=original,
        candidates=candidates,
        code_commit="abc123",
        implementation_conformance_hash="conformance-hash",
        exit_policy_engine_hash="engine-hash",
        structure_rule_compiler_hash="structure-hash",
        benchmark_compiler_hash="benchmark-hash",
    )

    assert corrected["correctionOfCampaignId"] == "original-campaign"
    assert corrected["correctionReason"] == "implementation_nonconformance"
    assert corrected["parameterChanges"] == 0
    assert corrected["candidateChanges"] == 0
    assert corrected["gateChanges"] == 0
    assert corrected["universeChanges"] == 0
    assert corrected["costChanges"] == 0
    assert corrected["safetyBoundary"] == {
        "lockedOosAccessCount": 0,
        "formalEvidenceCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
