from __future__ import annotations

import numpy as np
import pandas as pd

from alphapilot.advisory_r_campaign.pair_replay import _signals as pair_signals
from alphapilot.advisory_r_campaign.signals import (
    _signal_series,
    weak_signal_correlation_audit,
)


def _frame(closes: list[float], *, hours: list[int] | None = None) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="1h", tz="UTC")
    if hours is not None:
        dates = pd.DatetimeIndex(
            [pd.Timestamp(f"2026-01-{index // 24 + 1:02d} {hour:02d}:00", tz="UTC") for index, hour in enumerate(hours)]
        )
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [value + 0.5 for value in closes],
            "low": [value - 0.5 for value in closes],
            "close": closes,
            "volume": [1_500.0] * len(closes),
        }
    )


def _series(values: list[float], dates: pd.Series) -> pd.Series:
    return pd.Series(values, index=pd.DatetimeIndex(dates))


def test_s01_requires_two_consecutive_recovery_bars(monkeypatch) -> None:
    frame = _frame([100.0] * 220)
    residual_z = pd.Series([-1.0] * 216 + [-2.4, -2.3, -1.9, -1.8])
    monkeypatch.setattr("alphapilot.advisory_r_campaign.signals._rolling_z", lambda *_: residual_z)
    candidate = {
        "variantId": "S01",
        "featureDefinition": {
            "marketRegime": "btc_close_below_ema_200",
            "residualWindow": 3,
            "residualZMaximum": -2.25,
            "recoveryBars": 2,
        },
        "entryDefinition": {"minimumRecoveryZ": 0.35},
    }
    btc = _series([120.0 - index * 0.2 for index in range(220)], frame["date"])
    market = _series([100.0] * 220, frame["date"])

    signal = _signal_series(candidate, frame, btc_close=btc, market_close=market)

    assert signal.iloc[-3] == 0
    assert signal.iloc[-2] == 1


def test_s02_uses_prior_lagged_impulse_and_high_beta_filter(monkeypatch) -> None:
    frame = _frame([100, 100, 100, 100, 100, 100])
    impulse_z = pd.Series([0.0, 2.4, 0.0, 0.0, 0.0, 0.0])
    monkeypatch.setattr("alphapilot.advisory_r_campaign.signals._rolling_z", lambda *_: impulse_z)
    candidate = {
        "variantId": "S02",
        "featureDefinition": {"btcImpulseZ": 2.0, "lagWindow": 3, "betaWindow": 168},
        "entryDefinition": {"maximumFollowerMoveFraction": 0.45},
    }
    btc = _series([100, 110, 110, 110, 110, 110], frame["date"])
    market = _series([100] * 6, frame["date"])
    high_beta = pd.Series([0.9] * 6)

    signal = _signal_series(
        candidate,
        frame,
        btc_close=btc,
        market_close=market,
        beta_rank=high_beta,
    )

    assert signal.iloc[1] == 0
    assert signal.iloc[2] == 1


def test_s03_requires_frozen_two_bar_confirmation(monkeypatch) -> None:
    frame = _frame([100, 100, 108, 106, 104, 104])
    impulse_z = pd.Series([0.0, 2.5, 0.0, 0.0, 0.0, 0.0])
    monkeypatch.setattr("alphapilot.advisory_r_campaign.signals._rolling_z", lambda *_: impulse_z)
    candidate = {
        "variantId": "S03",
        "featureDefinition": {"btcImpulseZ": 2.0, "lagWindow": 3, "overreactionRatio": 1.1},
        "entryDefinition": {"confirmationBars": 2},
    }
    btc = _series([100, 104, 104, 104, 104, 104], frame["date"])
    market = _series([100] * 6, frame["date"])

    signal = _signal_series(candidate, frame, btc_close=btc, market_close=market)

    assert signal.iloc[3] == 0
    assert signal.iloc[4] == -1


def test_s08_uses_direction_from_prior_bars_not_current_bar() -> None:
    frame = _frame([100, 101, 102, 103, 90], hours=[1, 2, 3, 4, 7])
    candidate = {
        "variantId": "S08",
        "featureDefinition": {
            "utcEntryHours": [7],
            "trendWindow": 3,
            "minimumVolumeRatio": 0.5,
        },
        "entryDefinition": {"directionFromPriorBars": 3},
    }
    btc = _series([100] * 5, frame["date"])
    market = _series([100] * 5, frame["date"])

    signal = _signal_series(candidate, frame, btc_close=btc, market_close=market)

    assert signal.iloc[-1] == 1


def test_s05_consumes_frozen_baseline_and_two_turn_bars() -> None:
    candidate = {
        "variantId": "S05",
        "featureDefinition": {
            "baselineMinimum": 0.75,
            "breakMaximum": 0.25,
        },
        "entryDefinition": {"residualTurnBars": 2},
    }
    metrics = pd.DataFrame(
        {
            "correlationBaseline": [0.80, 0.80, 0.80, 0.80],
            "pairCorrelation": [0.20, 0.20, 0.20, 0.20],
            "residual": [0.04, 0.03, 0.02, 0.01],
        }
    )

    signal = pair_signals(candidate, metrics)

    assert signal.iloc[1] == 0
    assert signal.iloc[2] == -1


def test_s10_weak_signal_correlation_audit_uses_three_frozen_components() -> None:
    components = pd.DataFrame(
        {
            "residual_turn": [1, 0, -1, 1, -1, 0],
            "volume_surprise": [0, 1, -1, 0, 1, -1],
            "trend_slope": [1, 1, 1, -1, -1, -1],
        }
    )

    audit = weak_signal_correlation_audit(components)

    assert audit["componentNames"] == [
        "residual_turn",
        "volume_surprise",
        "trend_slope",
    ]
    assert set(audit["correlationMatrix"]) == set(audit["componentNames"])
    assert np.isclose(
        audit["correlationMatrix"]["residual_turn"]["residual_turn"],
        1.0,
    )
