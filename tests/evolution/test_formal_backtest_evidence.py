from __future__ import annotations

from copy import deepcopy

from alphapilot.evolution.promotion.formal_backtest_evidence import (
    validate_formal_backtest_evidence,
)
from alphapilot.evolution.registry.hashing import stable_hash


def preregistration() -> dict:
    candidate = {
        "candidateId": "candidate_1",
        "familyId": "family_1",
        "marketMechanismId": "mechanism_1",
        "definitionHash": "candidate_definition_1",
        "factorConfirmations": ["factor_hash_1"],
        "factorRanking": [],
        "factorVetoes": [],
    }
    return {
        "campaignId": "campaign_1",
        "preregistrationHash": "preregistration_1",
        "externalReferenceManifestHash": "external_refs_1",
        "dataSnapshotHash": "data_snapshot_1",
        "factorRegistryHash": "factor_registry_1",
        "factorShortlistHash": "factor_shortlist_1",
        "costScenarios": {"base": {"multiplier": 1.0}, "stress_1_5x": {"multiplier": 1.5}},
        "candidates": [candidate],
    }


def formal_evidence() -> dict:
    gate = {
        "samplePassed": True,
        "prescreenPassed": True,
        "basePassed": True,
        "formalPassed": True,
        "oosMetrics": {
            "profitFactor": 1.31,
            "averageNetR": 0.09,
            "maximumDrawdownPct": 11.0,
            "positiveFoldCount": 5,
            "folds": {f"fold_{index:03d}": {"profitFactor": 1.2} for index in range(1, 6)},
        },
        "stress1_5xMetrics": {"profitFactor": 1.12, "averageNetR": 0.04},
        "formalGates": {
            "holdoutAccessBeforeFinalEvaluation": {"observed": 0, "passed": True},
            "oosProfitFactor": {"observed": 1.31, "passed": True},
            "oosAverageNetR": {"observed": 0.09, "passed": True},
            "stress1_5xProfitFactor": {"observed": 1.12, "passed": True},
            "stress1_5xAverageNetR": {"observed": 0.04, "passed": True},
            "positiveFoldCount": {"observed": 5, "passed": True},
        },
    }
    return {
        "schemaVersion": "phase3c_formal_pass_evidence_v1",
        "formalPass": True,
        "campaignId": "campaign_1",
        "candidateId": "candidate_1",
        "candidateDefinitionHash": "candidate_definition_1",
        "externalReferenceManifestHash": "external_refs_1",
        "dataSnapshotHash": "data_snapshot_1",
        "factorRegistryHash": "factor_registry_1",
        "factorShortlistHash": "factor_shortlist_1",
        "factorDefinitionHashes": ["factor_hash_1"],
        "factorRoles": {"confirmation": ["factor_hash_1"], "ranking": [], "veto": []},
        "marketMechanismId": "mechanism_1",
        "preregistrationHash": "preregistration_1",
        "gateEvidence": gate,
        "formalGateHash": stable_hash(gate, prefix="formal_gate"),
    }


def test_complete_formal_evidence_passes() -> None:
    result = validate_formal_backtest_evidence(
        formal_evidence(),
        preregistration=preregistration(),
        campaign_summary={"campaignId": "campaign_1", "formalPassCount": 1},
        artifact_manifest={"campaignId": "campaign_1", "manifestHash": "artifacts_1"},
    )

    assert result.passed is True
    assert result.failedCheckIds == ()
    assert result.normalized["backtestReportHash"] == "artifacts_1"


def test_nonformal_or_changed_lineage_fails_closed() -> None:
    evidence = formal_evidence()
    evidence["formalPass"] = False
    evidence["factorRegistryHash"] = "changed"

    result = validate_formal_backtest_evidence(
        evidence,
        preregistration=preregistration(),
        campaign_summary={"campaignId": "campaign_1", "formalPassCount": 1},
        artifact_manifest={"campaignId": "campaign_1", "manifestHash": "artifacts_1"},
    )

    assert result.passed is False
    assert "formal_pass" in result.failedCheckIds
    assert "factor_registry_hash" in result.failedCheckIds


def test_local_shadow_or_engineering_counts_cannot_replace_formal_evidence() -> None:
    evidence = deepcopy(formal_evidence())
    evidence.pop("formalPass")
    evidence["shadowClosedSamples"] = 10_000
    evidence["engineeringSmokePassed"] = True

    result = validate_formal_backtest_evidence(
        evidence,
        preregistration=preregistration(),
        campaign_summary={"campaignId": "campaign_1", "formalPassCount": 1},
        artifact_manifest={"campaignId": "campaign_1", "manifestHash": "artifacts_1"},
    )

    assert result.passed is False
    assert result.failedCheckIds == ("formal_pass",)
