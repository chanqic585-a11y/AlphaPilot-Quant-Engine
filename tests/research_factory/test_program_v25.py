from __future__ import annotations

from alphapilot.research_factory.program_v25 import (
    build_capacity_semantics_clarification_sidecar,
    build_v25_route,
    publish_required_contract_artifacts,
)


def test_clarification_sidecar_reclassifies_without_economic_claim() -> None:
    sidecar = build_capacity_semantics_clarification_sidecar()

    assert sidecar["originalRoute"] == "capital_infeasible"
    assert sidecar["originalProgramRoute"] == "completed_zero_qualified_candidates"
    assert sidecar["economicResultValid"] is False
    assert sidecar["strategyPerformanceFailure"] is False
    assert sidecar["implementationFailure"] is False
    assert sidecar["dataContractFailure"] is True
    assert sidecar["clarifiedClassification"] == (
        "formal_data_blocked_capacity_semantics"
    )
    assert sidecar["clarifiedPrimaryReason"] == (
        "candidate_data_profile_not_compatible_with_mandatory_capital_policy_inputs"
    )
    assert sidecar["prefilterSurvivorStatus"] == (
        "frozen_prefilter_survivor_waiting_verified_capacity_profile"
    )


def test_v25_blocks_before_claim_when_frozen_ranking_semantics_are_missing() -> None:
    decision = build_v25_route(
        capacity_profile={"status": "ready", "profileHash": "profile-hash"},
        capacity_certification={
            "certificationStatus": "passed",
            "rawSignalCount": 1258,
            "capacityInputAvailableCount": 1258,
            "capacityCalculationCount": 1258,
            "capacityPassCount": 1258,
            "capacityRejectCount": 0,
            "economicResultReadCount": 0,
            "exitResultReadCount": 0,
            "statisticalResultReadCount": 0,
        },
        readiness={
            "signalReady": True,
            "formalReady": False,
            "demoReady": False,
            "missingFormalFields": [
                "eventExtremeResidualZ",
                "recoverySizeZ",
            ],
            "missingDemoFields": [
                "eventExtremeResidualZ",
                "recoverySizeZ",
                "instrument_id",
                "lot_size",
                "tick_size",
            ],
        },
        formal_gate={
            "status": "formal_data_blocked_before_claim",
            "claimPermitted": False,
            "formalRunBudgetConsumed": 0,
            "ledgerDelta": {
                "claimCount": 0,
                "attemptCount": 0,
                "resultCount": 0,
                "resultReadCount": 0,
            },
        },
        demo_gate={
            "status": "demo_data_blocked_before_release",
            "releaseEligible": False,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
        candidate_definition_diff_count=0,
        policy_gate_diff_count=0,
    )

    assert decision["v25Status"] == "completed_data_semantics_audit"
    assert decision["finalRoute"] == "formal_data_blocked_capacity_semantics"
    assert decision["primaryReason"] == "frozen_ranking_feature_semantics_unresolved"
    assert decision["v26Started"] is False
    assert decision["replayCampaignId"] is None
    assert decision["formalLedger"] == {
        "claimCount": 0,
        "attemptCount": 0,
        "resultCount": 0,
        "resultReadCount": 0,
    }
    assert decision["formalRunBudgetConsumed"] == 0
    assert decision["lockedOosReadCount"] == 0
    assert decision["releaseCount"] == 0
    assert decision["approvalCount"] == 0
    assert decision["demoArm"] is False
    assert decision["orderCount"] == 0
    assert decision["candidateDefinitionDiffCount"] == 0
    assert decision["policyGateDiffCount"] == 0


def test_required_contract_artifacts_use_authoritative_names(tmp_path) -> None:
    capital_dependencies = {"policyHash": "capacity-policy-hash"}
    exchange_audit = {"auditHash": "exchange-audit-hash"}

    publish_required_contract_artifacts(
        output_root=tmp_path,
        capital_dependencies=capital_dependencies,
        exchange_audit=exchange_audit,
    )

    assert (
        tmp_path / "capital_policy_data_dependencies.json"
    ).read_text(encoding="utf-8")
    assert (
        tmp_path / "exchange_identity_and_portability_audit.json"
    ).read_text(encoding="utf-8")
