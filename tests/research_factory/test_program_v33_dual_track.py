from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphapilot.research_factory.program_ledger import ProgramLedger
from alphapilot.research_factory.program_v33 import (
    DualTrackLedgerSet,
    build_dual_track_program_id,
    initialize_dual_track_successor,
    record_v34a_data_pilot,
    record_v34b_data_extension,
    record_v34c_public_data_service,
)


PREDECESSOR_ID = "automatic_strategy_renewal_v28_4e6ab55a5e949716"


def _predecessor(tmp_path: Path) -> Path:
    root = tmp_path / "automatic_research_program" / PREDECESSOR_ID
    root.mkdir(parents=True)
    (root / "program_budget.json").write_text(
        json.dumps(
            {
                "campaignsUsed": 1,
                "fullBacktestsUsed": 0,
                "fullBacktestsRemaining": 96,
                "maximumAdditionalFullBacktests": 96,
            }
        ),
        encoding="utf-8",
    )
    ProgramLedger(root / "program_ledger.jsonl").append(
        event_type="program_completed",
        stage="v30_completed",
        created_at="2026-07-18T16:04:24Z",
        payload={"finalRoute": "blocked_formal_data"},
    )
    (root / "program_summary.json").write_text(
        json.dumps(
            {
                "programId": PREDECESSOR_ID,
                "finalRoute": "blocked_formal_data",
                "formalRunCount": 0,
                "resultReadCount": 0,
                "lockedOosReadCount": 0,
            }
        ),
        encoding="utf-8",
    )
    return root


def test_successor_identity_is_deterministic_and_predecessor_scoped() -> None:
    first = build_dual_track_program_id(
        predecessor_program_id=PREDECESSOR_ID,
        predecessor_budget_ledger_hash="sha256:ledger-a",
        implementation_contract_hash="sha256:contract-a",
    )
    repeated = build_dual_track_program_id(
        predecessor_program_id=PREDECESSOR_ID,
        predecessor_budget_ledger_hash="sha256:ledger-a",
        implementation_contract_hash="sha256:contract-a",
    )
    changed = build_dual_track_program_id(
        predecessor_program_id=PREDECESSOR_ID,
        predecessor_budget_ledger_hash="sha256:ledger-b",
        implementation_contract_hash="sha256:contract-a",
    )

    assert first == repeated
    assert first.startswith("alphapilot_dual_track_v33_")
    assert changed != first


def test_successor_inherits_budget_and_writes_unambiguous_statuses(
    tmp_path: Path,
) -> None:
    predecessor = _predecessor(tmp_path)

    summary = initialize_dual_track_successor(
        reports_root=tmp_path,
        predecessor_program_root=predecessor,
        implementation_contract_hash="sha256:v33-contract",
        implementation_commit="commit-v33",
        generated_at="2026-07-19T00:00:00Z",
        writer_id="test-writer",
    )
    root = tmp_path / "dual_track" / summary["programId"]
    budget = json.loads((root / "inherited_budget.json").read_text(encoding="utf-8"))
    status = json.loads((root / "qualification_status.json").read_text(encoding="utf-8"))

    assert budget["campaignsUsed"] == 1
    assert budget["fullBacktestsUsed"] == 0
    assert budget["fullBacktestsRemaining"] == 96
    assert budget["budgetReset"] is False
    assert status == {
        "schemaVersion": "dual_track_qualification_status_v1",
        "closeoutIntegrityPassed": True,
        "programObjectivePassed": False,
        "strategyQualified": False,
        "demoQualified": False,
        "liveQualified": False,
    }
    assert "overallPass" not in status
    assert summary["topLevelState"] == "baseline_frozen"
    assert summary["formalRunCount"] == 0
    assert summary["resultReadCount"] == 0
    assert summary["orderCount"] == 0


