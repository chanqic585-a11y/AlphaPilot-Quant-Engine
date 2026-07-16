from __future__ import annotations

from alphapilot.derivatives_data.forward_collection import build_forward_collection_plan


def test_forward_collection_is_append_only_public_data_and_not_historical_formal() -> None:
    result = build_forward_collection_plan(
        capabilities={
            "open_interest": True,
            "funding": True,
            "spot_ohlcv": True,
            "perpetual_ohlcv": True,
            "basis": True,
            "instrument_state": True,
            "pit_liquidity": True,
            "spread": True,
            "liquidation": False,
        },
        budget={"maximumRequestsPerMinute": 60, "maximumRunHours": 6},
    )

    assert result["appendOnly"] is True
    assert result["resumable"] is True
    assert result["publicDataOnly"] is True
    assert result["accountAccess"] is False
    assert result["orderCreation"] is False
    assert result["historicalFormalReady"] is False
    assert result["futureCollectionReady"] is True
    liquidation = next(row for row in result["streams"] if row["dataType"] == "liquidation")
    assert liquidation["status"] == "unavailable"
