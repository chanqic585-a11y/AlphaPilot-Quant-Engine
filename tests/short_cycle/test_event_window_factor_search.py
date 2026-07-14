from __future__ import annotations

import unittest

from alphapilot.short_cycle.event_window_factor_search import (
    discover_robust_factor_guards,
)


class EventWindowFactorSearchTests(unittest.TestCase):
    @staticmethod
    def _rows(segment: str) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        for index in range(120):
            aligned_return = (index - 60) / 1000
            rows.append(
                {
                    "pair": f"{segment}-{index % 6}",
                    "netR": 0.8 if aligned_return >= 0 else -0.9,
                    "aligned_return": aligned_return,
                    "aligned_slope20": aligned_return / 2,
                    "aligned_trend20_50": 0.01,
                    "aligned_trend50_200": 0.02,
                    "btc_aligned": 0.001,
                    "atr_pct": 0.006,
                }
            )
        return rows

    def test_search_finds_guard_that_is_positive_in_all_development_segments(self) -> None:
        results = discover_robust_factor_guards(
            {
                "derivationTrain": self._rows("train"),
                "derivationValidation": self._rows("validation"),
                "symbolHoldback": self._rows("holdback"),
            },
            max_results=3,
        )

        self.assertTrue(results)
        best = results[0]
        self.assertTrue(best["eligible"])
        self.assertTrue(
            "aligned_return_min" in best["factorGuards"]
            or "aligned_slope20_min" in best["factorGuards"]
        )
        for metrics in best["segmentMetrics"].values():
            self.assertGreater(metrics["expectancyR"], 0)
            self.assertGreater(metrics["profitFactor"], 1)

    def test_search_returns_empty_when_holdback_has_no_positive_subgroup(self) -> None:
        holdback = self._rows("holdback")
        for row in holdback:
            row["netR"] = -0.5

        results = discover_robust_factor_guards(
            {
                "derivationTrain": self._rows("train"),
                "derivationValidation": self._rows("validation"),
                "symbolHoldback": holdback,
            },
            max_results=3,
        )

        self.assertEqual(results, ())

    def test_search_can_attribute_edge_to_btc_regime_factor(self) -> None:
        rows_by_segment: dict[str, list[dict[str, object]]] = {}
        for segment in ("derivationTrain", "derivationValidation", "symbolHoldback"):
            rows = []
            for index in range(120):
                btc_trend = (index - 60) / 1000
                rows.append(
                    {
                        "pair": f"{segment}-{index % 8}",
                        "netR": 0.9 if btc_trend >= 0 else -0.8,
                        "aligned_return": 0.0,
                        "aligned_slope20": 0.0,
                        "aligned_trend20_50": 0.0,
                        "aligned_trend50_200": 0.0,
                        "btc_aligned": 0.0,
                        "btc_trend20_50": btc_trend,
                        "btc_trend50_200": btc_trend / 2,
                        "btc_slope20_12": btc_trend / 3,
                        "atr_pct": 0.006,
                    }
                )
            rows_by_segment[segment] = rows

        results = discover_robust_factor_guards(rows_by_segment, max_results=3)

        self.assertTrue(results)
        self.assertTrue(
            any(
                key.startswith("btc_trend") or key.startswith("btc_slope")
                for key in results[0]["factorGuards"]
            )
        )


if __name__ == "__main__":
    unittest.main()
