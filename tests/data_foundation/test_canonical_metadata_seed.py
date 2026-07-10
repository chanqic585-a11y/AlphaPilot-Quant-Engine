from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from alphapilot.data_foundation.canonical import canonical_metadata_path
from alphapilot.data_foundation.types import FrameQuality, RawDataAsset
from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.reports.seed_v13_16_canonical_metadata import seed_metadata


class CanonicalMetadataSeedTests(unittest.TestCase):
    def test_seed_requires_matching_source_and_canonical_hashes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.csv"
            source.write_text("source", encoding="utf-8")
            canonical = root / "canonical.parquet"
            pd.DataFrame({"timestamp_ms": [0]}).to_parquet(canonical, index=False)
            asset = RawDataAsset(
                sourcePath=str(source),
                relativePath="source.csv",
                sourceGroup="test",
                fileFormat="csv",
                dataKind="ohlcv",
                marketType="swap",
                instrumentId="BTC-USDT-SWAP",
                symbol="BTC",
                timeframe="15m",
                partition="all",
                duplicateFamily=None,
                sizeBytes=source.stat().st_size,
                modifiedAtNs=source.stat().st_mtime_ns,
                sha256=sha256_file(source),
            )
            quality = FrameQuality(
                rows=1,
                startTime="1970-01-01T00:00:00+00:00",
                endTime="1970-01-01T00:00:00+00:00",
                duplicateTimestampCount=0,
                backwardTimestampCount=0,
                gapEventCount=0,
                missingBarCount=0,
                invalidOhlcCount=0,
                negativeVolumeCount=0,
                unconfirmedDroppedCount=0,
                sourceRows=1,
            )
            catalog_path = root / "catalog.json"
            report_path = root / "report.json"
            catalog_path.write_text(json.dumps({"assets": [asset.to_dict()]}), encoding="utf-8")
            report_path.write_text(
                json.dumps(
                    {
                        "canonicalAssets": [
                            {
                                "sourcePath": str(source),
                                "outputPath": str(canonical),
                                "status": "existing",
                                "contentSha256": sha256_file(canonical),
                                "quality": quality.to_dict(),
                            }
                        ]
                    }
                ),
                encoding="utf-8",
            )

            report = seed_metadata(
                foundation_report=report_path,
                raw_catalog=catalog_path,
            )

            metadata = json.loads(canonical_metadata_path(canonical).read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "completed")
        self.assertEqual(report["seededCount"], 1)
        self.assertEqual(metadata["sourceSha256"], asset.sha256)
        self.assertEqual(metadata["quality"]["rows"], 1)


if __name__ == "__main__":
    unittest.main()
