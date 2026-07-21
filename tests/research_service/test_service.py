from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.research_service.policy import ResearchServicePolicy
from alphapilot.research_service.service import ResearchService
from alphapilot.research_service.state import ResearchServiceStateStore


class RecordingExecutor:
    def __init__(self, *, status: str = "ready_for_prefilter") -> None:
        self.status = status
        self.calls: list[dict[str, object]] = []

    def execute(self, job: dict[str, object]) -> dict[str, object]:
        self.calls.append(job)
        return {
            "status": self.status,
            "candidateCount": len(job.get("candidateIds") or []),
            "formalRunCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 1 if self.status == "immutable_release_ready" else 0,
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
        }


class PauseThenReadyExecutor(RecordingExecutor):
    def execute(self, job: dict[str, object]) -> dict[str, object]:
        self.calls.append(job)
        status = "paused" if len(self.calls) == 1 else "ready_for_prefilter"
        return {
            "status": status,
            "candidateCount": len(job.get("candidateIds") or []),
            "formalRunCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
        }


def _build_service(
    root: Path,
    *,
    executor: RecordingExecutor,
    pause_file: Path | None = None,
    owner: str = "test-service",
) -> ResearchService:
    policy = ResearchServicePolicy.default()
    state_store = ResearchServiceStateStore(root / "state.json", policy=policy)
    return ResearchService(
        policy=policy,
        state_store=state_store,
        executor=executor,
        lease_path=root / "service.lock",
        receipt_path=root / "receipts.jsonl",
        owner=owner,
        pause_file=pause_file,
    )


class ResearchServiceTests(unittest.TestCase):
    def test_pause_file_prevents_campaign_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pause_file = root / "PAUSE"
            pause_file.write_text("paused\n", encoding="utf-8")
            executor = RecordingExecutor()
            service = _build_service(
                root,
                executor=executor,
                pause_file=pause_file,
            )
            service.enqueue(
                campaign_id="campaign-a",
                family_ids=("crypto_tsmom_turtle_v1",),
                candidate_ids=("candidate-a",),
                queued_at="2026-07-19T00:00:00+00:00",
            )

            result = service.run_cycle(now="2026-07-19T00:01:00+00:00")

            self.assertEqual(result["status"], "paused")
            self.assertEqual(executor.calls, [])

    def test_service_executes_one_campaign_and_writes_hash_chained_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = RecordingExecutor()
            service = _build_service(root, executor=executor)
            service.enqueue(
                campaign_id="campaign-a",
                family_ids=("crypto_tsmom_turtle_v1",),
                candidate_ids=("candidate-a", "candidate-b"),
                queued_at="2026-07-19T00:00:00+00:00",
            )

            first = service.run_cycle(now="2026-07-19T00:01:00+00:00")
            second = service.run_cycle(now="2026-07-19T00:02:00+00:00")
            receipts = [
                json.loads(line)
                for line in (root / "receipts.jsonl").read_text(encoding="utf-8").splitlines()
            ]

            self.assertEqual(first["status"], "ready_for_prefilter")
            self.assertEqual(first["candidateCount"], 2)
            self.assertEqual(first["demoReleaseCount"], 0)
            self.assertFalse(first["demoArm"])
            self.assertEqual(first["orderCount"], 0)
            self.assertEqual(second["status"], "idle")
            self.assertEqual(len(executor.calls), 1)
            self.assertEqual(receipts[1]["previousReceiptHash"], receipts[0]["receiptHash"])

    def test_executor_pause_keeps_job_queued_for_a_real_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = PauseThenReadyExecutor()
            service = _build_service(root, executor=executor)
            service.enqueue(
                campaign_id="campaign-resume",
                family_ids=("crypto_tsmom_turtle_v1",),
                candidate_ids=("candidate-a",),
                queued_at="2026-07-19T00:00:00+00:00",
            )

            paused = service.run_cycle(now="2026-07-19T00:01:00+00:00")
            paused_state = service.state_store.load_or_initialize(
                now="2026-07-19T00:01:00+00:00"
            )
            resumed = service.run_cycle(now="2026-07-19T00:02:00+00:00")

            self.assertEqual(paused["status"], "paused")
            self.assertEqual(paused["campaignId"], "campaign-resume")
            self.assertEqual(paused_state["status"], "paused")
            self.assertEqual(paused_state["jobs"][0]["status"], "queued")
            self.assertEqual(resumed["status"], "ready_for_prefilter")
            self.assertEqual(len(executor.calls), 2)

    def test_service_stops_at_immutable_release_ready_without_approval_or_arm(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executor = RecordingExecutor(status="immutable_release_ready")
            service = _build_service(root, executor=executor)
            service.enqueue(
                campaign_id="campaign-a",
                family_ids=("crypto_tsmom_turtle_v1",),
                candidate_ids=("candidate-a",),
                queued_at="2026-07-19T00:00:00+00:00",
            )

            result = service.run_cycle(now="2026-07-19T00:01:00+00:00")
            state = service.state_store.load_or_initialize(
                now="2026-07-19T00:01:00+00:00"
            )

            self.assertEqual(result["status"], "waiting_exact_release_approval")
            self.assertEqual(result["releaseCount"], 1)
            self.assertEqual(result["approvalCount"], 0)
            self.assertEqual(result["demoReleaseCount"], 0)
            self.assertFalse(result["demoArm"])
            self.assertEqual(result["orderCount"], 0)
            self.assertEqual(state["status"], "waiting_exact_release_approval")

    def test_budget_rejects_campaign_with_more_than_six_families(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = _build_service(root, executor=RecordingExecutor())

            with self.assertRaisesRegex(ValueError, "family_budget_exceeded"):
                service.enqueue(
                    campaign_id="campaign-a",
                    family_ids=tuple(f"family-{index}" for index in range(7)),
                    candidate_ids=("candidate-a",),
                    queued_at="2026-07-19T00:00:00+00:00",
                )


if __name__ == "__main__":
    unittest.main()
