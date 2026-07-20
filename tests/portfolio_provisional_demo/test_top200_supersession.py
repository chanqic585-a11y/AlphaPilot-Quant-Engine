from __future__ import annotations

from copy import deepcopy

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.portfolio_provisional_demo.top200_supersession import (
    build_top200_supersession_bundle,
    write_top200_supersession_bundle,
)


def _old_release() -> dict[str, object]:
    identity_core = {
        "schemaVersion": "provisional_demo_execution_identity_v1",
        "componentIdentities": [
            {
                "candidateId": "short_1h",
                "strategyDefinitionHash": "definition_short",
                "sourceContractHash": "contract_short",
                "sourceReleaseHash": "source_release_short",
            },
            {
                "candidateId": "mean_reversion_1d",
                "strategyDefinitionHash": "definition_mean_reversion",
                "sourceContractHash": "contract_mean_reversion",
                "sourceReleaseHash": "source_release_mean_reversion",
            },
            {
                "candidateId": "breakout_1d",
                "strategyDefinitionHash": "definition_breakout",
                "sourceContractHash": "contract_breakout",
                "sourceReleaseHash": "source_release_breakout",
            },
        ],
        "portfolioDefinitionHash": "portfolio_definition_hash",
        "cooldownSemanticsHash": "cooldown_hash",
        "quantImplementationCommit": "a" * 40,
        "consoleExecutionCommit": "b" * 40,
        "quantRuntimeImplementationHash": "quant_runtime_hash",
        "consoleRuntimeImplementationHash": "console_runtime_hash",
        "candidatePortfolioRuntimeHash": "candidate_runtime_hash",
        "exitPolicyHash": "exit_policy_hash",
        "riskProfileHash": "risk_profile_hash",
        "riskOverlayHash": "risk_overlay_hash",
        "researchUniverseHash": "research_universe_hash",
        "publicUniverseSnapshotHash": "old_public_hash",
        "authenticatedDemoUniverseHash": "old_authenticated_hash",
        "confirmedRuntimeUniverseHash": "old_runtime_hash",
        "executionIntersectionHash": "old_intersection_hash",
        "costModelHash": "cost_model_hash",
        "evidenceClassification": {
            "historicalEvidenceClass": "development_selected_result",
            "strategyQualification": "provisional_research_only",
            "formalPass": False,
        },
    }
    identity = {
        **identity_core,
        "executionIdentityHash": stable_hash(
            identity_core, prefix="provisional_demo_execution_identity"
        ),
    }
    release_core = {
        "schemaVersion": "provisional_research_demo_v1",
        "releaseId": "provisional_research_demo_v46_old",
        "releasePurpose": "provisional_research_demo",
        "evidenceClass": "historical_selected_forward_collection",
        "historicalEvidenceClass": "development_selected_result",
        "forwardEvidenceStatus": "collecting",
        "strategyQualification": "provisional_research_only",
        "formalPass": False,
        "cleanHistoricalOosPass": False,
        "livePromotionEligible": False,
        "automaticLivePromotionAllowed": False,
        "approvalRequired": True,
        "approved": False,
        "demoArm": False,
        "route": "blocked_waiting_exact_release_approval",
        "portfolioCandidateId": "portfolio_candidate",
        "portfolioDefinitionHash": "portfolio_definition_hash",
        "componentIds": ["short_1h", "mean_reversion_1d", "breakout_1d"],
        "riskOverlayHash": "risk_overlay_hash",
        "executionIntersectionHash": "old_intersection_hash",
        "executionInstruments": ["BTC-USDT-SWAP"],
        "executionIdentity": identity,
        "executionIdentityHash": identity["executionIdentityHash"],
        "historicalMetrics": {"profitFactor": 1.4, "expectancyR": 0.2},
        "additionalCostStress0_10R": {"profitFactor": 1.2},
        "replayParityPercent": 100.0,
        "generatedAt": "2026-07-20T00:00:00Z",
    }
    return {
        **release_core,
        "releaseHash": stable_hash(release_core, prefix="provisional_demo_release"),
    }


def _policy() -> dict[str, object]:
    core = {
        "schemaVersion": "okx_demo_top200_universe_policy_v1",
        "policyId": "okx_demo_top200_liquid_usdt_swap_forward_v1",
        "maximumInstrumentCount": 200,
        "refreshCadence": "daily_frozen_snapshot",
        "rankingMetric": "medianDailyQuoteTurnover",
        "resultBasedSelectionAllowed": False,
    }
    return {**core, "policyHash": stable_hash(core, prefix="top200_universe_policy")}


def _snapshot(policy: dict[str, object]) -> dict[str, object]:
    return {
        "schemaVersion": "okx_demo_top200_universe_snapshot_v1",
        "utcDate": "2026-07-20",
        "policyId": policy["policyId"],
        "policyHash": policy["policyHash"],
        "maximumInstrumentCount": 200,
        "actualInstrumentCount": 3,
        "instrumentIds": [
            "ETH-USDT-SWAP",
            "BTC-USDT-SWAP",
            "SOL-USDT-SWAP",
        ],
        "status": "ready",
        "snapshotHash": "demo_top200_universe_snapshot_test",
    }


