from __future__ import annotations

import unittest

from alphapilot.evolution.forward import (
    ForwardBar,
    ForwardDecision,
    ForwardRiskEnvelope,
    ForwardState,
    process_completed_bar,
)


INTERVAL = 4 * 60 * 60 * 1000


def _state() -> ForwardState:
    return ForwardState(
        forwardSessionId="session_test",
        forwardReleaseId="release_test",
        strategyCandidateId="candidate_test",
        accountId="account_test",
        initialEquity=1000.0,
        cashBalance=1000.0,
        equity=1000.0,
    )


def _bar(timestamp: int, *, high: float = 101.0, low: float = 99.5) -> ForwardBar:
    return ForwardBar(
        instrumentId="BTC-USDT-SWAP",
        timeframe="4h",
        timestampMs=timestamp,
        open=100.0,
        high=high,
        low=low,
        close=100.5,
        volume=1000.0,
    )


class LocalForwardEngineTests(unittest.TestCase):
    def test_signal_fills_only_on_next_bar_and_closes_at_two_r(self) -> None:
        envelope = ForwardRiskEnvelope(feeRate=0.0, slippageRate=0.0)
        first = process_completed_bar(
            _state(),
            _bar(0),
            envelope=envelope,
            decision=ForwardDecision("signal_1", "long", 1.0, {"rsi_14": 25.0}),
        )
        self.assertEqual(len(first.state.openPositions), 0)
        self.assertIn("BTC-USDT-SWAP", first.state.pendingSignals)

        second = process_completed_bar(
            first.state,
            _bar(INTERVAL, high=103.0, low=99.5),
            envelope=envelope,
        )
        self.assertEqual(len(second.closedOutcomes), 1)
        outcome = second.closedOutcomes[0]
        self.assertEqual(outcome["entryTimestampMs"], INTERVAL)
        self.assertEqual(outcome["exitReason"], "target")
        self.assertAlmostEqual(outcome["netR"], 2.0)
        self.assertFalse(outcome["createsOrder"])
        self.assertAlmostEqual(second.state.equity, 1005.0)

    def test_same_bar_ambiguity_is_stop_first(self) -> None:
        envelope = ForwardRiskEnvelope(feeRate=0.0, slippageRate=0.0)
        pending = process_completed_bar(
            _state(),
            _bar(0),
            envelope=envelope,
            decision=ForwardDecision("signal_1", "long", 1.0),
        )
        closed = process_completed_bar(
            pending.state,
            _bar(INTERVAL, high=103.0, low=98.0),
            envelope=envelope,
        )
        outcome = closed.closedOutcomes[0]
        self.assertEqual(outcome["exitReason"], "stop")
        self.assertTrue(outcome["sameBarAmbiguousStopFirst"])

    def test_downtime_records_gap_without_backfilling(self) -> None:
        first = process_completed_bar(_state(), _bar(0))
        resumed = process_completed_bar(first.state, _bar(3 * INTERVAL))
        gaps = [event for event in resumed.events if event["eventType"] == "collection_gap"]
        self.assertEqual(len(gaps), 1)
        self.assertEqual(gaps[0]["payload"]["missingBars"], 2)
        self.assertFalse(gaps[0]["payload"]["backfilledAsForwardEvidence"])


if __name__ == "__main__":
    unittest.main()
