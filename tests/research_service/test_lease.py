from __future__ import annotations

import json
import os
import socket
import tempfile
import unittest
from pathlib import Path

from alphapilot.research_service.lease import (
    ResearchServiceLease,
    ResearchServiceLeaseUnavailable,
)


class ResearchServiceLeaseTests(unittest.TestCase):
    def test_live_same_host_process_lease_is_not_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service.lease.json"
            path.write_text(
                json.dumps(
                    {
                        "owner": f"{socket.gethostname()}:{os.getpid()}",
                        "acquiredAt": "2026-07-18T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            lease = ResearchServiceLease(
                path,
                owner="new-owner",
                stale_after_seconds=1,
            )

            with self.assertRaises(ResearchServiceLeaseUnavailable):
                lease.acquire(acquired_at="2026-07-19T00:00:00+00:00")

    def test_expired_dead_process_lease_is_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "service.lease.json"
            path.write_text(
                json.dumps(
                    {
                        "owner": f"{socket.gethostname()}:999999999",
                        "acquiredAt": "2026-07-18T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            lease = ResearchServiceLease(
                path,
                owner="new-owner",
                stale_after_seconds=60,
            )

            lease.acquire(acquired_at="2026-07-19T00:00:00+00:00")
            payload = json.loads(path.read_text(encoding="utf-8"))

            self.assertEqual(payload["owner"], "new-owner")
            lease.release()
            self.assertFalse(path.exists())


if __name__ == "__main__":
    unittest.main()
