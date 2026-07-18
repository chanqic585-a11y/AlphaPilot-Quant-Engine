from __future__ import annotations

import csv
import json
from pathlib import Path
import zipfile

from alphapilot.research_factory.program_v27_closeout import (
    materialize_v27_zero_survivor_closeout,
)


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_v27_zero_survivor_closeout_writes_explicit_terminal_evidence(
    tmp_path: Path,
) -> None:
    reports = tmp_path / "reports"
    program_id = "v26-program"
    root = reports / "automatic_strategy_to_demo" / program_id
    v27 = root / "v27"
    prompt = tmp_path / "master.md"
    prompt.write_text("# frozen master workflow\n", encoding="utf-8")

    _write_json(
        root / "program_state.json",
        {
            "programId": program_id,
            "stage": "v27_completed",
            "nextAllowedStage": "completed_zero_qualified_candidates",
            "terminalRoute": "completed_zero_qualified_candidates",
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    )
    _write_json(root / "program_budget.json", {"campaignsConsumed": 1, "candidateTrialsConsumed": 2})
    (root / "program_ledger.jsonl").write_text("{}\n", encoding="utf-8")
    (root / "program_budget_ledger.jsonl").write_text("{}\n", encoding="utf-8")
    for name in (
        "program_spec.json",
        "baseline_identity.json",
        "v25_ranking_semantics_clarification_sidecar.json",
        "candidate_ranking_registry.json",
        "ranking_semantics_derivation_audit.json",
        "current_candidate_resolution.json",
    ):
        _write_json(root / name, {"name": name})

    hypotheses = [
        {
            "hypothesisId": "hyp-a",
            "familyId": "family-a",
            "timeframe": "1h",
            "sourceReferences": ["reports/source.json"],
        }
    ]
    candidates = [
        {
            "candidateId": "candidate-a",
            "hypothesisId": "hyp-a",
            "familyId": "family-a",
            "timeframe": "1h",
            "direction": "long",
            "candidateSpecHash": "candidate-hash",
            "dataReadinessReceiptHash": "receipt-hash",
        },
        {
            "candidateId": "candidate-b",
            "hypothesisId": "hyp-a",
            "familyId": "family-a",
            "timeframe": "1h",
            "direction": "short",
            "candidateSpecHash": "candidate-hash-b",
            "dataReadinessReceiptHash": "receipt-hash",
        },
    ]
    structural = [
        {"candidateId": candidate["candidateId"], "status": "passed"}
        for candidate in candidates
    ]
    ranking = [
        {"candidateId": candidate["candidateId"], "status": "passed"}
        for candidate in candidates
    ]
    capacity = [
        {"candidateId": "candidate-a", "status": "passed"},
        {"candidateId": "candidate-b", "status": "failed"},
    ]
    prefilter = [
        {
            "candidateId": "candidate-a",
            "familyId": "family-a",
            "passed": False,
            "failedGates": ["minimumBenchmarkIncrementNetR"],
            "metrics": {"eventCount": 100, "profitFactor": 1.04, "averageNetR": 0.01},
            "gates": {
                "minimumBenchmarkIncrementNetR": {
                    "passed": False,
                    "observed": -2.0,
                    "operator": ">",
                    "required": 0.0,
                }
            },
        },
        {
            "candidateId": "candidate-b",
            "familyId": "family-a",
            "passed": False,
            "failedGates": ["capacityCertification"],
            "metrics": {},
            "gates": {},
        },
    ]
    fixtures: dict[str, object] = {
        "data_readiness_receipts.json": {"1h": {"status": "ready", "receiptHash": "receipt-hash"}},
        "capacity_profiles.json": {"1h": {"status": "ready", "profileHash": "profile-hash"}},
        "hypothesis_inventory.json": hypotheses,
        "candidate_inventory.json": candidates,
        "candidate_structural_certification.json": structural,
        "candidate_ranking_certification.json": ranking,
        "candidate_ranking_evidence.json": {"candidate-a": []},
        "candidate_capacity_certification.json": capacity,
        "prefilter_results.json": prefilter,
        "prefilter_route.json": {
            "formalCandidateIds": [],
            "prefilterFailedCandidateIds": ["candidate-a", "candidate-b"],
            "terminalRoute": "completed_zero_prefilter_survivors",
        },
        "v27_summary.json": {
            "candidateCount": 2,
            "prefilterPassCount": 0,
            "formalCandidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "demoApprovalCount": 0,
            "demoArm": False,
            "orderCount": 0,
            "nextStage": "completed_zero_qualified_candidates",
        },
    }
    for name, payload in fixtures.items():
        _write_json(v27 / name, payload)
    (v27 / "v27_summary.md").write_text("# V27\n", encoding="utf-8")

    result = materialize_v27_zero_survivor_closeout(
        reports_root=reports,
        program_id=program_id,
        prompt_path=prompt,
        generated_at="2026-07-18T08:00:00Z",
    )

    assert result["finalRoute"] == "completed_zero_qualified_candidates"
    assert result["candidateCount"] == 2
    assert result["formalRunCount"] == 0
    assert result["releaseCount"] == 0
    assert result["demoArm"] is False
    assert (root / "final_route_decision.json").is_file()
    assert (root / "final_self_check.md").is_file()
    assert (root / "release_import_audit.json").is_file()
    assert (root / "demo_arm_audit.json").is_file()
    assert (root / "candidate_releases" / "release_inventory.json").is_file()

    with (root / "candidate_data_gate_matrix.csv").open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 2
    assert {row["candidateId"] for row in rows} == {"candidate-a", "candidate-b"}

    package_root = root / "evidence_packages"
    package_names = {
        "AlphaPilot-V26-31-Automatic-Strategy-to-Demo-Core-Evidence.zip",
        "AlphaPilot-V26-31-Candidate-and-Formal-Evidence.zip",
        "AlphaPilot-V26-31-OKX-Release-and-Demo-Evidence.zip",
    }
    assert {path.name for path in package_root.glob("*.zip")} == package_names
    for archive in package_root.glob("*.zip"):
        with zipfile.ZipFile(archive) as bundle:
            assert "PACKAGE_MANIFEST.json" in bundle.namelist()
            assert not any("credential" in name.lower() for name in bundle.namelist())

    route = json.loads((root / "final_route_decision.json").read_text(encoding="utf-8"))
    assert route["formalRunCount"] == 0
    assert route["resultReadCount"] == 0
    assert route["lockedOosReadCount"] == 0
    assert route["releaseCount"] == 0
    assert route["approvalCount"] == 0
    assert route["orderCount"] == 0