def test_successor_creates_four_hash_chained_ledgers(tmp_path: Path) -> None:
    predecessor = _predecessor(tmp_path)
    summary = initialize_dual_track_successor(
        reports_root=tmp_path,
        predecessor_program_root=predecessor,
        implementation_contract_hash="sha256:v33-contract",
        implementation_commit="commit-v33",
        generated_at="2026-07-19T00:00:00Z",
        writer_id="test-writer",
    )
    root = tmp_path / "dual_track" / summary["programId"]

    names = {
        "master": "master_program_ledger.jsonl",
        "research": "research_track_ledger.jsonl",
        "demo_product": "demo_product_track_ledger.jsonl",
        "cross_track": "cross_track_receipt_ledger.jsonl",
    }
    for name in names.values():
        rows = ProgramLedger(root / name).read_all()
        assert len(rows) == 1
        assert rows[0]["sequence"] == 1
        assert rows[0]["stage"] == "v33_baseline"


def test_dual_track_ledger_rejects_a_second_live_writer(tmp_path: Path) -> None:
    ledgers = DualTrackLedgerSet(tmp_path, writer_id="writer-a")

    with ledgers.writer_lease("master"):
        with pytest.raises(RuntimeError, match="ledger_writer_lease_unavailable"):
            with DualTrackLedgerSet(tmp_path, writer_id="writer-b").writer_lease(
                "master"
            ):
                pass


def test_v34a_receipt_advances_data_state_without_creating_strategy_or_orders(
    tmp_path: Path,
) -> None:
    predecessor = _predecessor(tmp_path)
    summary = initialize_dual_track_successor(
        reports_root=tmp_path,
        predecessor_program_root=predecessor,
        implementation_contract_hash="sha256:v33-contract",
        implementation_commit="commit-v33",
        generated_at="2026-07-19T00:00:00Z",
        writer_id="test-writer",
    )
    root = tmp_path / "dual_track" / summary["programId"]

    updated = record_v34a_data_pilot(
        program_root=root,
        pilot_result={
            "status": "completed",
            "scope": "v34a_data_only",
            "snapshotId": "okx_snapshot_123",
            "partitionCount": 9,
            "reusedPartitionCount": 6,
            "downloadedRowCount": 100,
            "candidateCount": 0,
            "formalRunCount": 0,
            "demoReleaseCount": 0,
            "orderCount": 0,
        },
        created_at="2026-07-19T01:00:00Z",
        writer_id="test-writer",
    )

    assert updated["topLevelState"] == "data_pilot_completed"
    assert updated["dataSnapshotId"] == "okx_snapshot_123"
    assert updated["candidateCount"] == 0
    assert updated["formalRunCount"] == 0
    assert updated["releaseCount"] == 0
    assert updated["orderCount"] == 0
    state = json.loads((root / "program_state.json").read_text(encoding="utf-8"))
    assert state["researchTrackState"] == "data_pilot_completed"
    assert state["demoProductTrackState"] == "demo_platform_building"
    master = ProgramLedger(root / "master_program_ledger.jsonl").read_all()
    research = ProgramLedger(root / "research_track_ledger.jsonl").read_all()
    cross_track = ProgramLedger(root / "cross_track_receipt_ledger.jsonl").read_all()
    assert master[-1]["eventType"] == "data_pilot_completed"
    assert research[-1]["eventType"] == "official_data_snapshot_registered"
    assert cross_track[-1]["eventType"] == "data_snapshot_receipt_recorded"


def test_v34b_receipt_extends_data_without_mutating_v34a_snapshot_or_side_effects(
    tmp_path: Path,
) -> None:
    predecessor = _predecessor(tmp_path)
    summary = initialize_dual_track_successor(
        reports_root=tmp_path,
        predecessor_program_root=predecessor,
        implementation_contract_hash="sha256:v33-contract",
        implementation_commit="commit-v33",
        generated_at="2026-07-19T00:00:00Z",
        writer_id="test-writer",
    )
    root = tmp_path / "dual_track" / summary["programId"]
    record_v34a_data_pilot(
        program_root=root,
        pilot_result={
            "status": "completed",
            "scope": "v34a_data_only",
            "snapshotId": "okx_snapshot_123",
            "partitionCount": 9,
            "candidateCount": 0,
            "formalRunCount": 0,
            "demoReleaseCount": 0,
            "orderCount": 0,
        },
        created_at="2026-07-19T01:00:00Z",
        writer_id="test-writer",
    )

    updated = record_v34b_data_extension(
        program_root=root,
        extension_result={
            "status": "completed",
            "scope": "v34b_public_data_only",
            "snapshotId": "okx_v34b_snapshot_456",
            "instrumentMetadataCount": 300,
            "fundingInstrumentCount": 3,
            "forwardStreamsCompleted": ["open_interest", "funding"],
            "candidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "orderCount": 0,
            "demoArm": False,
        },
        created_at="2026-07-19T02:00:00Z",
        writer_id="test-writer",
    )

    assert updated["dataSnapshotId"] == "okx_snapshot_123"
    assert updated["dataFoundationExtensionId"] == "okx_v34b_snapshot_456"
    assert updated["topLevelState"] == "data_foundation_extended"
    assert updated["candidateCount"] == 0
    assert updated["formalRunCount"] == 0
    assert updated["resultReadCount"] == 0
    assert updated["releaseCount"] == 0
    assert updated["approvalCount"] == 0
    assert updated["demoArm"] is False
    assert updated["orderCount"] == 0


