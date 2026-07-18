from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.data_foundation.okx_official_v1_incremental import (
    TaskCollectionResult,
)
from alphapilot.data_foundation.okx_official_v1_quality_monitor import (
    OkxOfficialV1QualityMonitor,
)
from alphapilot.data_foundation.okx_official_v1_schedule import (
    OkxPublicCollectionPolicy,
    SchedulerLease,
    SchedulerStateStore,
)
from alphapilot.data_foundation.okx_official_v1_service import (
    OkxOfficialV1PublicDataService,
)


class FakeCollector:
    def __init__(self, *, fail_task: str | None = None) -> None:
        self.fail_task = fail_task
        self.calls: list[tuple[str, str]] = []

    def collect_task(self, task_name: str, observed_at: str) -> TaskCollectionResult:
        self.calls.append((task_name, observed_at))
        if task_name == self.fail_task:
            raise RuntimeError("x" * 2_000)
        return TaskCollectionResult(
            task_name=task_name,
            status="collected",
            observed_at=observed_at,
            artifact_path=f"C:/warehouse/{task_name}.json",
            artifact_sha256="1" * 64,
            row_count=1,
            source_timestamp=observed_at,
            details={"artifactReused": False},
        )


def _build_service(
    root: Path,
    *,
    collector: FakeCollector | None = None,
    pause_file: Path | None = None,
) -> tuple[OkxOfficialV1PublicDataService, SchedulerStateStore, FakeCollector]:
    policy = OkxPublicCollectionPolicy.default(instruments=("BTC-USDT-SWAP",))
    store = SchedulerStateStore(root / "scheduler.json", policy=policy)
    selected_collector = collector or FakeCollector()
    monitor = OkxOfficialV1QualityMonitor(
        warehouse_root=root,
        policy=policy,
        state_store=store,
    )
    return (
        OkxOfficialV1PublicDataService(
            policy=policy,
            state_store=store,
            collector=selected_collector,
            quality_monitor=monitor,
            lease_path=root / "scheduler.lock",
            cycle_ledger_path=root / "cycles.jsonl",
            owner="test-service",
            pause_file=pause_file,
        ),
        store,
        selected_collector,
    )


class OkxOfficialV1PublicDataServiceTests(unittest.TestCase):
    def test_second_cycle_runs_only_newly_due_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            service, _, _ = _build_service(Path(directory))

            first = service.run_due_cycle(now="2026-07-19T00:00:00+00:00")
            second = service.run_due_cycle(now="2026-07-19T00:06:00+00:00")

            self.assertIn("instrument_metadata", first["executedTasks"])
            self.assertIn("ticker_spread", first["executedTasks"])
            self.assertNotIn("instrument_metadata", second["executedTasks"])
            self.assertIn("ticker_spread", second["executedTasks"])
            self.assertNotIn("quality", second["executedTasks"])
            self.assertIsNone(second["qualityStatus"])
            self.assertEqual(second["qualityArtifacts"], {})
            self.assertEqual(second["candidateCount"], 0)
            self.assertEqual(second["formalRunCount"], 0)
            self.assertEqual(second["demoReleaseCount"], 0)
            self.assertEqual(second["orderCount"], 0)

    def test_failed_stream_is_bounded_and_does_not_stop_later_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            collector = FakeCollector(fail_task="current_funding")
            service, store, _ = _build_service(root, collector=collector)

            result = service.run_due_cycle(now="2026-07-19T00:00:00+00:00")
            state = store.load_or_initialize(now="2026-07-19T00:00:00+00:00")

            self.assertIn("current_funding", result["failedTasks"])
            self.assertIn("open_interest", result["executedTasks"])
            self.assertLessEqual(len(result["errors"]["current_funding"]), 512)
            self.assertEqual(
                state["tasks"]["current_funding"]["nextDueAt"],
                "2026-07-19T00:01:00+00:00",
            )
            self.assertEqual(
                state["tasks"]["open_interest"]["lastStatus"],
                "success",
            )

    def test_pause_file_skips_cycle_without_touching_collector(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pause_file = root / "PAUSE"
            pause_file.write_text("pause\n", encoding="utf-8")
            service, _, collector = _build_service(root, pause_file=pause_file)

            result = service.run_due_cycle(now="2026-07-19T00:00:00+00:00")

            self.assertEqual(result["status"], "paused")
            self.assertEqual(collector.calls, [])

    def test_active_lease_returns_owner_audit_without_running(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service, _, collector = _build_service(root)
            active = SchedulerLease(root / "scheduler.lock", owner="other-service")
            active.acquire(acquired_at="2026-07-19T00:00:00+00:00")

            result = service.run_due_cycle(now="2026-07-19T00:01:00+00:00")

            self.assertEqual(result["status"], "lease_unavailable")
            self.assertEqual(result["ownerAudit"]["owner"], "other-service")
            self.assertEqual(collector.calls, [])
            active.release()

    def test_cycle_receipts_are_hash_chained_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service, _, _ = _build_service(root)

            first = service.run_due_cycle(now="2026-07-19T00:00:00+00:00")
            second = service.run_due_cycle(now="2026-07-19T00:06:00+00:00")
            records = [
                json.loads(line)
                for line in (root / "cycles.jsonl").read_text(encoding="utf-8").splitlines()
            ]

            self.assertEqual(len(records), 2)
            self.assertEqual(records[0]["cycleHash"], first["cycleHash"])
            self.assertEqual(records[1]["previousCycleHash"], records[0]["cycleHash"])
            self.assertEqual(records[1]["cycleHash"], second["cycleHash"])

    def test_operator_stop_is_persisted_with_zero_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service, _, _ = _build_service(root)

            receipt = service.record_operator_stop(
                now="2026-07-19T00:00:00+00:00"
            )
            persisted = json.loads(
                (root / "cycles.jsonl").read_text(encoding="utf-8").splitlines()[-1]
            )

            self.assertEqual(receipt["status"], "stopped_by_operator")
            self.assertEqual(receipt["candidateCount"], 0)
            self.assertEqual(receipt["orderCount"], 0)
            self.assertEqual(persisted["cycleHash"], receipt["cycleHash"])


if __name__ == "__main__":
    unittest.main()
