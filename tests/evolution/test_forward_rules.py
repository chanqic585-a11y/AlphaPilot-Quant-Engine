from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from alphapilot.evolution.forward.rules import (
    evaluate_frozen_policy,
    is_supported_frozen_policy,
)
from alphapilot.short_cycle.parameter_search import add_indicators
from alphapilot.short_cycle.workflow_candidates import (
    short_cycle_workflow_candidates,
)


def make_frame(instrument: str, *, btc_crash: bool = False) -> pd.DataFrame:
    interval = 300_000
    timestamps = np.arange(260, dtype="int64") * interval + 1_700_000_000_000
    close = 100.0 + np.sin(np.arange(260) / 6.0) * 0.1
    close[-1] = 94.0 if btc_crash else 102.0
    frame = pd.DataFrame(
        {
            "timestamp_ms": timestamps,
            "date": pd.to_datetime(timestamps, unit="ms", utc=True),
            "open": close - 0.05,
            "high": close + 0.2,
            "low": close - 0.2,
            "close": close,
            "volume": np.full(260, 100.0),
            "instrument_id": instrument,
            "timeframe": "5m",
        }
    )
    frame.loc[frame.index[-1], "volume"] = 250.0
    return frame


class ForwardRuleTests(unittest.TestCase):
    def policy(self) -> dict:
        candidate = short_cycle_workflow_candidates()[0]
        policy = candidate.definition()["forwardSignalPolicy"]
        return {
            **policy,
            "parameters": {
                **policy["parameters"],
                "lookback": 20,
                "rsi_max": 100,
                "volume_min": 1.1,
            },
        }

    def test_short_cycle_policy_uses_same_rules_and_signal_bar_atr(self) -> None:
        eth = make_frame("ETH-USDT-SWAP")
        btc = make_frame("BTC-USDT-SWAP")

        result = evaluate_frozen_policy(
            eth,
            policy=self.policy(),
            release_id="release-short-cycle",
            instrument_id="ETH-USDT-SWAP",
            reference_frames={"BTC-USDT-SWAP": btc},
        )

        self.assertEqual(result.status, "signal")
        assert result.decision is not None
        expected_atr = float(add_indicators(eth)["atr14"].iloc[-1])
        self.assertAlmostEqual(
            result.decision.riskDistance,
            expected_atr * float(self.policy()["parameters"]["stop_atr"]),
        )
        self.assertEqual(result.decision.direction, "long")

    def test_short_cycle_policy_fails_closed_on_btc_shock_or_unknown_family(self) -> None:
        eth = make_frame("ETH-USDT-SWAP")
        blocked = evaluate_frozen_policy(
            eth,
            policy=self.policy(),
            release_id="release-short-cycle",
            instrument_id="ETH-USDT-SWAP",
            reference_frames={
                "BTC-USDT-SWAP": make_frame("BTC-USDT-SWAP", btc_crash=True)
            },
        )
        invalid = evaluate_frozen_policy(
            eth,
            policy={**self.policy(), "signalFamily": "unknown-family"},
            release_id="release-short-cycle",
            instrument_id="ETH-USDT-SWAP",
            reference_frames={"BTC-USDT-SWAP": make_frame("BTC-USDT-SWAP")},
        )

        self.assertIsNone(blocked.decision)
        self.assertEqual(blocked.status, "conditions_not_met")
        self.assertIsNone(invalid.decision)
        self.assertEqual(invalid.status, "invalid_frozen_policy")

    def test_one_hour_short_cycle_policy_is_supported_for_local_forward(self) -> None:
        policy = {**self.policy(), "timeframe": "1h"}

        self.assertTrue(is_supported_frozen_policy(policy))


if __name__ == "__main__":
    unittest.main()
