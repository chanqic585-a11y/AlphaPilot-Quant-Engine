from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.scripts.run_v35_standard_replication_service import main


class RunV35StandardReplicationServiceTests(unittest.TestCase):
    def test_once_enqueues_default_campaign_and_writes_health(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)

            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    str(state_root),
                    "--enqueue-default",
                    "--once",
                    "--now",
                    "2026-07-19T00:00:00+00:00",
                ]
            )
            health = json.loads(
                (state_root / "health.json").read_text(encoding="utf-8")
            )

            self.assertEqual(exit_code, 0)
            self.assertEqual(health["serviceStatus"], "ready_for_prefilter")
            self.assertEqual(health["campaignCount"], 1)
            self.assertEqual(health["formalRunCount"], 0)
            self.assertEqual(health["demoReleaseCount"], 0)
            self.assertFalse(health["demoArm"])
            self.assertEqual(health["orderCount"], 0)

    def test_bounded_loop_exits_after_requested_cycle_count(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        with tempfile.TemporaryDirectory() as directory:
            state_root = Path(directory)

            exit_code = main(
                [
                    "--repo-root",
                    str(repo_root),
                    "--state-root",
                    str(state_root),
                    "--enqueue-default",
                    "--max-cycles",
                    "1",
                    "--interval-seconds",
                    "0",
                    "--now",
                    "2026-07-19T00:00:00+00:00",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((state_root / "health.json").is_file())


if __name__ == "__main__":
    unittest.main()