def test_top200_supersession_is_additive_unapproved_and_hash_bound() -> None:
    old_release = _old_release()
    original = deepcopy(old_release)
    policy = _policy()
    snapshot = _snapshot(policy)

    bundle = build_top200_supersession_bundle(
        old_release=old_release,
        policy=policy,
        snapshot=snapshot,
        risk_overlay={"riskOverlayHash": "risk_overlay_hash"},
        engineering_smoke_audit={
            "engineeringSmokeReady": True,
            "evidenceHash": "engineering_smoke_evidence_hash",
        },
        engineering_smoke_contract={"contractHash": "smoke_contract_hash"},
        quant_implementation_commit="c" * 40,
        console_execution_commit="d" * 40,
        quant_runtime_implementation_hash="quant_top200_runtime_hash",
        console_runtime_implementation_hash="console_top200_runtime_hash",
        generated_at="2026-07-20T18:00:00Z",
    )

    assert old_release == original
    release = bundle["supersedingRelease"]
    assert release["releaseId"] != old_release["releaseId"]
    assert release["releaseHash"] != old_release["releaseHash"]
    assert release["executionInstruments"] == snapshot["instrumentIds"]
    assert release["dynamicUniversePolicyHash"] == policy["policyHash"]
    assert release["dynamicUniverseSnapshotHash"] == snapshot["snapshotHash"]
    assert release["actualInstrumentCount"] == 3
    assert release["riskOverlayHash"] == old_release["riskOverlayHash"]
    assert release["historicalEvidenceClass"] == "development_selected_result"
    assert release["formalPass"] is False
    assert release["approved"] is False
    assert release["demoArm"] is False
    assert release["livePromotionEligible"] is False

    overlay = bundle["oldReleaseSupersessionOverlay"]
    assert overlay["oldReleaseStatus"] == "superseded_unapproved"
    assert overlay["oldReleaseHash"] == old_release["releaseHash"]
    assert overlay["supersedingReleaseHash"] == release["releaseHash"]

    request = bundle["approvalRequest"]
    assert request["releaseHash"] == release["releaseHash"]
    assert request["riskOverlayHash"] == "risk_overlay_hash"
    assert request["approvalGranted"] is False
    assert request["demoArm"] is False
    assert request["strategyOrderCount"] == 0
    assert request["route"] == "blocked_waiting_exact_release_approval"


def test_top200_supersession_rejects_mismatched_or_empty_snapshot() -> None:
    old_release = _old_release()
    policy = _policy()
    snapshot = _snapshot(policy)
    snapshot["policyHash"] = "wrong"

    try:
        build_top200_supersession_bundle(
            old_release=old_release,
            policy=policy,
            snapshot=snapshot,
            risk_overlay={"riskOverlayHash": "risk_overlay_hash"},
            engineering_smoke_audit={"engineeringSmokeReady": True},
            engineering_smoke_contract={"contractHash": "smoke_contract_hash"},
            quant_implementation_commit="c" * 40,
            console_execution_commit="d" * 40,
            quant_runtime_implementation_hash="quant_top200_runtime_hash",
            console_runtime_implementation_hash="console_top200_runtime_hash",
            generated_at="2026-07-20T18:00:00Z",
        )
    except ValueError as error:
        assert str(error) == "top200_snapshot_policy_mismatch"
    else:
        raise AssertionError("mismatched snapshot must fail closed")


def test_writer_uses_fixed_additive_artifact_names(tmp_path) -> None:
    old_release = _old_release()
    bundle = build_top200_supersession_bundle(
        old_release=old_release,
        policy=(policy := _policy()),
        snapshot=_snapshot(policy),
        risk_overlay={"riskOverlayHash": "risk_overlay_hash"},
        engineering_smoke_audit={
            "engineeringSmokeReady": True,
            "evidenceHash": "engineering_smoke_evidence_hash",
        },
        engineering_smoke_contract={"contractHash": "smoke_contract_hash"},
        quant_implementation_commit="c" * 40,
        console_execution_commit="d" * 40,
        quant_runtime_implementation_hash="quant_top200_runtime_hash",
        console_runtime_implementation_hash="console_top200_runtime_hash",
        generated_at="2026-07-20T18:00:00Z",
    )

    manifest = write_top200_supersession_bundle(tmp_path, bundle)

    assert manifest["artifactCount"] == 5
    assert {path.name for path in tmp_path.iterdir()} == {
        "superseding_provisional_release.json",
        "superseding_release_hash_audit.json",
        "superseding_demo_approval_request.json",
        "old_release_supersession_overlay.json",
        "top200_supersession_artifact_manifest.json",
    }
