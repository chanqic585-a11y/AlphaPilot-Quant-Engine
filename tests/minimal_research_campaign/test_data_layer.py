from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from alphapilot.minimal_research_campaign.data_layer import (
    profile_ohlcv_frame,
    select_core_universe,
)


def _profile(
    instrument: str,
    timeframe: str,
    *,
    months: int,
    coverage: float,
    activity: float,
    cutoff_days_ago: int,
) -> dict[str, object]:
    cutoff = datetime(2026, 7, 15, tzinfo=UTC) - timedelta(days=cutoff_days_ago)
    return {
        "instrumentId": instrument,
        "exchange": "okx",
        "marketType": "swap",
        "timeframe": timeframe,
        "effectiveBacktestStart": (cutoff - timedelta(days=months * 30)).isoformat(),
        "latestConfirmed": cutoff.isoformat(),
        "historyMonths": months,
        "coveragePct": coverage,
        "missingRatePct": 100.0 - coverage,
        "liquidityScore": activity,
        "sourceTraceable": True,
        "contractActive": True,
        "symbolMappingStable": True,
        "filePath": f"canonical/{instrument}/{timeframe}.parquet",
        "sha256": f"sha-{instrument}-{timeframe}",
        "rowCount": 10_000,
    }


def test_profile_excludes_unconfirmed_zero_volume_and_flat_leading_placeholders() -> None:
    dates = pd.date_range("2024-01-01", periods=6, freq="4h", tz="UTC")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [10, 10, 10, 10, 10.5, 10.7],
            "high": [10, 10, 10, 10.8, 10.9, 11.0],
            "low": [10, 10, 10, 9.8, 10.1, 10.5],
            "close": [10, 10, 10, 10.5, 10.7, 10.8],
            "volume": [0, 0, 5, 8, 9, 10],
            "confirmed": [False, True, True, True, True, False],
        }
    )

    profile = profile_ohlcv_frame(
        frame,
        instrument_id="BTC-USDT-SWAP",
        timeframe="4h",
        file_path="btc.parquet",
        file_hash="abc",
    )

    assert profile["effectiveBacktestStart"] == dates[3].isoformat()
    assert profile["latestConfirmed"] == dates[4].isoformat()
    assert profile["excludedLeadingRows"] == 3
    assert profile["excludedTailRows"] == 1


def test_core_selection_is_deterministic_and_uses_common_cutoff() -> None:
    profiles: list[dict[str, object]] = []
    for index in range(24):
        instrument = f"C{index:02d}-USDT-SWAP"
        for timeframe in ("1h", "4h"):
            profiles.append(
                _profile(
                    instrument,
                    timeframe,
                    months=48 - index,
                    coverage=99.5 - index * 0.1,
                    activity=100.0 - index,
                    cutoff_days_ago=index % 3,
                )
            )

    first = select_core_universe(
        profiles,
        target_size=20,
        required_timeframes=("1h", "4h"),
    )
    second = select_core_universe(
        list(reversed(profiles)),
        target_size=20,
        required_timeframes=("1h", "4h"),
    )

    assert [row["instrumentId"] for row in first["members"]] == [
        row["instrumentId"] for row in second["members"]
    ]
    assert len(first["members"]) == 20
    assert first["cohortType"] == "fixed_core_cohort"
    assert first["historicalPitUniverse"] is False
    selected = {row["instrumentId"] for row in first["members"]}
    expected_4h_cutoff = min(
        str(row["latestConfirmed"])
        for row in profiles
        if row["timeframe"] == "4h" and row["instrumentId"] in selected
    )
    assert first["commonCutoffByTimeframe"]["4h"] == expected_4h_cutoff


def test_core_selection_rejects_strategy_performance_fields() -> None:
    profiles = [
        {
            **_profile(
                "BTC-USDT-SWAP",
                timeframe,
                months=48,
                coverage=99.9,
                activity=100.0,
                cutoff_days_ago=0,
            ),
            "profitFactor": 2.0,
        }
        for timeframe in ("1h", "4h")
    ]

    with pytest.raises(ValueError, match="strategy performance"):
        select_core_universe(
            profiles,
            target_size=1,
            required_timeframes=("1h", "4h"),
        )
