from __future__ import annotations

import pytest

from alphapilot.v63_foundation.parallel_tracks import (
    V62_FAILED_CANDIDATE_IDS,
    build_track_b_campaign,
    build_track_c_status_matrix,
    write_parallel_track_artifacts,
)


def test_track_b_campaign_is_fresh_bounded_and_does_not_read_locked_oos() -> None:
    campaign = build_track_b_campaign(
        campaign_id="v63-fresh-mechanism-campaign-20260724",
        created_at="2026-07-24T01:00:00Z",
        data_snapshot_id="snapshot-development-only",
    )

    assert campaign["status"] == "preregistered_dry_preparation_only"
    assert campaign["lockedOosReadCount"] == 0
    assert campaign["releaseApprovalAllowed"] is False
    assert campaign["armAllowed"] is False
    assert campaign["orderCapabilityEnabled"] is False
    assert campaign["budget"]["maximumFamilies"] == 3
    assert campaign["budget"]["maximumCandidates"] == 6
    assert len(campaign["families"]) == 3
    assert len(campaign["candidateIds"]) == 6
    assert set(campaign["candidateIds"]).isdisjoint(V62_FAILED_CANDIDATE_IDS)
    assert campaign["preregistrationHash"].startswith("v63_track_b_preregistration_")

    repeated = build_track_b_campaign(
        campaign_id="v63-fresh-mechanism-campaign-20260724",
        created_at="2026-07-24T01:00:00Z",
        data_snapshot_id="snapshot-development-only",
    )
    assert repeated == campaign


def test_track_b_rejects_an_excluded_candidate_identity() -> None:
    with pytest.raises(ValueError, match="v62_failed_candidate_identity_reused"):
        build_track_b_campaign(
            campaign_id="v63-fresh-mechanism-campaign-20260724",
            created_at="2026-07-24T01:00:00Z",
            data_snapshot_id="snapshot-development-only",
            candidate_id_override=next(iter(V62_FAILED_CANDIDATE_IDS)),
        )


def test_track_c_preserves_honest_not_run_and_blocks_unsafe_results() -> None:
    matrix = build_track_c_status_matrix(
        checks={
            "coverage": {
                "status": "passed",
                "evidence": "coverage-summary.json",
            },
            "security_findings": {
                "status": "passed",
                "evidence": "security-findings.json",
            },
            "factor_bench": {
                "status": "not_run",
                "reason": "formal_factor_snapshot_unavailable",
            },
            "qlib": {
                "status": "blocked",
                "reason": "docker_image_unavailable",
            },
            "observer": {
                "status": "passed",
                "evidence": "observer-preflight.json",
            },
            "deployment_scripts": {
                "status": "passed",
                "evidence": "deployment-validation.json",
            },
        }
    )

    assert matrix["overallStatus"] == "completed_with_blockers"
    assert matrix["counts"] == {"passed": 4, "blocked": 1, "not_run": 1}
    assert matrix["checks"]["factor_bench"]["status"] == "not_run"
    assert matrix["checks"]["qlib"]["status"] == "blocked"
    assert matrix["demoArmAllowed"] is False
    assert matrix["liveArmAllowed"] is False
    assert matrix["orderCapabilityEnabled"] is False


def test_parallel_track_artifacts_are_written_with_a_hash_manifest(tmp_path) -> None:
    campaign = build_track_b_campaign(
        campaign_id="v63-fresh-mechanism-campaign-20260724",
        created_at="2026-07-24T01:00:00Z",
        data_snapshot_id="snapshot-development-only",
    )
    matrix = build_track_c_status_matrix(
        checks={
            "coverage": {
                "status": "not_run",
                "reason": "coverage_package_unavailable",
            },
            "security_findings": {
                "status": "passed",
                "evidence": "security-findings.json",
            },
            "factor_bench": {
                "status": "passed",
                "evidence": "factor-bench.json",
            },
            "qlib": {
                "status": "blocked",
                "reason": "formal_snapshot_unavailable",
            },
            "observer": {
                "status": "passed",
                "evidence": "observer-preflight.json",
            },
            "deployment_scripts": {
                "status": "passed",
                "evidence": "deployment-validation.json",
            },
        }
    )

    manifest = write_parallel_track_artifacts(
        repository_root=tmp_path,
        campaign=campaign,
        track_c_matrix=matrix,
    )

    preregistration = (
        tmp_path
        / "research"
        / "preregistrations"
        / "v63-fresh-mechanism-campaign-20260724.json"
    )
    report_root = tmp_path / "reports" / "v63_server_foundation"
    assert preregistration.is_file()
    assert (report_root / "track_b_campaign_preparation.json").is_file()
    assert (report_root / "track_c_status_matrix.json").is_file()
    assert (report_root / "artifact_manifest.json").is_file()
    assert manifest["artifactCount"] == 3
    assert all(item["sha256"] for item in manifest["artifacts"])
