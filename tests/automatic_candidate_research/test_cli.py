from __future__ import annotations

import json
from pathlib import Path

from alphapilot.scripts.run_v36_candidate_research import main
from alphapilot.standard_replication import ReplicationSourceRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_cli_runs_via_v35_service_and_emits_machine_readable_receipt(
    tmp_path: Path,
    capsys,
) -> None:
    registry = ReplicationSourceRegistry.load(
        REPO_ROOT / "research/source_registry/strategy_research_source_registry.json"
    )
    job_path = tmp_path / "job.json"
    job_path.write_text(
        json.dumps(
            {
                "campaignId": "v36-cli-smoke",
                "createdAt": "2026-07-19T00:00:00Z",
                "familyIds": list(registry.family_ids),
                "candidateIds": sorted(
                    variant.candidate_id
                    for family in registry.items
                    for variant in family.variants
                ),
                "comparisonPanel": {
                    "developmentStart": "2024-01-01T00:00:00Z",
                    "developmentEnd": "2025-01-01T00:00:00Z",
                    "dataSnapshotId": "okx-public-snapshot-v34c",
                    "costPolicyHash": "cost-policy-v13",
                    "capitalPolicyHash": "capital-policy-v18",
                    "benchmarkPolicyHash": "benchmark-policy-v32",
                    "randomSeed": 36,
                },
                "developmentEvidence": [],
                "formalOutcomes": [],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--state-root",
            str(tmp_path / "state"),
            "--output-root",
            str(tmp_path / "reports"),
            "--job-json",
            str(job_path),
            "--now",
            "2026-07-19T00:01:00Z",
        ]
    )

    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt["status"] == "research_blocked_data"
    assert receipt["candidateCount"] == 9
    assert receipt["blockedFamilyCount"] == 2
    assert receipt["releaseCount"] == 0
    assert receipt["demoArm"] is False
    assert receipt["orderCount"] == 0
    assert (tmp_path / "state/research_service_state.json").is_file()
    assert (tmp_path / "state/research_cycle_receipts.jsonl").is_file()


def test_cli_accepts_an_explicit_frozen_registry_path(
    tmp_path: Path,
    capsys,
) -> None:
    registry_path = (
        REPO_ROOT
        / "research/source_registry/strategy_research_source_registry_v36_5.json"
    )
    registry = ReplicationSourceRegistry.load(registry_path)
    job_path = tmp_path / "job.json"
    job_path.write_text(
        json.dumps(
            {
                "campaignId": "v36-5-cli-smoke",
                "createdAt": "2026-07-19T00:00:00Z",
                "familyIds": list(registry.family_ids),
                "candidateIds": sorted(
                    variant.candidate_id
                    for family in registry.items
                    for variant in family.variants
                ),
                "comparisonPanel": {
                    "developmentStart": "2024-01-01T00:00:00Z",
                    "developmentEnd": "2025-01-01T00:00:00Z",
                    "dataSnapshotId": "snapshot-fixture",
                    "costPolicyHash": "cost-policy-fixture",
                    "capitalPolicyHash": "capital-policy-fixture",
                    "benchmarkPolicyHash": "benchmark-policy-fixture",
                    "randomSeed": 365,
                },
                "developmentEvidence": [],
                "formalOutcomes": [],
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--registry-path",
            str(registry_path),
            "--state-root",
            str(tmp_path / "state"),
            "--output-root",
            str(tmp_path / "reports"),
            "--job-json",
            str(job_path),
            "--now",
            "2026-07-19T00:01:00Z",
        ]
    )

    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt["candidateCount"] == 3
    assert receipt["eligibleCandidateCount"] == 2
    assert receipt["blockedFamilyCount"] == 1
    assert receipt["trialCount"] == 6


def test_cli_honors_explicit_pause_file_before_research_execution(
    tmp_path: Path,
    capsys,
) -> None:
    registry_path = (
        REPO_ROOT
        / "research/source_registry/strategy_research_source_registry_v36_5.json"
    )
    registry = ReplicationSourceRegistry.load(registry_path)
    family = registry.items[0]
    candidate_id = family.variants[0].candidate_id
    job_path = tmp_path / "job.json"
    job_path.write_text(
        json.dumps(
            {
                "campaignId": "v56-paused-cli-smoke",
                "createdAt": "2026-07-21T00:00:00Z",
                "familyIds": [family.family_id],
                "candidateIds": [candidate_id],
                "comparisonPanel": {
                    "developmentStart": "2024-01-01T00:00:00Z",
                    "developmentEnd": "2025-01-01T00:00:00Z",
                    "dataSnapshotId": "snapshot-fixture",
                    "costPolicyHash": "cost-policy-fixture",
                    "capitalPolicyHash": "capital-policy-fixture",
                    "benchmarkPolicyHash": "benchmark-policy-fixture",
                    "randomSeed": 56,
                },
                "developmentEvidence": [],
                "formalOutcomes": [],
            }
        ),
        encoding="utf-8",
    )
    pause_file = tmp_path / "PAUSE"
    pause_file.write_text("paused\n", encoding="ascii")

    worker_exit_file = tmp_path / "worker-stopped.json"
    exit_code = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--registry-path",
            str(registry_path),
            "--state-root",
            str(tmp_path / "state"),
            "--output-root",
            str(tmp_path / "reports"),
            "--job-json",
            str(job_path),
            "--pause-file",
            str(pause_file),
            "--worker-exit-file",
            str(worker_exit_file),
            "--now",
            "2026-07-21T00:01:00Z",
        ]
    )

    receipt = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert receipt["status"] == "paused"
    assert receipt["candidateCount"] == 0
    assert receipt["demoArm"] is False
    assert receipt["orderCount"] == 0
    assert worker_exit_file.is_file()

    pause_file.unlink()
    exit_code = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--registry-path",
            str(registry_path),
            "--state-root",
            str(tmp_path / "state"),
            "--output-root",
            str(tmp_path / "reports"),
            "--job-json",
            str(job_path),
            "--pause-file",
            str(pause_file),
            "--worker-exit-file",
            str(worker_exit_file),
            "--now",
            "2026-07-21T00:02:00Z",
        ]
    )
    resumed_receipt = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert resumed_receipt["status"] == "research_zero_qualified"
    assert resumed_receipt["campaignId"] == "v56-paused-cli-smoke"
    assert resumed_receipt["candidateCount"] == 1
    assert resumed_receipt["eligibleCandidateCount"] == 1
    assert resumed_receipt["blockedFamilyCount"] == 0
    assert resumed_receipt["trialCount"] == 3


