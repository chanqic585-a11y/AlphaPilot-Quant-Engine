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
