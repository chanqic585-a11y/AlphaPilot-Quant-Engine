from __future__ import annotations

import unittest

from alphapilot.short_cycle.event_window_candidates import event_window_candidate_pool
from alphapilot.short_cycle.event_window_prescreen import (
    CandidatePrescreenMetrics,
    select_prescreen_candidates,
)


class EventWindowPrescreenTests(unittest.TestCase):
    def test_selection_rejects_negative_cost_adjusted_candidates(self) -> None:
        pool = event_window_candidate_pool()
        metrics = []
        for index, candidate in enumerate(pool):
            metrics.append(
                CandidatePrescreenMetrics(
                    candidateKey=candidate.familyKey,
                    timeframe=candidate.timeframe,
                    signalFamily=candidate.signalFamily,
                    tradeCount=80 + index,
                    profitFactor=1.05 + index / 100,
                    averageNetR=0.03 + index / 1000,
                    totalR=8.0 + index,
                    maximumDrawdownR=4.0,
                    pairCount=8,
                    largestPairShare=0.25,
                    eventsPer1000Candles=2.0,
                )
            )
        rejected_key = pool[0].familyKey
        metrics[0] = CandidatePrescreenMetrics(
            candidateKey=rejected_key,
            timeframe=pool[0].timeframe,
            signalFamily=pool[0].signalFamily,
            tradeCount=500,
            profitFactor=0.7,
            averageNetR=-0.2,
            totalR=-100.0,
            maximumDrawdownR=110.0,
            pairCount=10,
            largestPairShare=0.2,
            eventsPer1000Candles=8.0,
        )

        selection = select_prescreen_candidates(pool, metrics, per_timeframe=5)

        self.assertEqual(len(selection.selected), 10)
        self.assertNotIn(rejected_key, {item.familyKey for item in selection.selected})
        rejected = next(item for item in selection.rejected if item.candidateKey == rejected_key)
        self.assertIn("non_positive_cost_adjusted_expectancy", rejected.reasons)

    def test_selection_enforces_family_diversity(self) -> None:
        pool = event_window_candidate_pool()
        metrics = [
            CandidatePrescreenMetrics(
                candidateKey=candidate.familyKey,
                timeframe=candidate.timeframe,
                signalFamily=candidate.signalFamily,
                tradeCount=100,
                profitFactor=2.0 if candidate.signalFamily == "windowed_trend_reclaim_long" else 1.2,
                averageNetR=0.4 if candidate.signalFamily == "windowed_trend_reclaim_long" else 0.08,
                totalR=40.0,
                maximumDrawdownR=5.0,
                pairCount=10,
                largestPairShare=0.2,
                eventsPer1000Candles=1.5,
            )
            for candidate in pool
        ]

        selection = select_prescreen_candidates(pool, metrics, per_timeframe=5)

        for timeframe in ("5m", "15m"):
            selected = [item for item in selection.selected if item.timeframe == timeframe]
            self.assertEqual(len(selected), 5)
            trend_count = sum(
                item.signalFamily == "windowed_trend_reclaim_long" for item in selected
            )
            self.assertLessEqual(trend_count, 2)


if __name__ == "__main__":
    unittest.main()