def test_cli_persists_safe_failure_receipt_and_worker_exit_marker(
    tmp_path: Path,
    capsys,
) -> None:
    registry_path = (
        REPO_ROOT
        / "research/source_registry/strategy_research_source_registry_v36_5.json"
    )
    registry = ReplicationSourceRegistry.load(registry_path)
    family = registry.items[0]
    candidate_id = family.variants[0].candidate_id
    campaign_id = "v62-missing-snapshot-cli-smoke"
    job_path = tmp_path / "job.json"
    job_path.write_text(
        json.dumps(
            {
                "campaignId": campaign_id,
                "createdAt": "2026-07-22T00:00:00Z",
                "familyIds": [family.family_id],
                "candidateIds": [candidate_id],
                "comparisonPanel": {
                    "developmentStart": "2024-01-01T00:00:00Z",
                    "developmentEnd": "2025-01-01T00:00:00Z",
                    "dataSnapshotId": "missing-snapshot-fixture",
                    "costPolicyHash": "cost-policy-fixture",
                    "capitalPolicyHash": "capital-policy-fixture",
                    "benchmarkPolicyHash": "benchmark-policy-fixture",
                    "randomSeed": 62,
                },
                "developmentReplay": {
                    "snapshotManifestPath": str(
                        tmp_path / "missing-snapshot-manifest.json"
                    ),
                    "roundTripCostRate": 0.001,
                },
                "developmentEvidence": [],
                "formalOutcomes": [],
            }
        ),
        encoding="utf-8",
    )
    worker_exit_file = tmp_path / "worker-stopped.json"

    exit_code = main(
        [
            "--repo-root",
            str(REPO_ROOT),
            "--registry-path",
            str(registry_path),
            "--state-root",
            str(tmp_path / "state"),
            "--output-root",
            str(tmp_path / "reports"),
            "--job-json",
            str(job_path),
            "--worker-exit-file",
            str(worker_exit_file),
            "--now",
            "2026-07-22T00:01:00Z",
        ]
    )

    receipt = json.loads(capsys.readouterr().out)
    receipt_lines = (
        tmp_path / "state/research_cycle_receipts.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    persisted_receipt = json.loads(receipt_lines[-1])
    worker_exit = json.loads(worker_exit_file.read_text(encoding="utf-8"))

    assert exit_code == 1
    assert receipt == persisted_receipt
    assert receipt["campaignId"] == campaign_id
    assert receipt["status"] == "error"
    assert receipt["errorType"] == "V36ContractError"
    assert receipt["errorCode"] == "snapshot_manifest_missing"
    assert receipt["candidateCount"] == 1
    assert receipt["releaseCount"] == 0
    assert receipt["demoArm"] is False
    assert receipt["orderCount"] == 0
    assert worker_exit["campaignId"] == campaign_id
    assert worker_exit["status"] == "error"
