from __future__ import annotations

import json
from pathlib import Path

from alphapilot.portfolio_provisional_demo.finalize_engineering_smoke import (
    finalize_engineering_smoke,
)


def _write(root: Path, name: str, payload: dict) -> None:
    (root / name).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def test_finalizer_requires_complete_smoke_and_writes_exact_approval_gate(tmp_path: Path) -> None:
    release = {
        "releaseId": "release-v46",
        "releaseHash": "release-hash-v46",
        "riskOverlayHash": "risk-hash-v46",
        "executionIntersectionHash": "intersection-hash-v46",
        "executionInstruments": ["BTC-USDT-SWAP"],
        "approved": False,
        "demoArm": False,
        "formalPass": False,
        "livePromotionEligible": False,
    }
    contract = {
        "status": "passed",
        "requestType": "engineering_smoke_only",
        "releaseId": "release-v46",
        "releaseHash": "release-hash-v46",
        "riskOverlayHash": "risk-hash-v46",
        "executionIntersectionHash": "intersection-hash-v46",
        "contractHash": "contract-hash-v46",
        "demoArm": False,
        "liveExecutionAllowed": False,
        "withdrawAllowed": False,
    }
    common_passed = {"status": "passed"}
    inputs = {
        "provisional_release.json": release,
        "engineering_smoke_contract.json": contract,
        "engineering_smoke_contract_hash_audit.json": {
            "status": "passed",
            "exactBindingsVerified": True,
            "contractHash": "contract-hash-v46",
        },
        "engineering_smoke_approval_overlay.json": {
            "status": "approved_engineering_smoke_only",
            "requestType": "engineering_smoke_only",
            "strategyReleaseApprovalAccepted": False,
            "demoArm": False,
            "live": False,
            "withdraw": False,
        },
        "engineering_smoke_private_preflight.json": {
            "status": "passed",
            "environment": "okx_demo",
            "demoHeaderRequired": True,
            "credentialsRetained": False,
            "rawResponsesRetained": False,
        },
        "engineering_smoke_cancel_audit.json": {
            "status": "passed",
            "finalOrderState": "canceled",
        },
        "engineering_smoke_fill_close_audit.json": {
            "status": "passed",
            "finalPositionSize": "0",
            "reduceOnlyClose": True,
            "orderAttemptCount": 3,
        },
        "engineering_smoke_restart_recovery_audit.json": common_passed,
        "engineering_smoke_rest_reconciliation_audit.json": {
            "status": "passed",
            "pendingOrderCount": 0,
            "nonzeroPositionCount": 0,
            "unknownOrderCount": 0,
            "orphanPositionCount": 0,
        },
        "engineering_smoke_private_websocket_audit.json": {
            "status": "passed",
            "authenticated": True,
            "subscribed": True,
            "credentialsRetained": False,
        },
        "engineering_smoke_kill_switch_audit.json": common_passed,
        "engineering_smoke_strategy_evidence_isolation_audit.json": {
            "status": "passed",
            "strategyEvidenceChanged": False,
            "strategyOrderCountDelta": 0,
            "strategyClosedTradeCountDelta": 0,
            "forwardEvidenceDelta": 0,
            "formalEvidenceDelta": 0,
        },
        "engineering_smoke_final_self_check.json": {
            "status": "passed",
            "engineeringSmokeReady": True,
            "releaseId": "release-v46",
            "releaseHash": "release-hash-v46",
            "riskOverlayHash": "risk-hash-v46",
            "executionIntersectionHash": "intersection-hash-v46",
            "contractHash": "contract-hash-v46",
            "duplicateOrderCount": 0,
            "orphanOrderCount": 0,
            "orphanPositionCount": 0,
            "unknownStateCount": 0,
            "finalPositionCount": 0,
            "strategyOrderCount": 0,
            "strategyClosedTradeCount": 0,
            "forwardEvidenceDelta": 0,
            "formalEvidenceDelta": 0,
            "demoArm": False,
            "live": False,
            "withdraw": False,
            "nextRoute": "blocked_waiting_exact_release_approval",
        },
        "v46_portfolio_cooldown_semantics_audit.json": {"status": "passed"},
        "provisional_release_binding_audit.json": {
            "status": "passed",
            "allRequiredBindingsPresent": True,
            "transitiveHashChainVerified": True,
        },
        "provisional_demo_remote_freeze_receipt.json": {
            "status": "verified",
            "remoteVerified": True,
        },
        "patch_test_summary.json": {"status": "passed"},
        "pre_existing_test_exception_audit.json": {
            "status": "accepted_pre_existing_exception",
            "introducedByThisPatch": False,
            "executionPathImpact": False,
        },
        "provisional_demo_pre_arm_private_read_audit.json": {
            "status": "verified",
            "privateReadVerified": True,
            "executionIntersectionHashMatches": True,
            "verifiedInstruments": ["BTC-USDT-SWAP"],
        },
    }
    for name, payload in inputs.items():
        _write(tmp_path, name, payload)
    (tmp_path / "engineering_smoke_order_ledger.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "engineeringOnly": True,
                    "strategyQualification": False,
                    "stage": stage,
                }
            )
            for stage in ("path_a", "path_b_open", "path_b_close")
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "engineering_smoke_fill_ledger.jsonl").write_text(
        "\n".join(
            json.dumps(
                {
                    "engineeringOnly": True,
                    "strategyQualification": False,
                    "stage": stage,
                }
            )
            for stage in ("path_b_open", "path_b_close")
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "engineering_smoke_position_ledger.jsonl").write_text(
        json.dumps(
            {
                "engineeringOnly": True,
                "strategyQualification": False,
                "stage": "path_b_final",
                "quantity": "0",
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = finalize_engineering_smoke(
        evidence_root=tmp_path,
        generated_at="2026-07-20T02:00:00Z",
    )

    assert result["status"] == "completed"
    readiness = json.loads(
        (tmp_path / "updated_provisional_demo_pre_arm_readiness.json").read_text(
            encoding="utf-8"
        )
    )
    request = json.loads(
        (tmp_path / "provisional_demo_exact_release_approval_request.json").read_text(
            encoding="utf-8"
        )
    )
    assert readiness["engineeringSmokeReady"] is True
    assert readiness["approvalReady"] is True
    assert readiness["route"] == "blocked_waiting_exact_release_approval"
    assert readiness["demoArm"] is False
    assert request["status"] == "blocked_waiting_exact_release_approval"
    assert request["approvalGranted"] is False
    assert request["demoArm"] is False
    assert request["orderCount"] == 0
    assert request["live"] is False
    assert request["withdraw"] is False
    assert (tmp_path / "engineering_smoke_artifact_manifest.json").is_file()
