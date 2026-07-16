from __future__ import annotations

import pandas as pd
import pytest

from alphapilot.exit_policy import ExitPolicy, ExitPolicyMode
from alphapilot.exit_policy.engine import replay_exit_policy
from alphapilot.exit_policy.exit_legs import ExitCosts


def _frame(rows: list[tuple[float, float, float, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=len(rows), freq="h", tz="UTC"),
            "open": [row[0] for row in rows],
            "high": [row[1] for row in rows],
            "low": [row[2] for row in rows],
            "close": [row[3] for row in rows],
        }
    )


ZERO_COSTS = ExitCosts()


def test_fixed_target_below_two_r_uses_next_bar_open_entry() -> None:
    frame = _frame(
        [
            (99, 101, 98, 100),
            (100, 112, 99, 110),
            (110, 116, 108, 115),
        ]
    )
    policy = ExitPolicy(
        mode=ExitPolicyMode.FIXED_R,
        maximumHoldBars=5,
        parameters={"targetR": 1.5},
    )

    result = replay_exit_policy(
        frame=frame,
        signalPosition=0,
        direction="long",
        riskDistance=10,
        policy=policy,
        costs=ZERO_COSTS,
    )

    assert result.entryPosition == 1
    assert result.entryPrice == 100
    assert result.legs[0].price == 115
    assert result.legs[0].grossR == pytest.approx(1.5)
    assert result.exitPolicy.mode is ExitPolicyMode.FIXED_R


def test_same_bar_stop_and_target_is_stop_first() -> None:
    frame = _frame([(99, 100, 98, 99), (100, 125, 85, 105)])
    policy = ExitPolicy(
        mode=ExitPolicyMode.FIXED_R,
        maximumHoldBars=2,
        parameters={"targetR": 2.0},
    )

    result = replay_exit_policy(
        frame=frame,
        signalPosition=0,
        direction="long",
        riskDistance=10,
        policy=policy,
        costs=ZERO_COSTS,
    )

    assert result.ambiguousPath is True
    assert result.legs[0].reason == "stop_loss"
    assert result.legs[0].price == 90
    assert result.netR == pytest.approx(-1.0)


def test_partial_exit_allocates_leg_weights_and_costs() -> None:
    frame = _frame(
        [
            (99, 100, 98, 99),
            (100, 111, 99, 110),
            (110, 112, 106, 111),
            (111, 112, 104, 105),
        ]
    )
    policy = ExitPolicy(
        mode=ExitPolicyMode.PARTIAL_THEN_TRAILING,
        maximumHoldBars=5,
        parameters={
            "partialAtR": 1.0,
            "partialFraction": 0.4,
            "trailingAtrMultiple": 1.0,
        },
    )

    result = replay_exit_policy(
        frame=frame,
        signalPosition=0,
        direction="long",
        riskDistance=10,
        policy=policy,
        costs=ExitCosts(
            feeBpsPerSide=10,
            slippageBpsPerSide=5,
            spreadBpsPerSide=5,
        ),
        atrValues=pd.Series([5.0, 5.0, 5.0, 5.0]),
    )

    assert [leg.fraction for leg in result.legs] == pytest.approx([0.4, 0.6])
    assert sum(leg.fraction for leg in result.legs) == pytest.approx(1.0)
    assert result.feesR == pytest.approx(sum(leg.feesR for leg in result.legs))
    assert result.slippageR == pytest.approx(sum(leg.slippageR for leg in result.legs))
    assert result.spreadProxyR == pytest.approx(
        sum(leg.spreadProxyR for leg in result.legs)
    )
    assert result.netR == pytest.approx(
        result.grossR
        - result.feesR
        - result.slippageR
        - result.spreadProxyR
        - result.fundingR
    )


def test_trailing_stop_tightens_and_activates_on_next_bar_only() -> None:
    frame = _frame(
        [
            (99, 100, 98, 99),
            (100, 111, 99, 110),
            (110, 114, 106, 113),
            (113, 114, 107, 108),
        ]
    )
    policy = ExitPolicy(
        mode=ExitPolicyMode.PARTIAL_THEN_TRAILING,
        maximumHoldBars=5,
        parameters={
            "partialAtR": 1.0,
            "partialFraction": 0.5,
            "trailingAtrMultiple": 1.0,
        },
    )

    result = replay_exit_policy(
        frame=frame,
        signalPosition=0,
        direction="long",
        riskDistance=10,
        policy=policy,
        costs=ZERO_COSTS,
        atrValues=pd.Series([5.0, 5.0, 5.0, 5.0]),
    )

    trailing_leg = result.legs[-1]
    assert trailing_leg.reason == "trailing_stop"
    assert trailing_leg.executionPosition == 3
    assert trailing_leg.price == 108
    assert result.stopHistory == pytest.approx((90, 105, 108))
    assert all(
        later >= earlier
        for earlier, later in zip(result.stopHistory, result.stopHistory[1:])
    )


