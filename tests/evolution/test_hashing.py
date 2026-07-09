from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.registry.hashing import canonical_json, sha256_file, stable_hash


class HashingTests(unittest.TestCase):
    def test_canonical_json_ignores_mapping_insertion_order(self) -> None:
        left = {"b": 2, "a": 1, "nested": {"y": 2, "x": 1}}
        right = {"nested": {"x": 1, "y": 2}, "a": 1, "b": 2}

        self.assertEqual(canonical_json(left), canonical_json(right))
        self.assertEqual(stable_hash(left), stable_hash(right))

    def test_list_order_changes_hash(self) -> None:
        self.assertNotEqual(stable_hash([1, 2]), stable_hash([2, 1]))

    def test_non_finite_numbers_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    canonical_json({"value": value})

    def test_prefix_is_included_in_readable_id(self) -> None:
        value = stable_hash({"value": 1}, prefix="factor")
        self.assertTrue(value.startswith("factor_"))
        self.assertEqual(len(value), len("factor_") + 64)

    def test_file_hash_changes_with_content(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample.txt"
            path.write_text("first", encoding="utf-8")
            first = sha256_file(path)
            path.write_text("second", encoding="utf-8")
            second = sha256_file(path)

        self.assertNotEqual(first, second)


if __name__ == "__main__":
    unittest.main()
