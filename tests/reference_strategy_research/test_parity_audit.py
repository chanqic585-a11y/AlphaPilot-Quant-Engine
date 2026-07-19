from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from alphapilot.reference_strategy_research.candidates import build_selected_candidates
from alphapilot.reference_strategy_research.parity_audit import audit_signal_parity


def _candidate(parent_id: str, direction: str):
    rows = build_selected_candidates(
        [{"candidateId": parent_id, "marketHypothesis": "parity fixture"}]
    )
    return next(row for row in rows if row.direction == direction)


def _session_frame(direction: str) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01T00:00:00Z", periods=32, freq="1h"),
            "open": np.full(32, 100.0),
            "high": np.full(32, 101.0),
            "low": np.full(32, 99.0),
            "close": np.full(32, 100.0),
            "volume": np.full(32, 1000.0),
        }
    )
    if direction == "long":
        frame.loc[24, ["open", "high", "low", "close"]] = [100.0, 103.0, 99.8, 102.5]
        frame.loc[25, ["open", "high", "low", "close"]] = [102.6, 104.0, 102.0, 103.5]
    else:
        frame.loc[24, ["open", "high", "low", "close"]] = [100.0, 100.2, 97.0, 97.5]
        frame.loc[25, ["open", "high", "low", "close"]] = [97.4, 98.0, 96.0, 96.5]
    return frame


def _second_entry_frame(direction: str) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01T00:00:00Z", periods=50, freq="4h"),
            "open": np.full(50, 102.0),
            "high": np.full(50, 104.0),
            "low": np.full(50, 100.0),
            "close": np.full(50, 102.0),
            "volume": np.full(50, 1000.0),
        }
    )
    if direction == "long":
        frame.loc[25, ["open", "high", "low", "close"]] = [101.0, 101.5, 98.5, 99.5]
        frame.loc[26, ["open", "high", "low", "close"]] = [99.7, 102.0, 99.2, 101.0]
        frame.loc[27, ["open", "high", "low", "close"]] = [100.8, 103.5, 99.1, 103.0]
        frame.loc[28, ["open", "high", "low", "close"]] = [103.1, 106.0, 102.5, 105.0]
    else:
        frame.loc[25, ["open", "high", "low", "close"]] = [103.0, 105.5, 102.5, 104.5]
        frame.loc[26, ["open", "high", "low", "close"]] = [104.3, 104.8, 102.0, 103.0]
        frame.loc[27, ["open", "high", "low", "close"]] = [104.2, 104.9, 101.5, 102.0]
        frame.loc[28, ["open", "high", "low", "close"]] = [101.9, 102.5, 99.0, 100.0]
    return frame


@pytest.mark.parametrize("direction", ["long", "short"])
def test_independent_oracle_matches_session_production_signals(direction: str) -> None:
    result = audit_signal_parity(
        candidate=_candidate("ref_utc_session_range_breakout_1h_v1", direction),
        frame=_session_frame(direction),
        fixture_id=f"synthetic_session_{direction}",
        provenance={"kind": "synthetic_known_positive"},
    )

    assert result["parityPassed"] is True
    assert result["productionSignalCount"] == result["oracleSignalCount"] == 1
    assert result["mismatches"] == []


@pytest.mark.parametrize("direction", ["long", "short"])
def test_independent_oracle_matches_second_entry_production_signals(direction: str) -> None:
    result = audit_signal_parity(
        candidate=_candidate("ref_pa_breakout_failure_second_entry_4h_v1", direction),
        frame=_second_entry_frame(direction),
        fixture_id=f"synthetic_second_entry_{direction}",
        provenance={"kind": "synthetic_known_positive"},
    )

    assert result["parityPassed"] is True
    assert result["productionSignalCount"] == result["oracleSignalCount"] == 1
    assert result["mismatches"] == []
