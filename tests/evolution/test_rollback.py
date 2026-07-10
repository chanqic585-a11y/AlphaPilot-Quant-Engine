from __future__ import annotations

import unittest

from alphapilot.evolution.promotion.drift_monitor import DriftEvaluation
from alphapilot.evolution.promotion.rollback import decide_demo_rollback


class RollbackTests(unittest.TestCase):
    def test_critical_drift_pauses_without_automatic_live_action(self) -> None:
        decision = decide_demo_rollback(
            DriftEvaluation(
                severity="critical",
                pauseRequired=True,
                reasonCodes=("ledger_exchange_mismatch",),
                checks=(),
            ),
            previousStableReleaseId="demo_previous",
            previousReleaseStillValid=True,
        )

        self.assertEqual(decision.action, "rollback_demo_release")
        self.assertEqual(decision.rollbackTargetId, "demo_previous")
        self.assertTrue(decision.stopNewEntries)
        self.assertFalse(decision.liveActionAllowed)

    def test_missing_valid_target_stays_paused(self) -> None:
        decision = decide_demo_rollback(
            DriftEvaluation(
                severity="critical",
                pauseRequired=True,
                reasonCodes=("checksum_mismatch",),
                checks=(),
            ),
            previousStableReleaseId=None,
            previousReleaseStillValid=False,
        )
        self.assertEqual(decision.action, "pause_demo_release")
        self.assertIsNone(decision.rollbackTargetId)


if __name__ == "__main__":
    unittest.main()
