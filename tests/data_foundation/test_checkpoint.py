from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from alphapilot.data_foundation.checkpoint import load_json, write_json_atomic


class CheckpointTests(unittest.TestCase):
    def test_atomic_replace_retries_windows_sharing_violation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "checkpoint.json"
            write_json_atomic(path, {"version": 1})
            real_replace = os.replace
            attempts = 0

            def flaky_replace(source: Path, destination: Path) -> None:
                nonlocal attempts
                attempts += 1
                if attempts < 3:
                    raise PermissionError("simulated Windows sharing violation")
                real_replace(source, destination)

            with (
                patch("alphapilot.data_foundation.checkpoint.os.replace", side_effect=flaky_replace),
                patch("alphapilot.data_foundation.checkpoint.time.sleep"),
            ):
                write_json_atomic(path, {"version": 2})

            loaded = load_json(path)

        self.assertEqual(attempts, 3)
        self.assertEqual(loaded, {"version": 2})


if __name__ == "__main__":
    unittest.main()
