"""Verified artifact catalog and bounded OKX Spot history collector for V37A."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .checkpoint import load_json, write_json_atomic
from .okx_official_v1 import BAR_DURATION_MS, parse_confirmed_candle_rows


OKX_HISTORY_ENDPOINT = "https://openapi.okx.com/api/v5/market/history-candles"


def _hash_digest(value: str, *, length: int) -> str:
    return value.rsplit("_", 1)[-1][:length]


class ArtifactIntegrityError(RuntimeError):
    """Raised when a referenced immutable artifact no longer matches evidence."""


@dataclass(frozen=True)
class CatalogArtifact:
    path: Path
    sha256: str
    manifest_path: Path
    manifest_sha256: str
    source_type: str
    instrument_id: str
    timeframe: str
    row_count: int
    start_timestamp_ms: int
    end_timestamp_ms: int
    details: dict[str, Any]


@dataclass(frozen=True)
class SpotCollectionResult:
    status: str
    artifact: CatalogArtifact
    request_count: int
    downloaded_rows: int


@dataclass(frozen=True)
class FundingConsolidationResult:
    status: str
    artifact: CatalogArtifact
    source_count: int


class FundingCarryCatalog:
    """Discover only artifacts with traceable paths and matching hashes."""

    def __init__(self, warehouse_root: Path | str) -> None:
        self.warehouse_root = Path(warehouse_root).resolve()
        self.v34_root = self.warehouse_root / "okx_official_v1"
        self.v37a_root = self.v34_root / "funding_carry_v37a"

    def _artifact_from_manifest(
        self,
        manifest_path: Path,
        manifest: dict[str, Any],
        *,
        source_type: str,
    ) -> CatalogArtifact:
        expected = str(manifest.get("outputSha256") or "")
        declared_output = Path(str(manifest.get("outputPath") or "")).resolve()
        output = declared_output
        path_resolution = "manifest_output_path"
        try:
            inside = output.is_relative_to(self.warehouse_root)
        except (OSError, ValueError):
            inside = False
        if inside and output.is_file():
            if not expected or sha256_file(output) != expected:
                raise ArtifactIntegrityError("content_hash_mismatch")
        else:
            basename = declared_output.name
            matches = [
                candidate.resolve()
                for candidate in self.v34_root.rglob(basename)
                if candidate.is_file()
                and expected
                and sha256_file(candidate) == expected
            ]
            unique_matches = sorted(set(matches))
            if len(unique_matches) != 1:
                reason = (
                    "ambiguous_relocated_output"
                    if len(unique_matches) > 1
                    else "missing_or_out_of_scope_output"
                )
                raise ArtifactIntegrityError(reason)
            output = unique_matches[0]
            path_resolution = "warehouse_unique_sha256"
        actual = sha256_file(output)
        if not expected or expected != actual:
            raise ArtifactIntegrityError("content_hash_mismatch")
        frame = pd.read_parquet(output)
        if frame.empty or "timestamp_ms" not in frame.columns:
            raise ArtifactIntegrityError("empty_or_invalid_partition")
        timestamps = pd.to_numeric(frame["timestamp_ms"], errors="coerce")
        if timestamps.isna().any() or timestamps.duplicated().any():
            raise ArtifactIntegrityError("invalid_partition_timestamps")
        return CatalogArtifact(
            path=output,
            sha256=actual,
            manifest_path=manifest_path.resolve(),
            manifest_sha256=sha256_file(manifest_path),
            source_type=source_type,
            instrument_id=str(manifest["instrumentId"]),
            timeframe=str(manifest["timeframe"]),
            row_count=int(len(frame)),
            start_timestamp_ms=int(timestamps.min()),
            end_timestamp_ms=int(timestamps.max()),
            details={**manifest, "pathResolution": path_resolution},
        )

    def perpetual_partition(
        self, *, instrument_id: str, timeframe: str
    ) -> CatalogArtifact:
        root = self.v34_root / "manifests"
        paths = sorted(
            root.glob(f"{instrument_id}-{timeframe}-*.json"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for path in paths:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if (
                manifest.get("schemaVersion")
                != "okx_official_v1_partition_manifest_v1"
                or manifest.get("instrumentId") != instrument_id
                or manifest.get("timeframe") != timeframe
            ):
                continue
            return self._artifact_from_manifest(
                path, manifest, source_type="okx_perpetual_ohlcv"
            )
        raise FileNotFoundError(
            f"verified_perpetual_partition_missing:{instrument_id}:{timeframe}"
        )

    def spot_partition(
        self, *, instrument_id: str, timeframe: str
    ) -> CatalogArtifact:
        root = self.v37a_root / "manifests" / "spot"
        paths = sorted(
            root.glob(f"{instrument_id}-{timeframe}-*.json"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for path in paths:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if (
                manifest.get("schemaVersion")
                != "v37a_okx_spot_partition_manifest_v1"
                or manifest.get("instrumentId") != instrument_id
                or manifest.get("timeframe") != timeframe
            ):
                continue
            return self._artifact_from_manifest(
                path, manifest, source_type="okx_spot_ohlcv"
            )
        raise FileNotFoundError(
            f"verified_spot_partition_missing:{instrument_id}:{timeframe}"
        )

    def funding_partition(self, *, instrument_id: str) -> CatalogArtifact:
        root = self.v37a_root / "manifests" / "funding"
        paths = sorted(
            root.glob(f"{instrument_id}-*.json"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for path in paths:
            manifest = json.loads(path.read_text(encoding="utf-8"))
            if (
                manifest.get("schemaVersion")
                != "v37a_okx_funding_partition_manifest_v1"
                or manifest.get("instrumentId") != instrument_id
            ):
                continue
            return self._artifact_from_manifest(
                path, manifest, source_type="okx_realized_funding"
            )
        raise FileNotFoundError(
            f"verified_funding_partition_missing:{instrument_id}"
        )


def _funding_timestamp_ms(values: pd.Series, *, column: str) -> pd.Series:
    parsed = pd.to_datetime(values, utc=True, errors="coerce")
    if parsed.isna().any():
        raise ArtifactIntegrityError(f"invalid_funding_timestamp:{column}")
    return parsed.map(lambda value: pd.Timestamp(value).value // 1_000_000).astype(
        "int64"
    )


def _normalize_funding_frame(
    frame: pd.DataFrame, *, instrument_id: str
) -> pd.DataFrame:
    if {"instrument_id", "timestamp_ms", "funding_rate", "available_at"}.issubset(
        frame.columns
    ):
        normalized = frame[
            ["instrument_id", "timestamp_ms", "funding_rate", "available_at"]
        ].copy()
    elif {
        "instrumentId",
        "fundingTime",
        "realizedRateAvailableAt",
    }.issubset(frame.columns) and (
        "realizedRate" in frame.columns or "fundingRate" in frame.columns
    ):
        rate_column = (
            "realizedRate" if "realizedRate" in frame.columns else "fundingRate"
        )
        normalized = pd.DataFrame(
            {
                "instrument_id": frame["instrumentId"],
                "timestamp_ms": frame["fundingTime"],
                "funding_rate": frame[rate_column],
                "available_at": frame["realizedRateAvailableAt"],
            }
        )
    else:
        raise ArtifactIntegrityError("unsupported_funding_source_schema")
    if set(normalized["instrument_id"].dropna().astype(str)) != {instrument_id}:
        raise ArtifactIntegrityError("funding_source_instrument_mismatch")
    normalized["timestamp_ms"] = pd.to_numeric(
        normalized["timestamp_ms"], errors="coerce"
    )
    normalized["funding_rate"] = pd.to_numeric(
        normalized["funding_rate"], errors="coerce"
    )
    available_ms = _funding_timestamp_ms(
        normalized["available_at"], column="available_at"
    )
    if normalized[["timestamp_ms", "funding_rate"]].isna().any().any():
        raise ArtifactIntegrityError("invalid_funding_source_values")
    normalized["timestamp_ms"] = normalized["timestamp_ms"].astype("int64")
    if (available_ms < normalized["timestamp_ms"]).any():
        raise ArtifactIntegrityError("funding_available_before_funding_time")
    normalized["available_at"] = pd.to_datetime(
        available_ms, unit="ms", utc=True
    ).map(lambda value: value.isoformat())
    return normalized.sort_values("timestamp_ms").reset_index(drop=True)


class FundingHistoryConsolidator:
    """Build one immutable actual-funding partition from verified V36/V34B inputs."""

    def __init__(self, warehouse_root: Path | str) -> None:
        self.catalog = FundingCarryCatalog(warehouse_root)
        self.warehouse_root = self.catalog.warehouse_root

    def _inside_file(self, value: str) -> Path:
        path = Path(value).resolve()
        try:
            inside = path.is_relative_to(self.warehouse_root)
        except (OSError, ValueError):
            inside = False
        if not inside or not path.is_file():
            raise ArtifactIntegrityError("funding_source_path_invalid")
        return path

    def _v36_sources(self, instrument_id: str) -> list[dict[str, Any]]:
        root = (
            self.warehouse_root
            / "_alphapilot"
            / "evidence"
            / "okx"
            / "funding_history"
            / "manifests"
        )
        sources: list[dict[str, Any]] = []
        for manifest_path in sorted(root.glob("*.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                manifest.get("schemaVersion") != "v36_okx_historical_funding_v1"
                or manifest.get("status") != "completed"
                or manifest.get("sameExchangeOnly") is not True
                or manifest.get("zeroFillUsed") is not False
            ):
                continue
            for artifact in manifest.get("artifacts", []):
                if (
                    artifact.get("artifactType") != "monthlyFundingArchive"
                    or artifact.get("instrumentId") != instrument_id
                ):
                    continue
                raw = self._inside_file(str(artifact.get("rawPath") or ""))
                if sha256_file(raw) != str(artifact.get("archiveSha256") or ""):
                    raise ArtifactIntegrityError("funding_archive_hash_mismatch")
                canonical = self._inside_file(
                    str(artifact.get("canonicalPath") or "")
                )
                sources.append(
                    {
                        "generation": "v36_monthly_archive",
                        "path": canonical,
                        "sha256": sha256_file(canonical),
                        "manifestPath": manifest_path.resolve(),
                        "manifestSha256": sha256_file(manifest_path),
                        "rawPath": raw,
                        "rawSha256": sha256_file(raw),
                    }
                )
        return sources

    def _resolve_v34_artifact(
        self, artifact: dict[str, Any]
    ) -> Path:
        declared = Path(str(artifact.get("path") or "")).resolve()
        expected = str(artifact.get("sha256") or "")
        try:
            inside = declared.is_relative_to(self.warehouse_root)
        except (OSError, ValueError):
            inside = False
        if inside and declared.is_file():
            if sha256_file(declared) != expected:
                raise ArtifactIntegrityError("v34b_funding_hash_mismatch")
            return declared
        matches = [
            path.resolve()
            for path in self.catalog.v34_root.rglob(declared.name)
            if path.is_file() and expected and sha256_file(path) == expected
        ]
        if len(set(matches)) != 1:
            raise ArtifactIntegrityError("v34b_funding_relocation_failed")
        return next(iter(set(matches)))

    def _v34b_sources(self, instrument_id: str) -> list[dict[str, Any]]:
        root = self.catalog.v34_root / "manifests" / "v34b"
        sources: list[dict[str, Any]] = []
        for manifest_path in sorted(root.glob("funding-*.json")):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if (
                manifest.get("schemaVersion")
                != "okx_official_v1_v34b_funding_manifest_v1"
                or manifest.get("publicDataOnly") is not True
            ):
                continue
            for artifact in manifest.get("artifacts", []):
                if artifact.get("instrumentId") != instrument_id:
                    continue
                canonical = self._resolve_v34_artifact(artifact)
                sources.append(
                    {
                        "generation": "v34b_recent_public_history",
                        "path": canonical,
                        "sha256": sha256_file(canonical),
                        "manifestPath": manifest_path.resolve(),
                        "manifestSha256": sha256_file(manifest_path),
                    }
                )
        return sources

    def consolidate(
        self, instrument_id: str, *, observed_at: str
    ) -> FundingConsolidationResult:
        try:
            artifact = self.catalog.funding_partition(instrument_id=instrument_id)
            return FundingConsolidationResult(
                status="reused", artifact=artifact, source_count=int(
                    len(artifact.details.get("sources", []))
                )
            )
        except FileNotFoundError:
            pass

        sources = self._v36_sources(instrument_id) + self._v34b_sources(
            instrument_id
        )
        if not sources:
            raise FileNotFoundError(
                f"verified_actual_funding_sources_missing:{instrument_id}"
            )
        frames: list[pd.DataFrame] = []
        source_records: list[dict[str, Any]] = []
        for source in sources:
            frame = _normalize_funding_frame(
                pd.read_parquet(source["path"]), instrument_id=instrument_id
            )
            frames.append(frame)
            source_records.append(
                {
                    key: str(value) if isinstance(value, Path) else value
                    for key, value in source.items()
                }
                | {"rowCount": int(len(frame))}
            )
        consolidated = pd.concat(frames, ignore_index=True)
        consolidated = consolidated.sort_values(
            ["timestamp_ms", "available_at"]
        ).drop_duplicates("timestamp_ms", keep="last")
        consolidated = consolidated.reset_index(drop=True)
        identity = stable_hash(
            consolidated.to_dict(orient="records"), prefix="v37a_actual_funding"
        )
        output = (
            self.catalog.v37a_root
            / "canonical"
            / "funding"
            / instrument_id
            / (
                f"{int(consolidated['timestamp_ms'].min())}-"
                f"{int(consolidated['timestamp_ms'].max())}-"
                f"{_hash_digest(identity, length=16)}.parquet"
            )
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        if not output.is_file():
            temporary = output.with_suffix(".parquet.tmp")
            consolidated.to_parquet(temporary, index=False, compression="zstd")
            temporary.replace(output)
        manifest = {
            "schemaVersion": "v37a_okx_funding_partition_manifest_v1",
            "instrumentId": instrument_id,
            "timeframe": "funding",
            "observedAt": observed_at,
            "sourceEndpoint": "verified_v36_monthly_plus_v34b_recent",
            "outputPath": str(output.resolve()),
            "outputSha256": sha256_file(output),
            "rowCount": int(len(consolidated)),
            "startTimestampMs": int(consolidated["timestamp_ms"].min()),
            "endTimestampMs": int(consolidated["timestamp_ms"].max()),
            "sources": source_records,
            "publicDataOnly": True,
            "actualFundingOnly": True,
            "sameExchangeOnly": True,
            "zeroFillUsed": False,
            "candidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "releaseCount": 0,
            "demoArmCount": 0,
            "orderCount": 0,
        }
        manifest_identity = stable_hash(manifest, prefix="v37a_funding_manifest")
        manifest_path = (
            self.catalog.v37a_root
            / "manifests"
            / "funding"
            / f"{instrument_id}-{_hash_digest(manifest_identity, length=20)}.json"
        )
        write_json_atomic(manifest_path, manifest)
        artifact = self.catalog.funding_partition(instrument_id=instrument_id)
        return FundingConsolidationResult(
            status="consolidated",
            artifact=artifact,
            source_count=len(source_records),
        )


class OkxSpotHistoryCollector:
    """Collect a bounded missing Spot partition without touching V34 artifacts."""

    def __init__(
        self,
        *,
        warehouse_root: Path | str,
        client: Any,
        timeframe: str,
        requested_start_ms: int,
    ) -> None:
        if timeframe not in BAR_DURATION_MS:
            raise ValueError(f"unsupported_v37a_spot_timeframe:{timeframe}")
        self.catalog = FundingCarryCatalog(warehouse_root)
        self.client = client
        self.timeframe = timeframe
        self.requested_start_ms = max(0, int(requested_start_ms))

    def collect(self, instrument_id: str, *, observed_at: str) -> SpotCollectionResult:
        try:
            artifact = self.catalog.spot_partition(
                instrument_id=instrument_id, timeframe=self.timeframe
            )
            return SpotCollectionResult(
                status="reused",
                artifact=artifact,
                request_count=0,
                downloaded_rows=0,
            )
        except FileNotFoundError:
            pass

        root = self.catalog.v37a_root
        checkpoint_path = root / "checkpoints" / f"{instrument_id}-{self.timeframe}.json"
        checkpoint = load_json(checkpoint_path)
        resume_valid = (
            checkpoint.get("schemaVersion") == "v37a_okx_spot_checkpoint_v1"
            and checkpoint.get("instrumentId") == instrument_id
            and checkpoint.get("timeframe") == self.timeframe
            and int(checkpoint.get("requestedStartMs") or 0) == self.requested_start_ms
        )
        durable_rows = [
            list(row)
            for row in checkpoint.get("rows", [])
            if resume_valid and isinstance(row, list)
        ]
        prior_request_count = int(checkpoint.get("requestCount") or 0) if resume_valid else 0
        oldest = checkpoint.get("oldestTimestampMs") if resume_valid else None
        initial_after = int(oldest) if oldest is not None else None
        elapsed = max(
            0,
            int(datetime.now(UTC).timestamp() * 1_000) - self.requested_start_ms,
        )
        max_pages = min(
            10_000,
            max(1, math.ceil(elapsed / BAR_DURATION_MS[self.timeframe] / 100) + 2),
        )

        def progress(value: dict[str, Any]) -> None:
            page_rows = value.get("pageRows")
            if isinstance(page_rows, list):
                durable_rows.extend(
                    list(row) for row in page_rows if isinstance(row, list)
                )
            unique = {int(row[0]): row for row in durable_rows if row}
            durable_rows[:] = [unique[key] for key in sorted(unique)]
            write_json_atomic(
                checkpoint_path,
                {
                    "schemaVersion": "v37a_okx_spot_checkpoint_v1",
                    "instrumentId": instrument_id,
                    "timeframe": self.timeframe,
                    "requestedStartMs": self.requested_start_ms,
                    "requestCount": prior_request_count
                    + int(value.get("requestCount") or 0),
                    "oldestTimestampMs": value.get("oldestTimestampMs"),
                    "rows": durable_rows,
                    "updatedAt": observed_at,
                },
            )

        rows, current_request_count = self.client.history_candle_rows(
            instrument_id=instrument_id,
            timeframe=self.timeframe,
            start_exclusive_ms=max(0, self.requested_start_ms - 1),
            max_pages=max(1, max_pages - prior_request_count),
            initial_after_ms=initial_after,
            page_progress=progress,
        )
        all_rows = durable_rows + [list(row) for row in rows]
        unique_rows = {int(row[0]): row for row in all_rows if row}
        ordered_rows = [unique_rows[key] for key in sorted(unique_rows)]
        frame = parse_confirmed_candle_rows(
            ordered_rows,
            timeframe=self.timeframe,
            ingested_at=observed_at,
        )
        if frame.empty:
            raise RuntimeError(f"okx_spot_history_empty:{instrument_id}")

        raw_identity = stable_hash(ordered_rows, prefix="v37a_okx_spot_raw")
        raw_path = (
            root
            / "raw"
            / "spot"
            / instrument_id
            / self.timeframe
            / f"rows-{_hash_digest(raw_identity, length=20)}.json"
        )
        write_json_atomic(
            raw_path,
            {
                "schemaVersion": "v37a_okx_spot_raw_rows_v1",
                "instrumentId": instrument_id,
                "instrumentType": "SPOT",
                "timeframe": self.timeframe,
                "sourceEndpoint": OKX_HISTORY_ENDPOINT,
                "observedAt": observed_at,
                "rows": ordered_rows,
            },
        )
        timestamps = frame["timestamp_ms"].astype("int64")
        frame_identity = stable_hash(
            {
                "instrumentId": instrument_id,
                "timeframe": self.timeframe,
                "timestamps": timestamps.tolist(),
                "close": frame["close"].astype(float).round(12).tolist(),
            },
            prefix="v37a_okx_spot_partition",
        )
        output = (
            root
            / "canonical"
            / "spot"
            / "ohlcv"
            / instrument_id
            / self.timeframe
            / (
                f"{int(timestamps.min())}-{int(timestamps.max())}-"
                f"{_hash_digest(frame_identity, length=16)}.parquet"
            )
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        if not output.is_file():
            frame.to_parquet(output, index=False, compression="zstd")
        output_hash = sha256_file(output)
        request_count = prior_request_count + int(current_request_count)
        manifest = {
            "schemaVersion": "v37a_okx_spot_partition_manifest_v1",
            "instrumentId": instrument_id,
            "instrumentType": "SPOT",
            "timeframe": self.timeframe,
            "sourceEndpoint": OKX_HISTORY_ENDPOINT,
            "confirmedOnly": True,
            "availableAtRule": "timestamp_ms_plus_bar_duration",
            "observedAt": observed_at,
            "rawPath": str(raw_path.resolve()),
            "rawSha256": sha256_file(raw_path),
            "outputPath": str(output.resolve()),
            "outputSha256": output_hash,
            "rowCount": int(len(frame)),
            "startTimestampMs": int(timestamps.min()),
            "endTimestampMs": int(timestamps.max()),
            "requestCount": request_count,
            "publicDataOnly": True,
            "zeroFillUsed": False,
            "crossExchangeSubstitution": False,
            "candidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "releaseCount": 0,
            "demoArmCount": 0,
            "orderCount": 0,
        }
        manifest_identity = stable_hash(manifest, prefix="v37a_spot_manifest")
        manifest_path = (
            root
            / "manifests"
            / "spot"
            / (
                f"{instrument_id}-{self.timeframe}-"
                f"{_hash_digest(manifest_identity, length=20)}.json"
            )
        )
        write_json_atomic(manifest_path, manifest)
        checkpoint_path.unlink(missing_ok=True)
        artifact = self.catalog.spot_partition(
            instrument_id=instrument_id, timeframe=self.timeframe
        )
        return SpotCollectionResult(
            status="collected",
            artifact=artifact,
            request_count=request_count,
            downloaded_rows=int(len(frame)),
        )
