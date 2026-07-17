from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

from alphapilot.formal_validation.phase2_readiness import (
    build_phase2_readiness_audit,
    classify_phase2_readiness,
    write_phase2_evidence_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _phase2_evidence() -> dict[str, dict[str, object]]:
    image = (
        "freqtradeorg/freqtrade@sha256:"
        "87aa5c6d65359b34e9d99a0bb260a38c0efe0315253811e6f48c2afe8f278a6a"
    )
    return {
        "runtimeManifest": {
            "schemaVersion": "freqtrade_runtime_manifest_v1",
            "status": "pinned",
            "imageReference": image,
            "imageDigest": image.split("@", 1)[1],
            "networkRequired": False,
            "credentialRequired": False,
            "lockedOosRequired": False,
        },
        "runtimeSmoke": {
            "schemaVersion": "freqtrade_runtime_smoke_v1",
            "status": "passed",
            "imageReference": image,
            "networkMode": "none",
            "networkAccessCount": 0,
            "credentialReadCount": 0,
            "lockedOosContentReadCount": 0,
            "formalResultCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
        "dualEngineParity": {
            "schemaVersion": "alphapilot_dual_engine_readiness_parity_v1",
            "status": "passed",
            "passed": True,
            "zeroSignalParityRejected": True,
            "referenceEventCount": 1,
            "implementationEventCount": 1,
            "matchedEventCount": 1,
            "matchedLegCount": 2,
            "missingEventCount": 0,
            "extraEventCount": 0,
            "mismatchedEventCount": 0,
            "actualStrategyAdapterInvoked": True,
            "formalSignalCount": 1,
            "adapterSignalCount": 1,
            "networkAccessCount": 0,
            "lockedOosAccessCount": 0,
            "credentialReadCount": 0,
            "formalPerformanceClaimed": False,
        },
        "ioGuard": {
            "schemaVersion": "alphapilot_freqtrade_io_guard_readiness_v1",
            "status": "passed",
            "runtimeImage": image,
            "repositoryReadOnly": True,
            "fixtureOnly": True,
            "lockedOosMounted": False,
            "networkMode": "none",
            "accessAudit": {
                "status": "passed",
                "hashChainValid": True,
                "unauthorizedAttemptCount": 0,
            },
            "lockedOosAccessCount": 0,
            "formalResultCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
        "futureLockedOos": {
            "schemaVersion": "alphapilot_future_locked_oos_readiness_v1",
            "status": "passed",
            "route": "future_data_required",
            "admissionStatus": "blocked",
            "blockers": [
                "future_market_data_not_available",
                "formal_walk_forward_not_completed",
            ],
            "audit": {
                "status": "passed",
                "identityHashValid": True,
                "hashChainValid": True,
                "metadataOnly": True,
                "contentReadCount": 0,
                "lockedOosAccessCount": 0,
            },
            "lockedOosAccessCount": 0,
            "formalResultCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    }


def test_phase2_ready_for_formal_execution_but_not_locked_oos() -> None:
    gates = classify_phase2_readiness(
        phase1_formal_blockers=[{"code": "freqtrade_runtime_missing"}],
        evidence=_phase2_evidence(),
    )

    assert gates["formalExecution"] == {"status": "ready", "blockers": []}
    assert gates["lockedOosAdmission"]["status"] == "blocked"
    assert [
        item["code"] for item in gates["lockedOosAdmission"]["blockers"]
    ] == [
        "future_market_data_not_available",
        "formal_walk_forward_not_completed",
    ]


def test_zero_signal_parity_is_not_phase2_ready() -> None:
    evidence = _phase2_evidence()
    parity = evidence["dualEngineParity"]
    parity["referenceEventCount"] = 0
    parity["implementationEventCount"] = 0
    parity["matchedEventCount"] = 0
    parity["formalSignalCount"] = 0
    parity["adapterSignalCount"] = 0

    gates = classify_phase2_readiness(
        phase1_formal_blockers=[{"code": "freqtrade_runtime_missing"}],
        evidence=evidence,
    )

    assert gates["formalExecution"]["status"] == "blocked"
    assert "dual_engine_positive_parity_failed" in {
        item["code"] for item in gates["formalExecution"]["blockers"]
    }


def test_io_violation_and_nonzero_side_effect_fail_closed() -> None:
    evidence = _phase2_evidence()
    evidence["ioGuard"]["accessAudit"]["unauthorizedAttemptCount"] = 1
    evidence["runtimeSmoke"]["orderCount"] = 1

    gates = classify_phase2_readiness(
        phase1_formal_blockers=[{"code": "freqtrade_runtime_missing"}],
        evidence=evidence,
    )

    codes = {item["code"] for item in gates["formalExecution"]["blockers"]}
    assert "io_isolation_failed" in codes
    assert "safety_boundary_violation" in codes


def test_repository_phase2_audit_uses_docker_evidence_and_preserves_zero_effects(
    tmp_path: Path,
) -> None:
    audit = build_phase2_readiness_audit(REPO_ROOT)

    assert audit["schemaVersion"] == "formal_validation_phase2_readiness_audit_v1"
    assert audit["route"] == "ready_for_formal_walk_forward"
    assert audit["gates"]["formalExecution"]["status"] == "ready"
    assert audit["gates"]["lockedOosAdmission"]["status"] == "blocked"
    assert audit["safetyBoundary"] == {
        "lockedOosAccessCount": 0,
        "formalResultCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }

    written = write_phase2_evidence_bundle(audit, tmp_path)
    assert {path.name for path in written} == {
        "phase2_readiness_audit.json",
        "phase2_readiness_audit.md",
        "phase2_artifact_manifest.json",
    }
    manifest = json.loads(
        (tmp_path / "phase2_artifact_manifest.json").read_text("utf-8")
    )
    assert manifest["schemaVersion"] == "formal_validation_phase2_manifest_v1"
    assert all(len(item["sha256"]) == 64 for item in manifest["artifacts"])


def test_phase1_non_runtime_blocker_is_preserved() -> None:
    gates = classify_phase2_readiness(
        phase1_formal_blockers=[
            {"code": "freqtrade_runtime_missing"},
            {"code": "formal_split_policy_not_frozen"},
        ],
        evidence=deepcopy(_phase2_evidence()),
    )

    assert gates["formalExecution"]["status"] == "blocked"
    assert "formal_split_policy_not_frozen" in {
        item["code"] for item in gates["formalExecution"]["blockers"]
    }
