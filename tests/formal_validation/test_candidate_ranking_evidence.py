from __future__ import annotations

from alphapilot.formal_validation.candidate_ranking_contract import (
    build_candidate_ranking_contract,
)
from alphapilot.formal_validation.candidate_ranking_evidence import (
    materialize_candidate_ranking_evidence,
)


def _contract() -> dict[str, object]:
    slot = {
        "semanticDefinition": "fixture magnitude",
        "sourceVariables": ["close"],
        "formula": "abs(close)",
        "normalization": "none",
        "lookback": 1,
        "order": "descending",
        "availableAt": "signal_close",
        "pointInTimeRule": "closed bar only",
        "missingPolicy": "reject_signal",
    }
    return build_candidate_ranking_contract(
        candidate_id="synthetic-a",
        family_id="family-a",
        primary_event_severity=slot,
        confirmation_strength=slot,
        liquidity_30d={
            "dataProfileHash": "profile-hash",
            "formula": "prior turnover",
            "lookback": 30,
            "order": "descending",
            "availableAt": "signal_close",
            "missingPolicy": "reject_signal",
        },
        instrument_id={"order": "ascending", "exactCanonicalIdentity": True},
    )


def test_evidence_is_complete_causal_and_candidate_neutral() -> None:
    signals = [
        {
            "signalId": "sig-1",
            "candidateId": "synthetic-a",
            "instrumentId": "BTC-USDT-SWAP",
            "signalTimestamp": "2026-01-01T00:00:00Z",
            "expectedEntryTimestamp": "2026-01-01T01:00:00Z",
        },
        {
            "signalId": "sig-2",
            "candidateId": "synthetic-a",
            "instrumentId": "ETH-USDT-SWAP",
            "signalTimestamp": "2026-01-01T00:00:00Z",
            "expectedEntryTimestamp": "2026-01-01T01:00:00Z",
        },
    ]
    rows = [
        {
            "signalId": "sig-1",
            "primaryEventSeverity": 2.2,
            "confirmationStrength": 0.8,
            "liquidity30d": 1_000_000.0,
            "availableAt": "2026-01-01T00:00:00Z",
            "sourceHash": "source-1",
        },
        {
            "signalId": "sig-2",
            "primaryEventSeverity": 1.7,
            "confirmationStrength": 0.4,
            "liquidity30d": 900_000.0,
            "availableAt": "2026-01-01T00:00:00Z",
            "sourceHash": "source-2",
        },
    ]

    records, certification = materialize_candidate_ranking_evidence(
        signals=signals, ranking_rows=rows, contract=_contract()
    )

    assert len(records) == 2
    assert certification["rankingRecordCoveragePct"] == 100.0
    assert certification["requiredRankingAvailabilityPct"] == 100.0
    assert certification["postEntryReadCount"] == 0
    assert certification["economicReadCount"] == 0
    assert certification["status"] == "passed"


def test_evidence_fails_closed_for_post_entry_or_missing_values() -> None:
    signals = [
        {
            "signalId": "sig-1",
            "candidateId": "synthetic-a",
            "instrumentId": "BTC-USDT-SWAP",
            "signalTimestamp": "2026-01-01T00:00:00Z",
            "expectedEntryTimestamp": "2026-01-01T01:00:00Z",
        }
    ]
    records, certification = materialize_candidate_ranking_evidence(
        signals=signals,
        ranking_rows=[
            {
                "signalId": "sig-1",
                "primaryEventSeverity": None,
                "confirmationStrength": 0.8,
                "liquidity30d": 1_000_000.0,
                "availableAt": "2026-01-01T02:00:00Z",
                "sourceHash": "source-1",
            }
        ],
        contract=_contract(),
    )

    assert records[0]["rankingEvidenceStatus"] == "rejected"
    assert certification["requiredRankingAvailabilityPct"] == 0.0
    assert certification["postEntryReadCount"] == 1
    assert certification["status"] == "failed"
