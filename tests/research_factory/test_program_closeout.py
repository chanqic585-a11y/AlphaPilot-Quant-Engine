from __future__ import annotations

import json
from pathlib import Path

from alphapilot.research_factory.program_closeout import materialize_program_closeout


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_materialize_program_closeout_writes_distributed_evidence_index(
    tmp_path: Path,
) -> None:
    reports_root = tmp_path / "reports"
    program_id = "program-a"
    program_root = reports_root / "automatic_research_program" / program_id
    campaign_root = program_root / "campaigns" / "campaign-a"
    formal_root = tmp_path / "formal" / "candidate-a"
    console_root = tmp_path / "console"
    prompt = tmp_path / "prompt.md"
    prompt.write_text("# frozen prompt", encoding="utf-8")

    _write_json(
        program_root / "program_state.json",
        {
            "programId": program_id,
            "activeCampaignId": "campaign-a",
            "stage": "completed",
            "terminalRoute": "completed_zero_qualified_candidates",
            "resultReadCount": 1,
        },
    )
    _write_json(program_root / "hypothesis_inventory.json", {"hypotheses": [{"familyId": "family-a"}]})
    _write_json(program_root / "candidate_inventory.json", {"candidates": [{"candidateId": "candidate-a"}]})
    _write_json(program_root / "release_inventory.json", {"releaseCount": 0, "releases": []})
    campaign_root.mkdir(parents=True, exist_ok=True)
    (campaign_root / "prefilter_metric_matrix.csv").write_text("candidateId,status\ncandidate-a,survivor\n", encoding="utf-8")
    (campaign_root / "prefilter_gate_matrix.csv").write_text("candidateId,passed\ncandidate-a,true\n", encoding="utf-8")
    _write_json(campaign_root / "prefilter_failure_attribution.json", {"failures": []})

    _write_json(
        formal_root / "formal_run_accounting.json",
        {"candidateId": "candidate-a", "formalRunCount": 1, "resultReadCount": 1, "lockedOosAccessCount": 0},
    )
    _write_json(
        formal_root / "formal_route.json",
        {"candidateId": "candidate-a", "status": "capital_infeasible", "releaseEligible": False},
    )
    _write_json(
        formal_root / "gate_matrix.json",
        {"acceptedTradeCount": 0, "passed": False, "gates": {"minimumFormalEvents": False}},
    )
    _write_json(
        formal_root / "statistical_audit.json",
        {"status": "unavailable", "methods": [{"method": "newey_west", "status": "unavailable"}]},
    )
    _write_json(formal_root / "failure_attribution.json", {"classification": "capital_infeasible"})
    _write_json(
        console_root / "release_import_audit.json",
        {"status": "completed_zero_qualified_candidates", "releaseCount": 0, "orderCount": 0},
    )
    for name in (
        "release_store_record.json",
        "engineering_smoke_isolation_audit.json",
        "demo_universe_audit.json",
        "demo_arm_audit.json",
        "demo_approval_request.json",
        "demo_approval_overlay.json",
    ):
        _write_json(console_root / name, {"status": "not_applicable_zero_release"})
    (console_root / "demo_approval_request.md").write_text("# No approval required\n", encoding="utf-8")
    _write_json(console_root / "final_route_decision.json", {"terminalRoute": "completed_zero_qualified_candidates"})
    (console_root / "final_self_check.md").write_text("# Final self-check\n", encoding="utf-8")

    result = materialize_program_closeout(
        reports_root=reports_root,
        program_id=program_id,
        formal_result_root=formal_root,
        console_output_root=console_root,
        prompt_path=prompt,
        generated_at="2026-07-18T04:00:00Z",
    )

    assert result["terminalRoute"] == "completed_zero_qualified_candidates"
    assert result["fullBacktestsUsed"] == 1
    assert result["releaseCount"] == 0
    assert (program_root / "program_spec.json").is_file()
    assert (program_root / "program_budget.json").is_file()
    assert (program_root / "budget_consumption_summary.json").is_file()
    assert (program_root / "formal_campaign_inventory.json").is_file()
    assert (program_root / "formal_metric_matrix.csv").is_file()
    assert (program_root / "formal_gate_matrix.csv").is_file()
    assert (program_root / "statistical_availability_matrix.json").is_file()
    assert (program_root / "trial_lineage.json").is_file()
    assert (program_root / "candidate_releases" / "release_inventory.json").is_file()
    assert (program_root / "release_import_audit.json").is_file()
    assert (program_root / "final_route_decision.json").is_file()
    assert (program_root / "final_self_check.md").is_file()
