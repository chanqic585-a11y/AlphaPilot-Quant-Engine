from __future__ import annotations

import numpy as np
import pandas as pd

from alphapilot.mechanism_breakthrough.contracts import build_frozen_candidates
from alphapilot.mechanism_breakthrough.mechanisms import (
    audit_funding_carry_episode_semantics,
    detect_spike_pullback_signals,
    rolling_pair_features,
)


def _ohlcv(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2025-01-01", periods=len(closes), freq="h", tz="UTC")
    opens = [closes[0], *closes[:-1]]
    return pd.DataFrame(
        {
            "date": dates,
            "open": opens,
            "high": [max(o, c) + 0.2 for o, c in zip(opens, closes)],
            "low": [min(o, c) - 0.2 for o, c in zip(opens, closes)],
            "close": closes,
            "volume": [100.0] * len(closes),
        }
    )


def test_spike_pullback_confirmation_uses_next_bar_open() -> None:
    quiet = [100.0 + (index % 2) * 0.05 for index in range(25)]
    closes = quiet + [102.0, 104.2, 106.5, 105.8, 105.2, 106.1, 106.4]
    frame = _ohlcv(closes)
    candidate = next(
        row
        for row in build_frozen_candidates()
        if row.candidateId == "v42_spike_pullback_continuation_long_1h_v1"
    )

    signals = detect_spike_pullback_signals(candidate=candidate, frame=frame)

    assert len(signals) == 1
    assert signals[0].entryPosition == signals[0].signalPosition + 1
    assert signals[0].entryPrice == frame.iloc[signals[0].entryPosition]["open"]


def test_dynamic_pair_features_use_only_prior_completed_bars() -> None:
    left = pd.Series(np.linspace(100.0, 130.0, 240))
    right = pd.Series(np.linspace(50.0, 65.0, 240))
    original = rolling_pair_features(left, right, hedge_window=90, z_window=120)
    changed = left.copy()
    changed.iloc[220:] = changed.iloc[220:] * 20.0
    mutated = rolling_pair_features(changed, right, hedge_window=90, z_window=120)

    assert original.loc[219, "hedgeRatio"] == mutated.loc[219, "hedgeRatio"]
    assert original.loc[219, "zScore"] == mutated.loc[219, "zScore"]


def test_funding_semantics_golden_fixture_closes_one_episode_not_each_observation() -> None:
    audit = audit_funding_carry_episode_semantics()

    assert audit["status"] == "funding_carry_current_mechanism_closed"
    assert audit["episodeCount"] == 1
    assert audit["fundingObservationCount"] == 3
    assert audit["openFeeCount"] == 1
    assert audit["closeFeeCount"] == 1
    assert audit["candidateCreated"] is False

