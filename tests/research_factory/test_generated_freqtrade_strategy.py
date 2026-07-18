from __future__ import annotations

import numpy as np
import pandas as pd

from alphapilot.research_factory.generated_candidate_adapter import (
    GeneratedDirectionalEventAdapter,
)
from alphapilot.research_factory.generated_freqtrade_strategy import (
    translated_load_signals,
    translated_replay,
)


def _frames() -> dict[str, pd.DataFrame]:
    count = 480
    dates = pd.date_range("2023-01-01", periods=count, freq="4h", tz="UTC")
    close = 100 + np.sin(np.arange(count) / 3.0) * 8 + np.arange(count) * 0.01
    open_ = pd.Series(close).shift(1).fillna(close[0])
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": open_,
            "high": np.maximum(open_, close) + 1.0,
            "low": np.minimum(open_, close) - 1.0,
            "close": close,
            "volume": 1000.0,
        }
    )
    return {"BTC-USDT-SWAP": frame, "ETH-USDT-SWAP": frame.copy()}


def _candidate(candidate_id: str = "candidate-a") -> dict[str, object]:
    return {
        "candidateId": candidate_id,
        "direction": "short",
        "entryDefinition": {"setupId": "trend_failure_reversal"},
        "maximumHoldBars": 18,
        "initialStop": {"atrMultiple": 1.25},
        "exitPolicy": {"targetR": 1.5},
    }


def test_actual_frame_signal_and_exit_translation_has_full_parity() -> None:
    candidate = _candidate()
    frames = _frames()
    adapter = GeneratedDirectionalEventAdapter(candidate_id="candidate-a")

    reference_signals = list(adapter.load_signals(candidate=candidate, frames=frames))
    translated_signals = translated_load_signals(candidate=candidate, frames=frames)
    reference_replay = list(
        adapter.replay(candidate=candidate, frames=frames, round_trip_cost_rate=0.0012)
    )
    translated_results = translated_replay(
        candidate=candidate, frames=frames, round_trip_cost_rate=0.0012
    )

    assert reference_signals
    assert reference_signals == translated_signals
    assert reference_replay == translated_results


def test_second_synthetic_candidate_uses_same_candidate_neutral_translation() -> None:
    candidate = _candidate("candidate-b")
    candidate["direction"] = "long"
    adapter = GeneratedDirectionalEventAdapter(candidate_id="candidate-b")

    parity, reference, translated = adapter.run_fixture_parity(candidate=candidate)

    assert reference
    assert reference == translated
    assert parity["passed"] is True
