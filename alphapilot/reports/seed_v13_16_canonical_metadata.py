"""Seed canonical metadata sidecars from a source-validated V13.16 report."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.canonical import (
    frame_quality_from_dict,
    write_canonical_metadata,
)
from alphapilot.data_foundation.types import RawDataAsset
from alphapilot.evolution.registry.hashing import sha256_file


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed V13.16 canonical quality sidecars.")
    parser.add_argument("--foundation-report", default="reports/v13_16_data_foundation_report.json")
    parser.add_argument("--raw-catalog", default="data/market/catalog/raw_catalog.json")
    parser.add_argument("--output-json", default="reports/v13_16_canonical_metadata_seed_report.json")
    return parser.parse_args()


def seed_metadata(
    *,
    foundation_report: Path | str,
    raw_catalog: Path | str,
) -> dict[str, Any]:
    report = json.loads(Path(foundation_report).read_text(encoding="utf-8"))
    catalog = json.loads(Path(raw_catalog).read_text(encoding="utf-8"))
    assets_by_source = {
        str(item.get("sourcePath")): item
        for item in catalog.get("assets", [])
        if isinstance(item, dict) and item.get("sourcePath")
    }
    seeded: list[dict[str, str]] = []
    errors: list[str] = []
    for item in report.get("canonicalAssets", []):
        if not isinstance(item, dict) or item.get("status") not in {"created", "existing"}:
            continue
        source_path = str(item.get("sourcePath") or "")
        output_path = Path(str(item.get("outputPath") or ""))
        quality_value = item.get("quality")
        raw_value = assets_by_source.get(source_path)
        if not output_path.is_file() or not isinstance(quality_value, dict) or not isinstance(raw_value, dict):
            errors.append(f"incomplete_evidence:{source_path}")
            continue
        asset = RawDataAsset(**raw_value)
        if not asset.sha256:
            errors.append(f"source_hash_missing:{source_path}")
            continue
        actual_hash = sha256_file(output_path)
        if actual_hash != item.get("contentSha256"):
            errors.append(f"canonical_hash_mismatch:{output_path}")
            continue
        metadata_path = write_canonical_metadata(
            output_path=output_path,
            asset=asset,
            content_sha256=actual_hash,
            quality=frame_quality_from_dict(quality_value),
        )
        seeded.append(
            {
                "sourcePath": source_path,
                "canonicalPath": str(output_path),
                "metadataPath": str(metadata_path),
            }
        )
    return {
        "reportId": "v13_16_canonical_metadata_seed_report",
        "version": "V13.16.0",
        "status": "completed" if seeded and not errors else "completed_with_errors" if seeded else "blocked",
        "generatedAt": datetime.now(UTC).isoformat(),
        "requestedCount": len(report.get("canonicalAssets", [])),
        "seededCount": len(seeded),
        "errorCount": len(errors),
        "seeded": seeded,
        "errors": errors,
        "safetyBoundary": {
            "localDataOnly": True,
            "rawFilesModified": False,
            "apiKeyUsed": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "orderCreated": False,
        },
    }


def main() -> None:
    args = parse_args()
    report = seed_metadata(
        foundation_report=args.foundation_report,
        raw_catalog=args.raw_catalog,
    )
    output = Path(args.output_json)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in (
        "reportId",
        "version",
        "status",
        "requestedCount",
        "seededCount",
        "errorCount",
    )}, ensure_ascii=False, indent=2))
    print(f"Wrote {output}")


if __name__ == "__main__":
    main()
