from __future__ import annotations

import json
from pathlib import Path

from alphapilot.reports.v18_pre_result_artifacts import (
    prepare_v18_pre_result_artifacts,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_pre_result_bundle_is_blocked_at_remote_freeze_without_result_access(
    tmp_path: Path,
) -> None:
    result = prepare_v18_pre_result_artifacts(
        source_repo_root=REPO_ROOT,
        output_repo_root=tmp_path,
        v17_provenance_reference=(
            "reports/v13_27_1_17_closeout_supplement/"
            "v17_closeout_provenance_sidecar.json"
        ),
        remote_code_commit=None,
        remote_preregistration_commit=None,
        remote_tag=None,
    )

    campaign_root = result["campaignRoot"]
    expected = {
        "correction_manifest.json",
        "v17_closeout_provenance_reference.json",
        "capacity_data_semantics_audit.json",
        "capacity_model_contract.json",
        "correlation_cluster_policy_contract.json",
        "portfolio_beta_policy_contract.json",
        "signal_ranking_policy_contract.json",
        "formal_portfolio_policy_v2.json",
        "capital_policy_conformance.json",
        "formal_preregistration_reference.json",
        "future_locked_oos_identity_reference.json",
        "route_decision.json",
        "campaign_summary.json",
        "campaign_summary.md",
        "artifact_manifest.json",
    }
    assert {path.name for path in campaign_root.iterdir()} == expected

    route = json.loads((campaign_root / "route_decision.json").read_text())
    summary = json.loads((campaign_root / "campaign_summary.json").read_text())
    correction = json.loads((campaign_root / "correction_manifest.json").read_text())
    prereg_reference = json.loads(
        (campaign_root / "formal_preregistration_reference.json").read_text()
    )
    future_oos = json.loads(
        (campaign_root / "future_locked_oos_identity_reference.json").read_text()
    )
    manifest = json.loads((campaign_root / "artifact_manifest.json").read_text())

    assert route["route"] == "blocked_remote_freeze"
    assert route["formalRunCount"] == 0
    assert summary["formalRunCount"] == 0
    assert summary["resultReadCount"] == 0
    assert summary["lockedOosAccessCount"] == 0
    assert summary["releaseCount"] == 0
    assert summary["demoArm"] is False
    assert summary["orderCount"] == 0
    assert correction["strategyParameterChanges"] == 0
    assert correction["formalPortfolioPolicyDefinitionChanges"] == 1
    assert prereg_reference["remoteFreezeStatus"] == "not_published"
    assert future_oos["status"] == "pending_remote_freeze"
    assert future_oos["contentRead"] is False
    assert future_oos["accessCount"] == 0
    assert not (tmp_path / "research" / "locked_oos").exists()
    assert all("fold_results" not in row["path"] for row in manifest["artifacts"])
    assert result["preregistrationPath"].is_file()


def test_pre_result_artifacts_are_deterministic(tmp_path: Path) -> None:
    first = prepare_v18_pre_result_artifacts(
        source_repo_root=REPO_ROOT,
        output_repo_root=tmp_path,
        v17_provenance_reference="v17_sidecar.json",
        remote_code_commit=None,
        remote_preregistration_commit=None,
        remote_tag=None,
    )
    before = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }
    second = prepare_v18_pre_result_artifacts(
        source_repo_root=REPO_ROOT,
        output_repo_root=tmp_path,
        v17_provenance_reference="v17_sidecar.json",
        remote_code_commit=None,
        remote_preregistration_commit=None,
        remote_tag=None,
    )
    after = {
        path.relative_to(tmp_path).as_posix(): path.read_bytes()
        for path in tmp_path.rglob("*")
        if path.is_file()
    }

    assert first["campaignId"] == second["campaignId"]
    assert before == after


def test_pre_result_artifacts_freeze_the_implementation_commit(
    tmp_path: Path,
) -> None:
    implementation_commit = "b" * 40

    result = prepare_v18_pre_result_artifacts(
        source_repo_root=REPO_ROOT,
        output_repo_root=tmp_path,
        v17_provenance_reference="v17_sidecar.json",
        remote_code_commit=implementation_commit,
        remote_preregistration_commit=None,
        remote_tag=None,
    )

    preregistration = json.loads(
        result["preregistrationPath"].read_text(encoding="utf-8")
    )
    assert preregistration["implementationCommit"] == implementation_commit
