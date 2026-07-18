from __future__ import annotations

import json
from pathlib import Path

from alphapilot.formal_validation.formal_reporting import (
    audit_executable_formal_contract,
    build_pre_run_terminal_route,
    write_pre_run_terminal_bundle,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _frozen_preregistration(repo_root: Path = REPO_ROOT) -> dict:
    path = (
        repo_root
        / "research"
        / "preregistrations"
        / "advisory_r_v17_s01_formal_walk_forward.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_current_frozen_capital_policy_is_not_executable() -> None:
    issues = audit_executable_formal_contract(_frozen_preregistration())

    assert {issue["code"] for issue in issues} == {
        "capacity_model_not_frozen",
        "correlation_cluster_policy_not_frozen",
        "portfolio_beta_policy_not_frozen",
        "ranking_field_definitions_not_frozen",
    }
    assert all(issue["requiresNewCampaign"] is True for issue in issues)
    assert all(issue["affectsResultComputation"] is True for issue in issues)


def test_incomplete_contract_routes_before_formal_execution() -> None:
    preregistration = _frozen_preregistration()
    issues = audit_executable_formal_contract(preregistration)

    route = build_pre_run_terminal_route(preregistration, issues)

    assert route["route"] == "implementation_invalid_requires_new_campaign"
    assert route["formalRunCount"] == 0
    assert route["resultReadCount"] == 0
    assert route["formalPass"] is False
    assert route["lockedOosAccessCount"] == 0
    assert route["releaseCount"] == 0
    assert route["demoArm"] is False
    assert route["orderCount"] == 0


def test_terminal_bundle_contains_no_formal_performance_artifacts(
    tmp_path: Path,
) -> None:
    preregistration = _frozen_preregistration()
    issues = audit_executable_formal_contract(preregistration)

    result = write_pre_run_terminal_bundle(tmp_path, preregistration, issues)

    expected = {
        "formal_execution_contract_audit.json",
        "route_decision.json",
        "gate_matrix.json",
        "failure_attribution.json",
        "campaign_summary.json",
        "campaign_summary.md",
        "artifact_manifest.json",
    }
    assert {path.name for path in tmp_path.iterdir()} == expected
    assert result["route"] == "implementation_invalid_requires_new_campaign"
    assert not (tmp_path / "formal_metrics.json").exists()
    assert not (tmp_path / "candidate_events.parquet").exists()

    manifest = json.loads((tmp_path / "artifact_manifest.json").read_text("utf-8"))
    assert manifest["formalPerformanceArtifactCount"] == 0
    assert manifest["lockedOosAccessCount"] == 0
