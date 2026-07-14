from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from alphapilot.data_foundation.official_partition_index import OfficialPartitionIndex
from alphapilot.evolution.registry.hashing import sha256_file


class OfficialPartitionIndexTests(unittest.TestCase):
    def _write_manifest(
        self,
        *,
        manifest_root: Path,
        canonical_root: Path,
        suffix: str,
        end_time: str,
        content: bytes,
        expected_hash: str | None = None,
        output_root: Path | None = None,
    ) -> Path:
        output = (output_root or canonical_root) / f"partition-{suffix}.parquet"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(content)
        digest = expected_hash or sha256_file(output)
        manifest_root.mkdir(parents=True, exist_ok=True)
        manifest = manifest_root / f"BTC-USDT-SWAP-5m-{suffix}.json"
        manifest.write_text(
            json.dumps(
                {
                    "schemaVersion": "okx_official_partition_manifest_v1",
                    "instrumentId": "BTC-USDT-SWAP",
                    "timeframe": "5m",
                    "sourceEndpoint": "https://official.example/history-candles",
                    "rows": 100,
                    "startTime": "2020-01-01T00:00:00+00:00",
                    "endTime": end_time,
                    "outputPath": str(output),
                    "outputSha256": digest,
                }
            ),
            encoding="utf-8",
        )
        return manifest

    def test_returns_latest_hash_verified_partition(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "canonical"
            manifests = root / "manifests"
            self._write_manifest(
                manifest_root=manifests,
                canonical_root=canonical,
                suffix="older",
                end_time="2026-07-13T00:00:00+00:00",
                content=b"older",
            )
            self._write_manifest(
                manifest_root=manifests,
                canonical_root=canonical,
                suffix="latest",
                end_time="2026-07-14T00:00:00+00:00",
                content=b"latest",
            )

            index = OfficialPartitionIndex.from_manifests(manifests, canonical)
            result = index.latest_valid(
                "BTC-USDT-SWAP",
                "5m",
                "https://official.example/history-candles",
            )

            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(result.endTime, "2026-07-14T00:00:00+00:00")
            self.assertEqual(result.manifestCount, 2)

    def test_skips_wrong_hash_and_output_outside_canonical_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "canonical"
            manifests = root / "manifests"
            self._write_manifest(
                manifest_root=manifests,
                canonical_root=canonical,
                suffix="wrong-hash",
                end_time="2026-07-14T00:00:00+00:00",
                content=b"wrong",
                expected_hash="not-the-file-hash",
            )
            self._write_manifest(
                manifest_root=manifests,
                canonical_root=canonical,
                suffix="outside",
                end_time="2026-07-13T00:00:00+00:00",
                content=b"outside",
                output_root=root / "outside",
            )

            index = OfficialPartitionIndex.from_manifests(manifests, canonical)

            self.assertIsNone(
                index.latest_valid(
                    "BTC-USDT-SWAP",
                    "5m",
                    "https://official.example/history-candles",
                )
            )

    def test_different_endpoint_is_not_compatible(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            canonical = root / "canonical"
            manifests = root / "manifests"
            self._write_manifest(
                manifest_root=manifests,
                canonical_root=canonical,
                suffix="endpoint",
                end_time="2026-07-14T00:00:00+00:00",
                content=b"endpoint",
            )
            index = OfficialPartitionIndex.from_manifests(manifests, canonical)

            self.assertIsNone(
                index.latest_valid(
                    "BTC-USDT-SWAP",
                    "5m",
                    "https://different.example/history-candles",
                )
            )


if __name__ == "__main__":
    unittest.main()
