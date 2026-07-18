from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.data_foundation.okx_official_v1_schedule import (
    OkxPublicCollectionPolicy,
    SchedulerLease,
    SchedulerLeaseUnavailable,
    SchedulerStatePolicyMismatch,
    SchedulerStateStore,
    select_due_tasks,
)


class OkxOfficialV1ScheduleTests(unittest.TestCase):
    def test_due_selection_orders_oldest_due_task_first(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            policy = OkxPublicCollectionPolicy.default()
            store = SchedulerStateStore(Path(directory) / "scheduler.json", policy=policy)
            state = store.load_or_initialize(now="2026-07-19T00:00:00+00:00")

        due = select_due_tasks(
            policy,
            state,
            now="2026-07-19T00:00:00+00:00",
        )

        self.assertEqual(due[0], "instrument_metadata")
        self.assertIn("ticker_spread", due)
        self.assertEqual(due[-1], "quality")

    def test_due_selection_uses_due_time_then_policy_order(self) -> None:
        policy = OkxPublicCollectionPolicy.default()
        state = {
            "policyHash": policy.policy_hash,
            "tasks": {
                task.name: {
                    "nextDueAt": (
                        "2026-07-18T23:00:00+00:00"
                        if task.name == "open_interest"
                        else "2026-07-19T00:00:00+00:00"
                    )
                }
                for task in policy.tasks
            },
        }

        due = select_due_tasks(
            policy,
            state,
            now="2026-07-19T00:00:00+00:00",
        )

        self.assertEqual(due[0], "open_interest")
        self.assertEqual(due[1], "instrument_metadata")

    def test_policy_hash_changes_when_cadence_changes(self) -> None:
        original = OkxPublicCollectionPolicy.default()
        changed = original.with_interval("ticker_spread", seconds=600)

        self.assertNotEqual(original.policy_hash, changed.policy_hash)
        self.assertEqual(
            next(task.interval_seconds for task in changed.tasks if task.name == "ticker_spread"),
            600,
        )

    def test_state_store_rejects_a_different_policy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scheduler.json"
            original = OkxPublicCollectionPolicy.default()
            SchedulerStateStore(path, policy=original).load_or_initialize(
                now="2026-07-19T00:00:00+00:00"
            )
            changed = original.with_interval("ticker_spread", seconds=600)

            with self.assertRaises(SchedulerStatePolicyMismatch):
                SchedulerStateStore(path, policy=changed).load_or_initialize(
                    now="2026-07-19T00:10:00+00:00"
                )

    def test_lease_never_steals_an_existing_owner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "scheduler.lock"
            first = SchedulerLease(path, owner="first-owner")
            first.acquire(acquired_at="2026-07-19T00:00:00+00:00")

            second = SchedulerLease(path, owner="second-owner")
            with self.assertRaises(SchedulerLeaseUnavailable) as raised:
                second.acquire(acquired_at="2026-07-19T01:00:00+00:00")

            self.assertEqual(raised.exception.owner_audit["owner"], "first-owner")
            self.assertTrue(path.exists())
            first.release()
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
