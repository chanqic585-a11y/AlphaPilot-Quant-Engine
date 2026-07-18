from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.data_foundation.okx_official_v1 import OkxOfficialV1Layout
from alphapilot.data_foundation.okx_official_v1_quality_monitor import (
    OkxOfficialV1QualityMonitor,
)
from alphapilot.data_foundation.okx_official_v1_schedule import (
    OkxPublicCollectionPolicy,
    SchedulerStateStore,
)
from alphapilot.evolution.registry.hashing import sha256_file


def _build_monitor(
    root: Path,
    *,
    ticker_next_due: str = "2026-07-19T00:05:00+00:00",
    ticker_failures: int = 0,
) -> OkxOfficialV1QualityMonitor:
    policy = OkxPublicCollectionPolicy.default(instruments=("BTC-USDT-SWAP",))
    store = SchedulerStateStore(root / "scheduler.json", policy=policy)
    state = store.load_or_initialize(now="2026-07-19T00:00:00+00:00")
    for task in policy.tasks:
        state["tasks"][task.name].update(
            {
                "nextDueAt": "2026-07-19T01:00:00+00:00",
                "lastStatus": "success",
                "lastCompletedAt": "2026-07-19T00:00:00+00:00",
            }
        )
    state["tasks"]["ticker_spread"].update(
        {
            "nextDueAt": ticker_next_due,
            "consecutiveFailures": ticker_failures,
            "lastStatus": "failed" if ticker_failures else "success",
        }
    )
    store.save(state)
    return OkxOfficialV1QualityMonitor(
        warehouse_root=root,
        policy=policy,
        state_store=store,
    )


class OkxOfficialV1QualityMonitorTests(unittest.TestCase):
    def test_quality_status_is_warning_for_single_overdue_task(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            monitor = _build_monitor(
                Path(directory),
                ticker_next_due="2026-07-18T23:55:00+00:00",
            )

            report = monitor.evaluate(now="2026-07-19T00:01:00+00:00")

            self.assertEqual(report.status, "warning")
            self.assertIn("task_overdue:ticker_spread", report.reasons)

    def test_quality_status_is_degraded_after_four_intervals(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            monitor = _build_monitor(
                Path(directory),
                ticker_next_due="2026-07-18T23:30:00+00:00",
            )

            report = monitor.evaluate(now="2026-07-19T00:01:00+00:00")

            self.assertEqual(report.status, "degraded")
            self.assertIn("task_severely_overdue:ticker_spread", report.reasons)

    def test_quality_status_is_blocked_for_hash_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            monitor = _build_monitor(root)
            layout = OkxOfficialV1Layout.from_warehouse(root)
            artifact = layout.forwardCollectionRoot / "v34c" / "test.json"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            artifact.write_text('{"status":"valid"}\n', encoding="utf-8")
            write_json_atomic(
                layout.manifestRoot / "v34c" / "artifact_index.json",
                {
                    "schemaVersion": "okx_official_v1_v34c_artifact_index_v1",
                    "appendOnly": True,
                    "entries": [
                        {
                            "taskName": "ticker_spread",
                            "observedAt": "2026-07-19T00:00:00+00:00",
                            "path": str(artifact.resolve()),
                            "sha256": "0" * 64,
                            "rowCount": 1,
                        }
                    ],
                },
            )

            report = monitor.evaluate(now="2026-07-19T00:01:00+00:00")

            self.assertEqual(report.status, "blocked")
            self.assertIn("artifact_hash_mismatch:ticker_spread", report.reasons)

    def test_quality_status_is_blocked_for_invalid_funding_causality(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            monitor = _build_monitor(root)
            layout = OkxOfficialV1Layout.from_warehouse(root)
            artifact = (
                layout.forwardCollectionRoot
                / "v34c"
                / "funding_increment"
                / "2026-07-19"
                / "invalid.parquet"
            )
            artifact.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                [
                    {
                        "instrumentId": "BTC-USDT-SWAP",
                        "fundingTime": 1000,
                        "realizedRateAvailableAt": "not-a-timestamp",
                        "retrievedAt": "2026-07-19T00:00:00+00:00",
                        "sourceHash": "1" * 64,
                        "sourceEndpoint": "/api/v5/public/funding-rate-history",
                        "observedAt": "2026-07-19T00:00:00+00:00",
                    }
                ]
            ).to_parquet(artifact, index=False)
            write_json_atomic(
                layout.manifestRoot / "v34c" / "artifact_index.json",
                {
                    "schemaVersion": "okx_official_v1_v34c_artifact_index_v1",
                    "appendOnly": True,
                    "entries": [
                        {
                            "taskName": "funding_increment",
                            "observedAt": "2026-07-19T00:00:00+00:00",
                            "path": str(artifact.resolve()),
                            "sha256": sha256_file(artifact),
                            "rowCount": 1,
                        }
                    ],
                },
            )

            report = monitor.evaluate(now="2026-07-19T00:01:00+00:00")

            self.assertEqual(report.status, "blocked")
            self.assertIn(
                "artifact_causal_schema_invalid:funding_increment",
                report.reasons,
            )

    def test_healthy_report_is_written_as_content_addressed_json_and_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            monitor = _build_monitor(root)

            report = monitor.evaluate(now="2026-07-19T00:01:00+00:00")
            artifacts = monitor.write_report(report)
            json_path = Path(artifacts["jsonPath"])
            markdown_path = Path(artifacts["markdownPath"])
            payload = json.loads(json_path.read_text(encoding="utf-8"))

            self.assertEqual(report.status, "healthy")
            self.assertIn(report.quality_hash, json_path.name)
            self.assertTrue(markdown_path.is_file())
            self.assertEqual(payload["qualityHash"], report.quality_hash)
            self.assertEqual(
                artifacts["jsonSha256"],
                hashlib.sha256(json_path.read_bytes()).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
