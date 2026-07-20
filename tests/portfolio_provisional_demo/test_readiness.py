from __future__ import annotations

from alphapilot.portfolio_provisional_demo.readiness import (
    build_engineering_smoke_compatibility_audit,
    build_exact_release_approval_request,
    build_pre_arm_readiness,
)


def _release() -> dict:
    return {
        "releaseId": "release-new",
        "releaseHash": "release-hash-new",
        "riskOverlayHash": "risk-hash",
        "executionIntersectionHash": "intersection-hash",
        "executionInstruments": [
            "BTC-USDT-SWAP",
            "DOGE-USDT-SWAP",
            "ETH-USDT-SWAP",
            "SOL-USDT-SWAP",
            "XRP-USDT-SWAP",
        ],
        "approved": False,
        "demoArm": False,
    }


def _base_inputs() -> dict:
    return {
        "release": _release(),
        "cooldown_audit": {"status": "passed"},
        "binding_audit": {
            "status": "passed",
            "allRequiredBindingsPresent": True,
            "transitiveHashChainVerified": True,
        },
        "remote_freeze_receipt": {"status": "verified", "remoteVerified": True},
        "targeted_test_summary": {"status": "passed"},
        "test_exception_audit": {
            "status": "accepted_pre_existing_exception",
            "introducedByThisPatch": False,
            "executionPathImpact": False,
        },
        "private_read_audit": {
            "status": "verified",
            "privateReadVerified": True,
            "executionIntersectionHashMatches": True,
            "verifiedInstruments": _release()["executionInstruments"],
        },
        "generated_at": "2026-07-20T00:00:00Z",
    }


def test_missing_engineering_smoke_stops_at_separate_approval_gate() -> None:
    smoke = build_engineering_smoke_compatibility_audit(
        smoke_contract={"status": "not_run"},
        cancel_audit={"status": "not_run"},
        fill_close_audit={"status": "not_run"},
        restart_audit={"status": "not_run"},
        reconciliation_audit={"status": "not_run"},
        private_websocket_audit={"status": "not_run"},
        kill_switch_audit={"status": "not_run"},
        final_self_check={"status": "not_run"},
        evidence_isolation_audit={
            "status": "completed",
            "strategyEvidenceChanged": False,
        },
        generated_at="2026-07-20T00:00:00Z",
    )
    readiness = build_pre_arm_readiness(
        **_base_inputs(), engineering_smoke_audit=smoke
    )

    assert smoke["engineeringSmokeReady"] is False
    assert readiness["approvalReady"] is False
    assert readiness["route"] == "waiting_engineering_smoke_approval"
    assert readiness["demoArm"] is False
    assert readiness["orderCount"] == 0


def test_exact_release_request_binds_smoke_and_stops_without_arm() -> None:
    readiness = build_pre_arm_readiness(
        **_base_inputs(),
        engineering_smoke_audit={
            "status": "compatible",
            "engineeringSmokeReady": True,
            "evidenceHash": "completed-smoke-hash",
        },
    )

    request = build_exact_release_approval_request(
        release=_release(),
        readiness=readiness,
        smoke_audit={
            "engineeringSmokeReady": True,
            "evidenceHash": "completed-smoke-hash",
        },
        smoke_contract={"contractHash": "smoke-contract-hash"},
        generated_at="2026-07-20T01:00:00Z",
    )

    assert request["status"] == "blocked_waiting_exact_release_approval"
    assert request["releaseHash"] == "release-hash-new"
    assert request["riskOverlayHash"] == "risk-hash"
    assert request["executionIntersectionHash"] == "intersection-hash"
    assert request["engineeringSmokeEvidenceHash"] == "completed-smoke-hash"
    assert request["engineeringSmokeContractHash"] == "smoke-contract-hash"
    assert request["approvalGranted"] is False
    assert request["approved"] is False
    assert request["demoArm"] is False
    assert request["orderCount"] == 0
    assert request["live"] is False
    assert request["withdraw"] is False
    assert "release-hash-new" in request["approvalChallenge"]
    assert readiness["approved"] is False
    assert readiness["live"] is False
    assert readiness["withdraw"] is False


def test_all_hard_checks_ready_stops_at_exact_release_approval() -> None:
    smoke = {
        "status": "compatible",
        "engineeringSmokeReady": True,
        "evidenceHash": "smoke-hash",
    }
    readiness = build_pre_arm_readiness(
        **_base_inputs(), engineering_smoke_audit=smoke
    )

    assert readiness["approvalReady"] is True
    assert readiness["route"] == "blocked_waiting_exact_release_approval"
    assert readiness["demoArm"] is False
    assert readiness["orderCount"] == 0


def test_frozen_cooldown_semantics_are_verified_without_mutating_artifact() -> None:
    inputs = _base_inputs()
    inputs["cooldown_audit"] = {
        "schemaVersion": "portfolio_cooldown_semantics_v2",
        "pairCooldownDays": 14,
        "durationSeconds": 1_209_600,
        "cooldownDurationSeconds": 1_209_600,
        "notAWaitingPeriod": True,
        "cooldownScope": "canonical_instrument_id",
        "cooldownAnchor": "previous_accepted_closed_trade_exit_timestamp",
        "cooldownSemanticsHash": "frozen-semantics-hash",
        "implementationSha256": "frozen-implementation-sha256",
    }
    readiness = build_pre_arm_readiness(
        **inputs,
        engineering_smoke_audit={
            "status": "compatible",
            "engineeringSmokeReady": True,
            "evidenceHash": "smoke-hash",
        },
    )

    assert readiness["cooldownSemanticParity"] is True
    assert readiness["approvalReady"] is True
