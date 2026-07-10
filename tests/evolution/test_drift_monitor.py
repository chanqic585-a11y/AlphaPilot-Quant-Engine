from __future__ import annotations

import unittest

from alphapilot.evolution.promotion.drift_monitor import (
    DemoDriftObservation,
    evaluate_demo_drift,
)


class DriftMonitorTests(unittest.TestCase):
    def test_healthy_observation_continues(self) -> None:
        result = evaluate_demo_drift(
            DemoDriftObservation(
                dataFresh=True,
                metadataFresh=True,
                clockSynchronized=True,
                ledgerMatchesExchange=True,
                checksumsMatch=True,
                rollingProfitFactor=1.18,
                consecutiveLosses=2,
                observedSlippageBps=6,
                assumedSlippageBps=5,
                calibrationError=0.06,
                regimePerformanceDrop=0.15,
            )
        )
        self.assertEqual(result.severity, "none")
        self.assertFalse(result.pauseRequired)

    def test_integrity_mismatch_is_critical(self) -> None:
        result = evaluate_demo_drift(
            DemoDriftObservation(
                dataFresh=True,
                metadataFresh=True,
                clockSynchronized=True,
                ledgerMatchesExchange=False,
                checksumsMatch=True,
                rollingProfitFactor=1.3,
                consecutiveLosses=0,
                observedSlippageBps=4,
                assumedSlippageBps=5,
                calibrationError=0.02,
                regimePerformanceDrop=0.0,
            )
        )
        self.assertEqual(result.severity, "critical")
        self.assertTrue(result.pauseRequired)
        self.assertIn("ledger_exchange_mismatch", result.reasonCodes)


if __name__ == "__main__":
    unittest.main()
