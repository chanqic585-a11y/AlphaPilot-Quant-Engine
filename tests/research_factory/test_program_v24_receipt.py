from __future__ import annotations

import json
from pathlib import Path

from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.program_state import ProgramStateStore
from alphapilot.research_factory.program_types import ProgramState
from alphapilot.research_factory.program_v24 import finalize_v24_zero_release_route
from alphapilot.evolution.registry.hashing import stable_hash


def test_zero_release_console_receipt_completes_program(tmp_path: Path) -> None:
    reports = tmp_path / "reports"
    program_id = "program-a"
    paths = ProgramArtifactPaths(reports, program_id)
    store = ProgramStateStore(paths)
    state = ProgramState.create(
        program_id=program_id,
        baseline_commit="abc123",
        program_spec_hash="spec123",
        created_at="2026-07-18T00:00:00Z",
    ).transition(
        stage="release_ready",
        updated_at="2026-07-18T00:00:00Z",
        active_campaign_id="campaign-a",
        terminal_route="completed_zero_qualified_candidates",
        one_shot_claims_consumed=1,
        result_read_count=1,
    )
    store.save(state)
    store.write_checkpoint(
        stage="v23",
        created_at="2026-07-18T00:00:00Z",
        payload={
            "releaseCount": 0,
            "approvalRequired": False,
            "demoArm": False,
            "orderCount": 0,
            "terminalRoute": "completed_zero_qualified_candidates",
        },
    )
    console_audit = tmp_path / "release_import_audit.json"
    audit = {
        "status": "completed_zero_qualified_candidates",
        "releaseCount": 0,
        "importedReleaseCount": 0,
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "engineeringSmokeCountedAsStrategyEvidence": False,
    }
    audit["auditHash"] = stable_hash(audit, prefix="automatic_v24_release_import_audit")
    console_audit.write_text(
        json.dumps(audit),
        encoding="utf-8",
    )

    result = finalize_v24_zero_release_route(
        reports_root=reports,
        program_id=program_id,
        generated_at="2026-07-18T01:00:00Z",
        console_audit_path=console_audit,
    )

    assert result["status"] == "completed"
    assert result["terminalRoute"] == "completed_zero_qualified_candidates"
    assert result["releaseCount"] == 0
    assert result["demoArm"] is False
    assert result["orderCount"] == 0
    assert store.load().stage == "completed"