def test_v34c_receipt_registers_service_without_advancing_strategy_or_trading(
    tmp_path: Path,
) -> None:
    predecessor = _predecessor(tmp_path)
    summary = initialize_dual_track_successor(
        reports_root=tmp_path,
        predecessor_program_root=predecessor,
        implementation_contract_hash="sha256:v33-contract",
        implementation_commit="commit-v33",
        generated_at="2026-07-19T00:00:00Z",
        writer_id="test-writer",
    )
    root = tmp_path / "dual_track" / summary["programId"]
    record_v34a_data_pilot(
        program_root=root,
        pilot_result={
            "status": "completed",
            "scope": "v34a_data_only",
            "snapshotId": "okx_snapshot_123",
            "candidateCount": 0,
            "formalRunCount": 0,
            "demoReleaseCount": 0,
            "orderCount": 0,
        },
        created_at="2026-07-19T01:00:00Z",
        writer_id="test-writer",
    )
    record_v34b_data_extension(
        program_root=root,
        extension_result={
            "status": "completed",
            "scope": "v34b_public_data_only",
            "snapshotId": "okx_v34b_snapshot_456",
            "candidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "orderCount": 0,
            "demoArm": False,
        },
        created_at="2026-07-19T02:00:00Z",
        writer_id="test-writer",
    )

    updated = record_v34c_public_data_service(
        program_root=root,
        service_result={
            "status": "completed",
            "scope": "v34c_public_data_service_only",
            "dataFoundationServiceId": "okx_public_service_789",
            "policyHash": "sha256:policy-789",
            "latestCycleHash": "sha256:cycle-789",
            "latestQualityStatus": "healthy",
            "cycleLedgerPath": "manifests/v34c/cycle_ledger.jsonl",
            "candidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "orderCount": 0,
            "demoArm": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "privateAccountReadUsed": False,
        },
        created_at="2026-07-19T03:00:00Z",
        writer_id="test-writer",
    )

    assert updated["dataSnapshotId"] == "okx_snapshot_123"
    assert updated["dataFoundationExtensionId"] == "okx_v34b_snapshot_456"
    assert updated["dataFoundationServiceId"] == "okx_public_service_789"
    assert updated["topLevelState"] == "public_data_service_active"
    assert updated["candidateCount"] == 0
    assert updated["formalRunCount"] == 0
    assert updated["resultReadCount"] == 0
    assert updated["lockedOosReadCount"] == 0
    assert updated["releaseCount"] == 0
    assert updated["approvalCount"] == 0
    assert updated["demoArm"] is False
    assert updated["orderCount"] == 0
    state = json.loads((root / "program_state.json").read_text(encoding="utf-8"))
    assert state["dataSnapshotId"] == "okx_snapshot_123"
    assert state["dataFoundationExtensionId"] == "okx_v34b_snapshot_456"
    assert state["dataFoundationServiceId"] == "okx_public_service_789"
    assert state["demoProductTrackState"] == "demo_platform_building"
    master = ProgramLedger(root / "master_program_ledger.jsonl").read_all()
    research = ProgramLedger(root / "research_track_ledger.jsonl").read_all()
    cross_track = ProgramLedger(root / "cross_track_receipt_ledger.jsonl").read_all()
    assert master[-1]["eventType"] == "public_data_service_registered"
    assert research[-1]["eventType"] == "public_data_scheduler_activated"
    assert cross_track[-1]["eventType"] == "public_data_service_receipt_recorded"
