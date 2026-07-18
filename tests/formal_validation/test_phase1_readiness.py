from __future__ import annotations

import json
from pathlib import Path

from alphapilot.formal_validation.readiness_audit import (
    build_phase1_readiness_audit,
    classify_phase1_readiness,
    write_phase1_evidence_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _ready_formal_checks() -> dict[str, bool]:
    return {
        "v16_identity_incomplete": True,
        "formal_preregistration_invalid": True,
        "formal_preregistration_not_published": True,
        "formal_split_policy_not_frozen": True,
        "capital_policy_not_frozen": True,
        "s01_freqtrade_translation_missing": True,
        "freqtrade_runtime_missing": True,
        "timerange_io_guard_missing": True,
    }


def test_missing_clean_locked_oos_does_not_block_formal_walk_forward() -> None:
    gates = classify_phase1_readiness(
        formal_checks=_ready_formal_checks(),
        clean_locked_oos_available=False,
        formal_walk_forward_completed=False,
    )

    assert gates["formalExecution"]["status"] == "ready"
    assert gates["formalExecution"]["blockers"] == []
    assert gates["lockedOosAdmission"]["status"] == "blocked"
    locked_codes = {
        item["code"] for item in gates["lockedOosAdmission"]["blockers"]
    }
    assert "locked_oos_identity_incomplete" in locked_codes
    assert "formal_walk_forward_not_completed" in locked_codes


def test_runtime_dependency_remains_a_formal_execution_blocker_only() -> None:
    checks = _ready_formal_checks()
    checks["freqtrade_runtime_missing"] = False

    gates = classify_phase1_readiness(
        formal_checks=checks,
        clean_locked_oos_available=False,
        formal_walk_forward_completed=False,
    )

    assert gates["formalExecution"]["status"] == "blocked"
    assert [item["code"] for item in gates["formalExecution"]["blockers"]] == [
        "freqtrade_runtime_missing"
    ]
    assert "freqtrade_runtime_missing" not in {
        item["code"] for item in gates["lockedOosAdmission"]["blockers"]
    }


def test_phase1_repository_audit_has_independent_gates_and_zero_side_effects(
    tmp_path: Path,
) -> None:
    audit = build_phase1_readiness_audit(REPO_ROOT)

    assert audit["schemaVersion"] == "formal_validation_phase1_readiness_audit_v1"
    assert set(audit["gates"]) == {"formalExecution", "lockedOosAdmission"}
    assert "locked_oos_identity_incomplete" not in {
        item["code"] for item in audit["gates"]["formalExecution"]["blockers"]
    }
    assert audit["safetyBoundary"] == {
        "lockedOosAccessCount": 0,
        "formalResultCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }

    written = write_phase1_evidence_bundle(audit, tmp_path)
    assert {path.name for path in written} == {
        "phase1_readiness_audit.json",
        "phase1_readiness_audit.md",
        "holdout_lineage_audit.json",
        "holdout_lineage_audit.md",
        "artifact_manifest.json",
    }
    manifest = json.loads((tmp_path / "artifact_manifest.json").read_text("utf-8"))
    assert manifest["schemaVersion"] == "formal_validation_phase1_manifest_v1"
    assert all(len(item["sha256"]) == 64 for item in manifest["artifacts"])