def test_structure_trigger_executes_at_next_bar_open() -> None:
    frame = _frame(
        [
            (99, 100, 98, 99),
            (100, 105, 97, 103),
            (103, 108, 101, 107),
            (104, 106, 102, 105),
        ]
    )
    policy = ExitPolicy(
        mode=ExitPolicyMode.STRUCTURE_OR_TIME,
        maximumHoldBars=10,
        parameters={
            "structureRule": {
                "kind": "event_reversal",
                "confirmationBars": 1,
            }
        },
    )

    result = replay_exit_policy(
        frame=frame,
        signalPosition=0,
        direction="long",
        riskDistance=10,
        policy=policy,
        costs=ZERO_COSTS,
        structureExitMask=pd.Series([False, False, True, False]),
    )

    assert result.legs[0].reason == "structure_exit"
    assert result.legs[0].triggerPosition == 2
    assert result.legs[0].executionPosition == 3
    assert result.legs[0].price == 104


def test_adverse_gap_through_stop_fills_at_open() -> None:
    frame = _frame(
        [
            (99, 100, 98, 99),
            (100, 105, 95, 100),
            (85, 92, 82, 90),
        ]
    )
    policy = ExitPolicy(
        mode=ExitPolicyMode.FIXED_R,
        maximumHoldBars=3,
        parameters={"targetR": 1.0},
    )

    result = replay_exit_policy(
        frame=frame,
        signalPosition=0,
        direction="long",
        riskDistance=10,
        policy=policy,
        costs=ZERO_COSTS,
    )

    assert result.legs[0].reason == "stop_gap"
    assert result.legs[0].price == 85
    assert result.legs[0].isGapFill is True
    assert result.grossR == pytest.approx(-1.5)


def test_favorable_gap_through_fixed_target_uses_preregistered_target_price() -> None:
    frame = _frame(
        [
            (99, 100, 98, 99),
            (100, 105, 95, 100),
            (115, 118, 112, 116),
        ]
    )
    policy = ExitPolicy(
        mode=ExitPolicyMode.FIXED_R,
        maximumHoldBars=3,
        parameters={"targetR": 1.0},
    )

    result = replay_exit_policy(
        frame=frame,
        signalPosition=0,
        direction="long",
        riskDistance=10,
        policy=policy,
        costs=ZERO_COSTS,
    )

    assert result.legs[0].reason == "target_gap"
    assert result.legs[0].price == 110
    assert result.legs[0].isGapFill is True
    assert result.grossR == pytest.approx(1.0)


def test_gap_through_partial_target_records_partial_gap_before_intrabar_path() -> None:
    frame = _frame(
        [
            (99, 100, 98, 99),
            (100, 104, 96, 101),
            (112, 114, 103, 105),
            (105, 106, 99, 100),
        ]
    )
    policy = ExitPolicy(
        mode=ExitPolicyMode.PARTIAL_THEN_TRAILING,
        maximumHoldBars=4,
        parameters={
            "partialAtR": 1.0,
            "partialFraction": 0.4,
            "trailingAtrMultiple": 1.0,
        },
    )

    result = replay_exit_policy(
        frame=frame,
        signalPosition=0,
        direction="long",
        riskDistance=10,
        policy=policy,
        costs=ZERO_COSTS,
        atrValues=pd.Series([5.0, 5.0, 5.0, 5.0]),
    )

    assert result.legs[0].reason == "partial_gap"
    assert result.legs[0].price == 110
    assert result.legs[0].fraction == pytest.approx(0.4)
    assert result.legs[0].isGapFill is True


def test_gap_through_active_trailing_stop_uses_open_and_actual_weighted_r() -> None:
    frame = _frame(
        [
            (99, 100, 98, 99),
            (100, 112, 99, 111),
            (112, 114, 108, 113),
            (98, 101, 95, 99),
        ]
    )
    policy = ExitPolicy(
        mode=ExitPolicyMode.PARTIAL_THEN_TRAILING,
        maximumHoldBars=5,
        parameters={
            "partialAtR": 1.0,
            "partialFraction": 0.5,
            "trailingAtrMultiple": 1.0,
        },
    )

    result = replay_exit_policy(
        frame=frame,
        signalPosition=0,
        direction="long",
        riskDistance=10,
        policy=policy,
        costs=ZERO_COSTS,
        atrValues=pd.Series([5.0, 5.0, 5.0, 5.0]),
    )

    assert result.legs[-1].reason == "trailing_gap"
    assert result.legs[-1].price == 98
    assert result.legs[-1].grossR == pytest.approx(-0.1)
    assert result.grossR == pytest.approx(0.4)


def test_result_reports_path_excursions_and_giveback() -> None:
    frame = _frame(
        [
            (99, 100, 98, 99),
            (100, 112, 96, 108),
            (108, 118, 105, 116),
            (116, 117, 107, 110),
        ]
    )
    policy = ExitPolicy(
        mode=ExitPolicyMode.STRUCTURE_OR_TIME,
        maximumHoldBars=3,
        parameters={
            "structureRule": {
                "kind": "event_reversal",
                "confirmationBars": 1,
            }
        },
    )

    result = replay_exit_policy(
        frame=frame,
        signalPosition=0,
        direction="long",
        riskDistance=10,
        policy=policy,
        costs=ZERO_COSTS,
        structureExitMask=pd.Series([False, False, True, False]),
    )

    assert result.mfeR == pytest.approx(1.8)
    assert result.maeR == pytest.approx(-0.4)
    assert result.grossR == pytest.approx(1.6)
    assert result.givebackR == pytest.approx(0.2)
