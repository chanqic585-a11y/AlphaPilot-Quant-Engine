from __future__ import annotations

from alphapilot.formal_validation.ranking_evidence import (
    audit_ranking_evidence_record_parity,
    materialize_ranking_evidence_records,
)


def _assigned(signal_id: str = "signal-1") -> dict[str, object]:
    return {
        "signalId": signal_id,
        "canonicalSignalId": signal_id,
        "candidateId": "candidate-s01",
        "instrumentId": "BTC-USDT-SWAP",
        "signalTimestamp": "2026-01-01T04:00:00Z",
        "entryTimestamp": "2026-01-01T08:00:00Z",
        "foldId": "fold-1",
    }


def _feature(signal_id: str = "signal-1") -> dict[str, object]:
    return {
        "signalId": signal_id,
        "eventExtremeResidualZ": -2.7,
        "recoverySizeZ": 0.5,
        "liquidity30d": 5_000_000.0,
        "availableAt": "2026-01-01T04:00:00Z",
        "sourceBarHashes": ["bar-a", "bar-b"],
    }


def test_every_assigned_event_gets_a_complete_available_ranking_record() -> None:
    rows, audit = materialize_ranking_evidence_records(
        [_assigned()],
        [_feature()],
        ranking_policy_hash="rank-hash",
        capacity_semantics_hash="capacity-hash",
    )

    assert len(rows) == 1
    assert rows[0]["rankingEvidenceStatus"] == "available"
    assert rows[0]["eventExtremeResidualZStatus"] == "available"
    assert rows[0]["recoverySizeZStatus"] == "available"
    assert rows[0]["liquidity30dStatus"] == "available"
    assert rows[0]["rankingUnavailableReason"] is None
    assert rows[0]["availableAt"] == "2026-01-01T04:00:00Z"
    assert rows[0]["rankingEvidenceHash"]
    assert audit["recordCoveragePct"] == 100.0
    assert audit["statusCoveragePct"] == 100.0
    assert audit["postEntryDataUseCount"] == 0


def test_missing_features_remain_as_stable_rejection_records_not_dropped() -> None:
    feature = _feature()
    feature["eventExtremeResidualZ"] = None
    feature["liquidity30d"] = None
    rows, audit = materialize_ranking_evidence_records(
        [_assigned()],
        [feature],
        ranking_policy_hash="rank-hash",
        capacity_semantics_hash="capacity-hash",
    )

    assert len(rows) == 1
    assert rows[0]["eventExtremeResidualZStatus"] == "unavailable_insufficient_history"
    assert rows[0]["liquidity30dStatus"] == "unavailable_volume_semantics"
    assert (
        rows[0]["rankingEvidenceStatus"]
        == "unavailable_insufficient_history"
    )
    assert rows[0]["rankingUnavailableReason"] == (
        "eventExtremeResidualZ:unavailable_insufficient_history;"
        "liquidity30d:unavailable_volume_semantics"
    )
    assert rows[0]["rankingEvidenceHash"]
    assert audit["recordCoveragePct"] == 100.0
    assert audit["unavailableRecordCount"] == 1


def test_record_parity_compares_status_provenance_and_rejection_reason() -> None:
    core, _ = materialize_ranking_evidence_records(
        [_assigned()],
        [_feature()],
        ranking_policy_hash="rank-hash",
        capacity_semantics_hash="capacity-hash",
    )
    adapter, _ = materialize_ranking_evidence_records(
        [_assigned()],
        [_feature()],
        ranking_policy_hash="rank-hash",
        capacity_semantics_hash="capacity-hash",
    )
    parity = audit_ranking_evidence_record_parity(core, adapter)

    assert parity["recordCoveragePct"] == 100.0
    assert parity["statusCoveragePct"] == 100.0
    assert parity["fieldParityPct"] == 100.0
    assert parity["hashParityPct"] == 100.0
    assert parity["rejectionReasonParityPct"] == 100.0
    assert parity["postEntryDataUseCount"] == 0

    adapter[0]["liquidity30dStatus"] = "unavailable_volume_semantics"
    mismatch = audit_ranking_evidence_record_parity(core, adapter)
    assert mismatch["statusCoveragePct"] < 100.0
    assert mismatch["fieldParityPct"] < 100.0


def test_capacity_semantics_hash_is_bound_per_instrument() -> None:
    second = _assigned("signal-2")
    second["instrumentId"] = "ETH-USDT-SWAP"
    second_feature = _feature("signal-2")
    rows, _ = materialize_ranking_evidence_records(
        [_assigned(), second],
        [_feature(), second_feature],
        ranking_policy_hash="rank-hash",
        capacity_semantics_hash={
            "BTC-USDT-SWAP": "capacity-btc",
            "ETH-USDT-SWAP": "capacity-eth",
        },
    )

    assert [row["capacitySemanticsHash"] for row in rows] == [
        "capacity-btc",
        "capacity-eth",
    ]
