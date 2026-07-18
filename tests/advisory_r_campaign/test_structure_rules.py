from __future__ import annotations

import pandas as pd
import pytest

from alphapilot.advisory_r_campaign.structure_rules import compile_structure_rule
from alphapilot.exit_policy import ExitCosts, exit_policy_from_dict, replay_exit_policy


def _frame(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=len(closes), freq="1h", tz="UTC")
    return pd.DataFrame(
        {
            "date": dates,
            "open": closes,
            "high": [value + 0.2 for value in closes],
            "low": [value - 0.2 for value in closes],
            "close": closes,
            "volume": [1_000.0] * len(closes),
        }
    )


def _candidate(kind: str, **parameters: object) -> dict[str, object]:
    return {
        "variantId": "TEST",
        "featureDefinition": {},
        "exitPolicy": {
            "version": "advisory_r_exit_policy_v1",
            "mode": "structure_or_time",
            "maximumHoldBars": 6,
            "initialStopMayWiden": False,
            "parameters": {"structureRule": {"kind": kind, **parameters}},
        },
    }


def test_event_reversal_requires_two_completed_bars() -> None:
    frame = _frame([100, 101, 102, 101, 100, 99])
    mask = compile_structure_rule(
        _candidate("event_reversal", confirmationBars=2), frame, side=1
    )

    assert not bool(mask.iloc[3])
    assert bool(mask.iloc[4])


def test_structure_trigger_executes_at_next_bar_open() -> None:
    frame = _frame([100, 101, 102, 101, 100, 99])
    candidate = _candidate("event_reversal", confirmationBars=2)
    mask = compile_structure_rule(candidate, frame, side=1)
    result = replay_exit_policy(
        frame=frame,
        signalPosition=1,
        direction="long",
        riskDistance=10.0,
        policy=exit_policy_from_dict(candidate["exitPolicy"]),
        costs=ExitCosts(),
        structureExitMask=mask,
    )

    assert result.legs[-1].triggerPosition == 4
    assert result.legs[-1].executionPosition == 5
    assert result.legs[-1].price == frame.iloc[5]["open"]


def test_residual_neutral_uses_frozen_context_zscore() -> None:
    frame = _frame([100, 100, 100, 100])
    frame["residualZ"] = [-1.2, -0.6, -0.34, -0.1]
    mask = compile_structure_rule(
        _candidate("residual_neutral_zone", absoluteZscoreMaximum=0.35),
        frame,
        side=1,
    )

    assert mask.tolist() == [False, False, True, True]


def test_correlation_recovery_uses_frozen_minimum() -> None:
    frame = _frame([100, 100, 100, 100])
    frame["pairCorrelation"] = [0.2, 0.59, 0.6, 0.8]
    mask = compile_structure_rule(
        _candidate("correlation_recovery", minimumCorrelation=0.6),
        frame,
        side=1,
    )

    assert mask.tolist() == [False, False, True, True]


def test_beta_rank_exit_uses_cross_sectional_rank() -> None:
    frame = _frame([100, 100, 100, 100])
    frame["betaRankPercentile"] = [0.2, 0.4, 0.51, 0.7]
    mask = compile_structure_rule(
        _candidate("beta_rank_exit", maximumRankPercentile=0.5),
        frame,
        side=1,
    )

    assert mask.tolist() == [False, False, True, True]


def test_trend_invalidation_uses_frozen_windows() -> None:
    frame = _frame([100, 101, 102, 103, 102, 101, 100, 99])
    mask = compile_structure_rule(
        _candidate("trend_invalidation", fastWindow=2, slowWindow=4),
        frame,
        side=1,
    )

    assert bool(mask.iloc[-1])


def test_unknown_structure_rule_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported structure rule"):
        compile_structure_rule(_candidate("invented_rule"), _frame([100] * 5), side=1)
