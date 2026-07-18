from __future__ import annotations
from alphapilot.formal_validation.signal_ranking_policy import rank_signal_batch_v1


def _signal(
    instrument: str,
    residual: float | None,
    recovery: float | None,
    liquidity: float | None,
) -> dict[str, object]:
    return {
        "signalId": instrument,
        "instrumentId": instrument,
        "entryTimestamp": "2026-01-01T04:00:00Z",
        "eventExtremeResidualZ": residual,
        "recoverySizeZ": recovery,
        "liquidity30d": liquidity,
    }


def test_ranking_is_frozen_and_missing_fields_are_rejected() -> None:
    result = rank_signal_batch_v1(
        [
            _signal("SOL", -2.0, 1.0, 10.0),
            _signal("BTC", -3.0, 0.5, 100.0),
            _signal("ETH", -2.0, 2.0, 50.0),
            _signal("BAD", None, 9.0, 999.0),
        ]
    )

    assert [row["instrumentId"] for row in result["ranked"]] == ["BTC", "ETH", "SOL"]
    assert result["rejected"][0]["instrumentId"] == "BAD"
    assert result["rejected"][0]["reason"] == "missing_ranking_field"


def test_ranking_rejects_mixed_entry_timestamps() -> None:
    later = _signal("ETH", -2.0, 1.0, 10.0)
    later["entryTimestamp"] = "2026-01-01T05:00:00Z"

    result = rank_signal_batch_v1([_signal("BTC", -3.0, 1.0, 10.0), later])

    assert result["ranked"] == []
    assert {row["reason"] for row in result["rejected"]} == {"mixed_entry_timestamp"}
