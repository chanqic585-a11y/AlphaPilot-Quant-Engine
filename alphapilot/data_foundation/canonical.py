"""Write verified canonical OHLCV assets with atomic replacement."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .checkpoint import load_json, write_json_atomic
from .quality import inspect_quality
from .readers import read_ohlcv
from .types import CanonicalAsset, FrameQuality, RawDataAsset


CANONICAL_SCHEMA_VERSION = "canonical_ohlcv_v1"
CANONICAL_METADATA_SCHEMA_VERSION = "canonical_ohlcv_metadata_v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def canonical_metadata_path(output_path: Path | str) -> Path:
    path = Path(output_path)
    return path.with_name(f"{path.name}.metadata.json")


def frame_quality_from_dict(value: dict[str, Any]) -> FrameQuality:
    return FrameQuality(
        rows=int(value["rows"]),
        startTime=value.get("startTime"),
        endTime=value.get("endTime"),
        duplicateTimestampCount=int(value["duplicateTimestampCount"]),
        backwardTimestampCount=int(value["backwardTimestampCount"]),
        gapEventCount=int(value["gapEventCount"]),
        missingBarCount=int(value["missingBarCount"]),
        invalidOhlcCount=int(value["invalidOhlcCount"]),
        negativeVolumeCount=int(value["negativeVolumeCount"]),
        unconfirmedDroppedCount=int(value["unconfirmedDroppedCount"]),
        sourceRows=int(value["sourceRows"]),
        errors=tuple(str(item) for item in value.get("errors", [])),
        warnings=tuple(str(item) for item in value.get("warnings", [])),
    )


def write_canonical_metadata(
    *,
    output_path: Path | str,
    asset: RawDataAsset,
    content_sha256: str,
    quality: FrameQuality,
) -> Path:
    metadata_path = canonical_metadata_path(output_path)
    write_json_atomic(
        metadata_path,
        {
            "schemaVersion": CANONICAL_METADATA_SCHEMA_VERSION,
            "canonicalSchemaVersion": CANONICAL_SCHEMA_VERSION,
            "sourcePath": asset.sourcePath,
            "sourceRelativePath": asset.relativePath,
            "sourceSha256": asset.sha256,
            "sourceSizeBytes": asset.sizeBytes,
            "sourceModifiedAtNs": asset.modifiedAtNs,
            "canonicalPath": str(Path(output_path)),
            "canonicalSha256": content_sha256,
            "quality": quality.to_dict(),
            "createdAt": _utc_now(),
        },
    )
    return metadata_path


def _load_matching_metadata(
    *,
    output_path: Path,
    asset: RawDataAsset,
    content_sha256: str,
) -> FrameQuality | None:
    metadata = load_json(canonical_metadata_path(output_path))
    if (
        metadata.get("schemaVersion") != CANONICAL_METADATA_SCHEMA_VERSION
        or metadata.get("canonicalSchemaVersion") != CANONICAL_SCHEMA_VERSION
        or metadata.get("sourceSha256") != asset.sha256
        or metadata.get("canonicalSha256") != content_sha256
        or not isinstance(metadata.get("quality"), dict)
    ):
        return None
    return frame_quality_from_dict(metadata["quality"])


def _output_path(asset: RawDataAsset, output_root: Path, exchange: str) -> Path:
    identity = stable_hash(
        {
            "schemaVersion": CANONICAL_SCHEMA_VERSION,
            "sourcePath": asset.relativePath,
            "sourceSha256": asset.sha256,
            "sizeBytes": asset.sizeBytes,
        }
    )[:16]
    partition = (asset.partition or "data").lower()
    return (
        output_root
        / exchange
        / asset.marketType
        / asset.dataKind
        / str(asset.instrumentId or "unknown")
        / str(asset.timeframe or "unknown")
        / f"part-{partition}-{identity}.parquet"
    )


def canonicalize_asset(
    asset: RawDataAsset,
    *,
    output_root: Path | str,
    exchange: str = "unknown",
    overwrite: bool = False,
) -> CanonicalAsset:
    if not asset.selected:
        return CanonicalAsset(
            sourcePath=asset.sourcePath,
            outputPath=None,
            status="excluded",
            marketType=asset.marketType,
            instrumentId=asset.instrumentId,
            timeframe=asset.timeframe,
            contentSha256=None,
            quality=None,
            error=asset.exclusionReason,
        )
    if asset.dataKind != "ohlcv" or not asset.timeframe:
        return CanonicalAsset(
            sourcePath=asset.sourcePath,
            outputPath=None,
            status="unsupported",
            marketType=asset.marketType,
            instrumentId=asset.instrumentId,
            timeframe=asset.timeframe,
            contentSha256=None,
            quality=None,
            error=f"unsupported_data_kind:{asset.dataKind}",
        )
    if asset.sha256 is None:
        asset.sha256 = sha256_file(Path(asset.sourcePath))
    output_path = _output_path(asset, Path(output_root), exchange)
    if output_path.exists() and not overwrite:
        try:
            content_hash = sha256_file(output_path)
            cached_quality = _load_matching_metadata(
                output_path=output_path,
                asset=asset,
                content_sha256=content_hash,
            )
            if cached_quality is not None:
                return CanonicalAsset(
                    sourcePath=asset.sourcePath,
                    outputPath=str(output_path),
                    status="existing",
                    marketType=asset.marketType,
                    instrumentId=asset.instrumentId,
                    timeframe=asset.timeframe,
                    contentSha256=content_hash,
                    quality=cached_quality,
                )
            source_result = read_ohlcv(asset.sourcePath)
            quality = inspect_quality(source_result, asset.timeframe)
            if quality.errors:
                return CanonicalAsset(
                    sourcePath=asset.sourcePath,
                    outputPath=None,
                    status="failed_quality",
                    marketType=asset.marketType,
                    instrumentId=asset.instrumentId,
                    timeframe=asset.timeframe,
                    contentSha256=None,
                    quality=quality,
                    error=";".join(quality.errors),
                )
            comparison_columns = [
                "timestamp_ms",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "confirmed",
            ]
            existing = pd.read_parquet(output_path, columns=comparison_columns)
            expected = source_result.frame[comparison_columns]
            pd.testing.assert_frame_equal(
                existing.reset_index(drop=True),
                expected.reset_index(drop=True),
                check_dtype=False,
                check_exact=True,
            )
            write_canonical_metadata(
                output_path=output_path,
                asset=asset,
                content_sha256=content_hash,
                quality=quality,
            )
            return CanonicalAsset(
                sourcePath=asset.sourcePath,
                outputPath=str(output_path),
                status="existing",
                marketType=asset.marketType,
                instrumentId=asset.instrumentId,
                timeframe=asset.timeframe,
                contentSha256=content_hash,
                quality=quality,
            )
        except AssertionError as exc:
            return CanonicalAsset(
                sourcePath=asset.sourcePath,
                outputPath=None,
                status="failed_existing_mismatch",
                marketType=asset.marketType,
                instrumentId=asset.instrumentId,
                timeframe=asset.timeframe,
                contentSha256=None,
                quality=None,
                error=str(exc),
            )
        except Exception as exc:  # noqa: BLE001 - isolate one corrupt reusable asset.
            return CanonicalAsset(
                sourcePath=asset.sourcePath,
                outputPath=None,
                status="failed",
                marketType=asset.marketType,
                instrumentId=asset.instrumentId,
                timeframe=asset.timeframe,
                contentSha256=None,
                quality=None,
                error=str(exc),
            )
    try:
        result = read_ohlcv(asset.sourcePath)
        quality = inspect_quality(result, asset.timeframe)
        if quality.errors:
            return CanonicalAsset(
                sourcePath=asset.sourcePath,
                outputPath=None,
                status="failed_quality",
                marketType=asset.marketType,
                instrumentId=asset.instrumentId,
                timeframe=asset.timeframe,
                contentSha256=None,
                quality=quality,
                error=";".join(quality.errors),
            )
        frame = result.frame.copy()
        frame["exchange"] = exchange
        frame["market_type"] = asset.marketType
        frame["instrument_id"] = asset.instrumentId
        frame["timeframe"] = asset.timeframe
        frame["source_sha256"] = asset.sha256
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = output_path.with_name(f"{output_path.name}.tmp")
        frame.to_parquet(temporary, index=False, compression="zstd")
        os.replace(temporary, output_path)
        content_hash = sha256_file(output_path)
        write_canonical_metadata(
            output_path=output_path,
            asset=asset,
            content_sha256=content_hash,
            quality=quality,
        )
        return CanonicalAsset(
            sourcePath=asset.sourcePath,
            outputPath=str(output_path),
            status="created",
            marketType=asset.marketType,
            instrumentId=asset.instrumentId,
            timeframe=asset.timeframe,
            contentSha256=content_hash,
            quality=quality,
        )
    except Exception as exc:  # noqa: BLE001 - one source failure must not corrupt the batch.
        return CanonicalAsset(
            sourcePath=asset.sourcePath,
            outputPath=None,
            status="failed",
            marketType=asset.marketType,
            instrumentId=asset.instrumentId,
            timeframe=asset.timeframe,
            contentSha256=None,
            quality=None,
            error=str(exc),
        )
