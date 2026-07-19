from __future__ import annotations

import pandas as pd
import pytest

from alphapilot.data_foundation.funding_carry_data import (
    FundingCarryDataPolicy,
    build_causal_funding_carry_panel,
)


def _candle(
    timestamp_ms: int,
    *,
    instrument_id: str,
    close: float,
    quote_turnover: float,
) -> dict[str, object]:
    return {
        "exchange": "OKX",
        "instrumentId": instrument_id,
        "timestamp_ms": timestamp_ms,
        "availableAt": pd.Timestamp(timestamp_ms + 3_600_000, unit="ms", tz="UTC").isoformat(),
        "close": close,
        "volCcyQuote": quote_turnover,
    }


def test_policy_hash_is_stable_and_changes_with_scope() -> None:
    original = FundingCarryDataPolicy.default()
    same = FundingCarryDataPolicy.default()
    changed = FundingCarryDataPolicy.default(assets=("BTC", "ETH"))

    assert original.policy_hash == same.policy_hash
    assert original.policy_hash != changed.policy_hash
    assert original.exchange == "OKX"
    assert original.timeframe == "1h"
    assert original.zero_fill_allowed is False
    assert original.cross_exchange_substitution_allowed is False


def test_panel_alignment_is_causal_and_never_uses_future_candle() -> None:
    spot = pd.DataFrame(
        [
            _candle(0, instrument_id="BTC-USDT", close=99.0, quote_turnover=900.0),
            _candle(3_600_000, instrument_id="BTC-USDT", close=100.0, quote_turnover=1_000.0),
            _candle(7_200_000, instrument_id="BTC-USDT", close=200.0, quote_turnover=2_000.0),
        ]
    )
    perpetual = pd.DataFrame(
        [
            _candle(0, instrument_id="BTC-USDT-SWAP", close=100.0, quote_turnover=1_800.0),
            _candle(3_600_000, instrument_id="BTC-USDT-SWAP", close=102.0, quote_turnover=2_500.0),
            _candle(7_200_000, instrument_id="BTC-USDT-SWAP", close=250.0, quote_turnover=3_000.0),
        ]
    )
    funding = pd.DataFrame(
        [
            {
                "instrument_id": "BTC-USDT-SWAP",
                "timestamp_ms": 7_200_000,
                "available_at": pd.Timestamp(7_200_000, unit="ms", tz="UTC").isoformat(),
                "funding_rate": 0.0001,
            }
        ]
    )

    panel = build_causal_funding_carry_panel(
        asset="BTC",
        spot=spot,
        perpetual=perpetual,
        funding=funding,
        maximum_lag_seconds=3_600,
    )

    assert len(panel) == 1
    row = panel.iloc[0]
    assert row["spotPrice"] == 100.0
    assert row["perpetualPrice"] == 102.0
    assert row["basisPct"] == pytest.approx(2.0)
    assert row["spotSourceTimestampMs"] == 3_600_000
    assert row["perpetualSourceTimestampMs"] == 3_600_000
    assert row["decisionAvailableAtMs"] == 7_200_000
    assert row["spotAvailableAtMs"] <= row["decisionAvailableAtMs"]
    assert row["perpetualAvailableAtMs"] <= row["decisionAvailableAtMs"]
    assert row["dualLegQuoteTurnoverProxy"] == 1_000.0
    assert bool(row["stale"]) is False
    assert row["joinDirection"] == "backward_asof"


def test_panel_staleness_uses_candle_availability_not_candle_open_time() -> None:
    spot = pd.DataFrame(
        [_candle(0, instrument_id="BTC-USDT", close=100.0, quote_turnover=0.0)]
    )
    perpetual = pd.DataFrame(
        [
            _candle(
                0,
                instrument_id="BTC-USDT-SWAP",
                close=101.0,
                quote_turnover=1_200.0,
            )
        ]
    )
    funding = pd.DataFrame(
        [
            {
                "instrument_id": "BTC-USDT-SWAP",
                "timestamp_ms": 3_605_000,
                "available_at": pd.Timestamp(
                    3_605_000, unit="ms", tz="UTC"
                ).isoformat(),
                "funding_rate": 0.0001,
            }
        ]
    )

    panel = build_causal_funding_carry_panel(
        asset="BTC",
        spot=spot,
        perpetual=perpetual,
        funding=funding,
        maximum_lag_seconds=3_600,
    )

    row = panel.iloc[0]
    assert row["spotLagSeconds"] == 5.0
    assert row["perpetualLagSeconds"] == 5.0
    assert row["dualLegQuoteTurnoverProxy"] == 0.0
    assert bool(row["stale"]) is False


def test_panel_rejects_cross_exchange_or_missing_quote_turnover() -> None:
    spot = pd.DataFrame(
        [_candle(0, instrument_id="BTC-USDT", close=100.0, quote_turnover=1_000.0)]
    )
    perpetual = pd.DataFrame(
        [_candle(0, instrument_id="BTC-USDT-SWAP", close=101.0, quote_turnover=1_200.0)]
    )
    perpetual.loc[0, "exchange"] = "Binance"
    funding = pd.DataFrame(
        [
            {
                "instrument_id": "BTC-USDT-SWAP",
                "timestamp_ms": 3_600_000,
                "available_at": pd.Timestamp(3_600_000, unit="ms", tz="UTC").isoformat(),
                "funding_rate": 0.0001,
            }
        ]
    )

    with pytest.raises(ValueError, match="same_exchange"):
        build_causal_funding_carry_panel(
            asset="BTC",
            spot=spot,
            perpetual=perpetual,
            funding=funding,
            maximum_lag_seconds=3_600,
        )
