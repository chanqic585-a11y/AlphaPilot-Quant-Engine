"""Audited OKX public-data layer for the bounded V34A pilot."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
import hashlib
import json
import math

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.evolution.registry.hashing import stable_hash

from .checkpoint import load_json, write_json_atomic
from .okx_public import OkxPublicClient


OKX_HISTORY_ENDPOINT = "https://openapi.okx.com/api/v5/market/history-candles"
OKX_BAR_VALUES = {"1h": "1H", "4h": "4H", "1dutc": "1Dutc"}
BAR_DURATION_MS = {
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1dutc": 24 * 60 * 60 * 1000,
}
PILOT_INSTRUMENTS = (
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
)
PILOT_TIMEFRAMES = ("1h", "4h", "1dutc")


@dataclass(frozen=True)
class OkxOfficialV1Layout:
    warehouseRoot: Path
    root: Path
    rawRoot: Path
    normalizedRoot: Path
    canonicalRoot: Path
    metadataSnapshotRoot: Path
    forwardCollectionRoot: Path
    manifestRoot: Path
    auditRoot: Path
    quarantineRoot: Path
    checkpointRoot: Path
    temporaryRoot: Path

    @classmethod
    def from_warehouse(cls, warehouse_root: Path | str) -> "OkxOfficialV1Layout":
        warehouse = Path(warehouse_root).resolve()
        root = (warehouse / "okx_official_v1").resolve()
        return cls(
            warehouseRoot=warehouse,
            root=root,
            rawRoot=root / "raw",
            normalizedRoot=root / "normalized",
            canonicalRoot=root / "canonical",
            metadataSnapshotRoot=root / "metadata_snapshots",
            forwardCollectionRoot=root / "forward_collection",
            manifestRoot=root / "manifests",
            auditRoot=root / "audit",
            quarantineRoot=root / "quarantine",
            checkpointRoot=root / "checkpoints",
            temporaryRoot=root / "tmp",
        )

    def ensure_directories(self) -> None:
        self.warehouseRoot.mkdir(parents=True, exist_ok=True)
        if not self.root.is_relative_to(self.warehouseRoot):
            raise ValueError("okx_official_v1_root_outside_approved_warehouse")
        for path in (
            self.rawRoot,
            self.normalizedRoot,
            self.canonicalRoot,
            self.metadataSnapshotRoot,
            self.forwardCollectionRoot,
            self.manifestRoot,
            self.auditRoot,
            self.quarantineRoot,
            self.checkpointRoot,
            self.temporaryRoot,
        ):
            path.mkdir(parents=True, exist_ok=True)


def _empty_candle_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "timestamp_ms",
            "date",
            "open",
            "high",
            "low",
            "close",
            "vol",
            "volCcy",
            "volCcyQuote",
            "confirm",
            "availableAt",
            "ingestedAt",
        ]
    )


def parse_confirmed_candle_rows(
    rows: list[list[Any]],
    *,
    timeframe: str,
    ingested_at: str,
) -> pd.DataFrame:
    """Parse the documented nine-field OKX candle contract and fail on drift."""

    if timeframe not in BAR_DURATION_MS:
        raise ValueError(f"unsupported_okx_official_v1_timeframe:{timeframe}")
    for row in rows:
        if not isinstance(row, list):
            raise ValueError("okx_history_candle_schema_drift:row_is_not_array")
        if len(row) != 9:
            raise ValueError(
                "okx_history_candle_schema_drift:expected_9_fields:"
                f"got_{len(row)}"
            )
    accepted = [row for row in rows if str(row[8]) == "1"]
    if not accepted:
        return _empty_candle_frame()
    frame = pd.DataFrame(
        {
            "timestamp_ms": [int(row[0]) for row in accepted],
            "open": [float(row[1]) for row in accepted],
            "high": [float(row[2]) for row in accepted],
            "low": [float(row[3]) for row in accepted],
            "close": [float(row[4]) for row in accepted],
            "vol": [float(row[5]) for row in accepted],
            "volCcy": [float(row[6]) for row in accepted],
            "volCcyQuote": [float(row[7]) for row in accepted],
            "confirm": [int(row[8]) for row in accepted],
        }
    )
    frame["date"] = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True)
    available = pd.to_datetime(
        frame["timestamp_ms"] + BAR_DURATION_MS[timeframe], unit="ms", utc=True
    )
    frame["availableAt"] = available.map(lambda value: value.isoformat())
    frame["ingestedAt"] = ingested_at
    return frame[
        [
            "timestamp_ms",
            "date",
            "open",
            "high",
            "low",
            "close",
            "vol",
            "volCcy",
            "volCcyQuote",
            "confirm",
            "availableAt",
            "ingestedAt",
        ]
    ].drop_duplicates("timestamp_ms", keep="last").sort_values("timestamp_ms").reset_index(drop=True)


@dataclass(frozen=True)
class ExistingPartitionAudit:
    instrumentId: str
    timeframe: str
    classification: str
    rows: int
    startTimestampMs: int | None
    latestTimestampMs: int | None
    outputPath: str | None
    outputSha256: str | None
    manifestPath: str | None
    manifestCount: int
    incompatibleExistingCount: int
    reason: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ExistingOkxPartitionAuditor:
    """Validate reusable V13-era partitions without silently changing semantics."""

    def __init__(self, warehouse_root: Path | str) -> None:
        self.warehouse_root = Path(warehouse_root).resolve()
        self.manifest_root = (
            self.warehouse_root
            / "_alphapilot"
            / "official"
            / "okx"
            / "raw"
            / "manifests"
        )
        self.canonical_root = (
            self.warehouse_root
            / "_alphapilot"
            / "canonical"
            / "okx"
            / "swap"
            / "ohlcv"
        ).resolve()

    @staticmethod
    def _load_manifest(path: Path) -> dict[str, Any] | None:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return None
        return value if isinstance(value, dict) else None

    def _manifest_paths(self, instrument_id: str, timeframe: str) -> list[Path]:
        if not self.manifest_root.is_dir():
            return []
        return sorted(
            self.manifest_root.glob(f"{instrument_id}-{timeframe}-*.json"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )

    def _validate_candidate(
        self,
        manifest_path: Path,
        row: dict[str, Any],
        *,
        timeframe: str,
    ) -> tuple[pd.DataFrame | None, str | None]:
        if row.get("schemaVersion") != "okx_official_partition_manifest_v1":
            return None, "unsupported_manifest_schema"
        if str(row.get("sourceEndpoint") or "") != OKX_HISTORY_ENDPOINT:
            return None, "non_okx_history_endpoint"
        requested = row.get("requestParameters") or {}
        if not bool(requested.get("confirmedOnly")):
            return None, "manifest_does_not_require_confirmed_rows"
        if str(row.get("timeframe") or "") != timeframe:
            return None, "timeframe_semantics_mismatch"
        output = Path(str(row.get("outputPath") or ""))
        expected_hash = str(row.get("outputSha256") or "")
        try:
            inside_root = output.resolve().is_relative_to(self.canonical_root)
        except (OSError, ValueError):
            inside_root = False
        if not inside_root or not output.is_file():
            return None, "missing_or_out_of_scope_output"
        if not expected_hash or sha256_file(output) != expected_hash:
            return None, "content_hash_mismatch"
        try:
            frame = pd.read_parquet(output)
        except Exception as error:  # pragma: no cover - engine detail is recorded
            return None, f"parquet_read_failed:{type(error).__name__}"
        required = {
            "timestamp_ms",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "confirmed",
        }
        if not required.issubset(frame.columns):
            return None, "legacy_partition_missing_required_columns"
        if frame.empty:
            return None, "empty_partition"
        timestamps = pd.to_numeric(frame["timestamp_ms"], errors="coerce")
        if timestamps.isna().any() or timestamps.duplicated().any():
            return None, "invalid_or_duplicate_timestamps"
        if (pd.to_numeric(frame["confirmed"], errors="coerce") != 1).any():
            return None, "unconfirmed_rows_present"
        interval = BAR_DURATION_MS[timeframe]
        ordered = timestamps.sort_values()
        differences = ordered.diff().dropna()
        if (ordered % interval != 0).any() or (
            not differences.empty and (differences % interval != 0).any()
        ):
            return None, "timestamp_alignment_mismatch"
        return frame, None

    def audit(self, *, instrument_id: str, timeframe: str) -> ExistingPartitionAudit:
        if timeframe not in BAR_DURATION_MS:
            raise ValueError(f"unsupported_okx_official_v1_timeframe:{timeframe}")
        paths = self._manifest_paths(instrument_id, timeframe)
        incompatible = 0
        missing_reason = "no_matching_manifest"
        if timeframe == "1dutc" and not paths:
            incompatible = len(self._manifest_paths(instrument_id, "1d"))
            if incompatible:
                missing_reason = "legacy_1d_is_not_1dutc"
        failures: list[str] = []
        valid: list[tuple[int, Path, dict[str, Any], pd.DataFrame]] = []
        for manifest_path in paths:
            row = self._load_manifest(manifest_path)
            if row is None:
                failures.append("invalid_manifest_json")
                continue
            frame, error = self._validate_candidate(
                manifest_path,
                row,
                timeframe=timeframe,
            )
            if error or frame is None:
                failures.append(str(error))
                continue
            latest = int(pd.to_numeric(frame["timestamp_ms"]).max())
            valid.append((latest, manifest_path, row, frame))
        if not valid:
            classification = (
                "quarantine_required" if paths and failures else "missing_official_partition"
            )
            return ExistingPartitionAudit(
                instrumentId=instrument_id,
                timeframe=timeframe,
                classification=classification,
                rows=0,
                startTimestampMs=None,
                latestTimestampMs=None,
                outputPath=None,
                outputSha256=None,
                manifestPath=None,
                manifestCount=len(paths),
                incompatibleExistingCount=incompatible,
                reason=";".join(sorted(set(failures))) if failures else missing_reason,
            )
        latest, manifest_path, row, frame = max(valid, key=lambda item: item[0])
        timestamps = pd.to_numeric(frame["timestamp_ms"])
        return ExistingPartitionAudit(
            instrumentId=instrument_id,
            timeframe=timeframe,
            classification="verified_existing_okx",
            rows=len(frame),
            startTimestampMs=int(timestamps.min()),
            latestTimestampMs=latest,
            outputPath=str(Path(str(row["outputPath"])).resolve()),
            outputSha256=str(row["outputSha256"]),
            manifestPath=str(manifest_path.resolve()),
            manifestCount=len(paths),
            incompatibleExistingCount=incompatible,
            reason=None,
        )


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _legacy_to_v1(
    frame: pd.DataFrame,
    *,
    timeframe: str,
    ingested_at: str,
) -> pd.DataFrame:
    timestamps = pd.to_numeric(frame["timestamp_ms"], errors="raise").astype("int64")
    converted = pd.DataFrame(
        {
            "timestamp_ms": timestamps,
            "date": pd.to_datetime(timestamps, unit="ms", utc=True),
            "open": pd.to_numeric(frame["open"], errors="raise"),
            "high": pd.to_numeric(frame["high"], errors="raise"),
            "low": pd.to_numeric(frame["low"], errors="raise"),
            "close": pd.to_numeric(frame["close"], errors="raise"),
            "vol": float("nan"),
            "volCcy": float("nan"),
            # The legacy collector explicitly mapped OKX item[7] to volume.
            "volCcyQuote": pd.to_numeric(frame["volume"], errors="raise"),
            "confirm": pd.to_numeric(frame["confirmed"], errors="raise").astype(int),
        }
    )
    available = pd.to_datetime(
        converted["timestamp_ms"] + BAR_DURATION_MS[timeframe],
        unit="ms",
        utc=True,
    )
    converted["availableAt"] = available.map(lambda value: value.isoformat())
    converted["ingestedAt"] = ingested_at
    return converted


def _quality_metrics(frame: pd.DataFrame, *, timeframe: str) -> dict[str, Any]:
    if frame.empty:
        return {
            "status": "invalid",
            "rows": 0,
            "errors": ["empty_partition"],
            "gapEventCount": 0,
            "missingBarCount": 0,
        }
    required = {
        "timestamp_ms",
        "date",
        "open",
        "high",
        "low",
        "close",
        "vol",
        "volCcy",
        "volCcyQuote",
        "confirm",
        "availableAt",
        "ingestedAt",
    }
    errors: list[str] = []
    missing = sorted(required - set(frame.columns))
    if missing:
        errors.append(f"missing_columns:{','.join(missing)}")
    ordered = frame.drop_duplicates("timestamp_ms", keep="last").sort_values(
        "timestamp_ms"
    )
    timestamps = pd.to_numeric(ordered["timestamp_ms"], errors="coerce")
    if timestamps.isna().any() or len(ordered) != len(frame):
        errors.append("invalid_or_duplicate_timestamps")
    if (pd.to_numeric(ordered["confirm"], errors="coerce") != 1).any():
        errors.append("unconfirmed_rows_present")
    numeric = ordered[["open", "high", "low", "close", "volCcyQuote"]].apply(
        pd.to_numeric,
        errors="coerce",
    )
    if numeric.isna().any().any():
        errors.append("non_numeric_required_market_fields")
    invalid_ohlc = (
        (numeric["low"] > numeric["high"])
        | (numeric["open"] < numeric["low"])
        | (numeric["open"] > numeric["high"])
        | (numeric["close"] < numeric["low"])
        | (numeric["close"] > numeric["high"])
        | (numeric["volCcyQuote"] < 0)
    )
    if invalid_ohlc.any():
        errors.append("invalid_ohlcv")
    interval = BAR_DURATION_MS[timeframe]
    if (timestamps % interval != 0).any():
        errors.append("timestamp_alignment_mismatch")
    differences = timestamps.diff().dropna()
    if (differences <= 0).any() or (differences % interval != 0).any():
        errors.append("non_monotonic_or_misaligned_intervals")
    gaps = differences[differences > interval]
    missing_bars = int(sum(int(value // interval) - 1 for value in gaps))
    expected_available = pd.to_datetime(
        timestamps + interval,
        unit="ms",
        utc=True,
    )
    actual_available = pd.to_datetime(ordered["availableAt"], utc=True, errors="coerce")
    if actual_available.isna().any() or not (
        actual_available.reset_index(drop=True)
        == pd.Series(expected_available).reset_index(drop=True)
    ).all():
        errors.append("available_at_not_candle_close")
    return {
        "status": "valid" if not errors else "invalid",
        "rows": len(ordered),
        "startTime": pd.Timestamp(int(timestamps.min()), unit="ms", tz="UTC").isoformat(),
        "endTime": pd.Timestamp(int(timestamps.max()), unit="ms", tz="UTC").isoformat(),
        "gapEventCount": len(gaps),
        "missingBarCount": missing_bars,
        "errors": sorted(set(errors)),
    }


class OkxOfficialV1Pilot:
    """Reuse audited history and download only missing OKX public rows."""

    def __init__(
        self,
        *,
        warehouse_root: Path | str,
        client: OkxPublicClient,
        instruments: tuple[str, ...] = PILOT_INSTRUMENTS,
        timeframes: tuple[str, ...] = PILOT_TIMEFRAMES,
        requested_start_ms: int = 1_577_836_800_000,
    ) -> None:
        if not instruments or not timeframes:
            raise ValueError("okx_official_v1_pilot_scope_must_not_be_empty")
        invalid_timeframes = sorted(set(timeframes) - set(OKX_BAR_VALUES))
        if invalid_timeframes:
            raise ValueError(
                "unsupported_okx_official_v1_timeframes:"
                + ",".join(invalid_timeframes)
            )
        self.layout = OkxOfficialV1Layout.from_warehouse(warehouse_root)
        self.client = client
        self.instruments = tuple(instruments)
        self.timeframes = tuple(timeframes)
        self.requested_start_ms = max(0, int(requested_start_ms))
        self.legacy_auditor = ExistingOkxPartitionAuditor(warehouse_root)

    def _pilot_base(
        self,
        *,
        instrument_id: str,
        timeframe: str,
    ) -> tuple[pd.DataFrame | None, ExistingPartitionAudit | None]:
        paths = sorted(
            self.layout.manifestRoot.glob(f"{instrument_id}-{timeframe}-*.json"),
            key=lambda path: path.stat().st_mtime_ns,
            reverse=True,
        )
        for path in paths:
            try:
                row = json.loads(path.read_text(encoding="utf-8"))
                output = Path(str(row["outputPath"]))
                expected = str(row["outputSha256"])
                if (
                    row.get("schemaVersion") != "okx_official_v1_partition_manifest_v1"
                    or not output.is_file()
                    or sha256_file(output) != expected
                ):
                    continue
                frame = pd.read_parquet(output)
                quality = _quality_metrics(frame, timeframe=timeframe)
                if quality["status"] != "valid":
                    continue
                timestamps = pd.to_numeric(frame["timestamp_ms"])
                return frame, ExistingPartitionAudit(
                    instrumentId=instrument_id,
                    timeframe=timeframe,
                    classification="verified_okx_official_v1",
                    rows=len(frame),
                    startTimestampMs=int(timestamps.min()),
                    latestTimestampMs=int(timestamps.max()),
                    outputPath=str(output.resolve()),
                    outputSha256=expected,
                    manifestPath=str(path.resolve()),
                    manifestCount=len(paths),
                    incompatibleExistingCount=0,
                    reason=None,
                )
            except (OSError, ValueError, TypeError, KeyError):
                continue
        return None, None

    def _load_base(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        ingested_at: str,
    ) -> tuple[pd.DataFrame, ExistingPartitionAudit]:
        pilot_frame, pilot_audit = self._pilot_base(
            instrument_id=instrument_id,
            timeframe=timeframe,
        )
        if pilot_frame is not None and pilot_audit is not None:
            return pilot_frame, pilot_audit
        audit = self.legacy_auditor.audit(
            instrument_id=instrument_id,
            timeframe=timeframe,
        )
        if audit.classification != "verified_existing_okx" or not audit.outputPath:
            return _empty_candle_frame(), audit
        legacy = pd.read_parquet(audit.outputPath)
        return _legacy_to_v1(
            legacy,
            timeframe=timeframe,
            ingested_at=ingested_at,
        ), audit

    def _write_raw_rows(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        rows: list[list[Any]],
        ingested_at: str,
    ) -> str | None:
        if not rows:
            return None
        digest = stable_hash(rows, prefix="okx_raw_candles")
        output = (
            self.layout.rawRoot
            / instrument_id
            / timeframe
            / f"rows-{digest[:20]}.json"
        )
        write_json_atomic(
            output,
            {
                "schemaVersion": "okx_official_v1_raw_candle_rows_v1",
                "instrumentId": instrument_id,
                "timeframe": timeframe,
                "okxBar": OKX_BAR_VALUES[timeframe],
                "sourceEndpoint": OKX_HISTORY_ENDPOINT,
                "ingestedAt": ingested_at,
                "rows": rows,
            },
        )
        return str(output)

    def _partition(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        ingested_at: str,
    ) -> dict[str, Any]:
        base, audit = self._load_base(
            instrument_id=instrument_id,
            timeframe=timeframe,
            ingested_at=ingested_at,
        )
        start_exclusive = (
            int(base["timestamp_ms"].max())
            if not base.empty
            else max(0, self.requested_start_ms - 1)
        )
        elapsed = max(
            0,
            int(datetime.now(UTC).timestamp() * 1000) - start_exclusive,
        )
        max_pages = min(
            10_000,
            max(1, math.ceil(elapsed / BAR_DURATION_MS[timeframe] / 100) + 2),
        )
        checkpoint_path = (
            self.layout.checkpointRoot / f"{instrument_id}-{timeframe}.json"
        )
        checkpoint = load_json(checkpoint_path)
        resume_valid = (
            checkpoint.get("schemaVersion") == "okx_official_v1_checkpoint_v1"
            and checkpoint.get("instrumentId") == instrument_id
            and checkpoint.get("timeframe") == timeframe
            and int(checkpoint.get("startExclusiveMs") or 0) == start_exclusive
        )
        durable_rows: list[list[Any]] = []
        prior_request_count = 0
        initial_after_ms: int | None = None
        if resume_valid:
            durable_rows = [
                list(row)
                for row in checkpoint.get("rows", [])
                if isinstance(row, list)
            ]
            prior_request_count = int(checkpoint.get("requestCount") or 0)
            value = checkpoint.get("oldestTimestampMs")
            initial_after_ms = int(value) if value is not None else None

        def progress(value: dict[str, Any]) -> None:
            page_rows = value.get("pageRows")
            if isinstance(page_rows, list):
                durable_rows.extend(
                    list(row) for row in page_rows if isinstance(row, list)
                )
            unique_rows = {
                int(row[0]): row
                for row in durable_rows
                if row
            }
            durable_rows[:] = [unique_rows[key] for key in sorted(unique_rows)]
            write_json_atomic(
                checkpoint_path,
                {
                    "schemaVersion": "okx_official_v1_checkpoint_v1",
                    "instrumentId": instrument_id,
                    "timeframe": timeframe,
                    "startExclusiveMs": start_exclusive,
                    "requestCount": prior_request_count
                    + int(value.get("requestCount") or 0),
                    "rowCount": len(durable_rows),
                    "oldestTimestampMs": value.get("oldestTimestampMs"),
                    "maxPages": max_pages,
                    "isFinalPage": bool(value.get("isFinalPage")),
                    "rows": durable_rows,
                    "updatedAt": _utc_now(),
                },
            )

        rows, current_request_count = self.client.history_candle_rows(
            instrument_id=instrument_id,
            timeframe=timeframe,
            start_exclusive_ms=start_exclusive,
            max_pages=max(1, max_pages - prior_request_count),
            initial_after_ms=initial_after_ms,
            page_progress=progress,
        )
        all_rows = durable_rows + [list(row) for row in rows]
        unique_rows = {int(row[0]): row for row in all_rows if row}
        rows = [unique_rows[key] for key in sorted(unique_rows)]
        request_count = prior_request_count + current_request_count
        raw_path = self._write_raw_rows(
            instrument_id=instrument_id,
            timeframe=timeframe,
            rows=rows,
            ingested_at=ingested_at,
        )
        incremental = parse_confirmed_candle_rows(
            rows,
            timeframe=timeframe,
            ingested_at=ingested_at,
        )
        if not incremental.empty:
            normalized_digest = stable_hash(
                {
                    "instrumentId": instrument_id,
                    "timeframe": timeframe,
                    "timestamps": incremental["timestamp_ms"].astype(int).tolist(),
                },
                prefix="okx_normalized_increment",
            )
            normalized_path = (
                self.layout.normalizedRoot
                / instrument_id
                / timeframe
                / f"increment-{normalized_digest[:20]}.parquet"
            )
            normalized_path.parent.mkdir(parents=True, exist_ok=True)
            incremental.to_parquet(normalized_path, index=False, compression="zstd")
        else:
            normalized_path = None
        combined = pd.concat(
            [item for item in (base, incremental) if not item.empty],
            ignore_index=True,
        ) if not base.empty or not incremental.empty else _empty_candle_frame()
        combined = combined.drop_duplicates("timestamp_ms", keep="last").sort_values(
            "timestamp_ms"
        ).reset_index(drop=True)
        quality = _quality_metrics(combined, timeframe=timeframe)
        if quality["status"] != "valid":
            quarantine = (
                self.layout.quarantineRoot
                / f"{instrument_id}-{timeframe}-{stable_hash(quality)[:16]}.json"
            )
            write_json_atomic(
                quarantine,
                {
                    "instrumentId": instrument_id,
                    "timeframe": timeframe,
                    "quality": quality,
                    "baseAudit": audit.to_dict(),
                },
            )
            raise RuntimeError(
                f"okx_official_v1_partition_failed_quality:{instrument_id}:{timeframe}"
            )
        frame_digest = hashlib.sha256(
            pd.util.hash_pandas_object(combined, index=False).values.tobytes()
        ).hexdigest()
        output = (
            self.layout.canonicalRoot
            / "swap"
            / "ohlcv"
            / instrument_id
            / timeframe
            / f"{int(combined['timestamp_ms'].min())}-{int(combined['timestamp_ms'].max())}-{frame_digest[:16]}.parquet"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        if not output.is_file():
            combined.to_parquet(output, index=False, compression="zstd")
        digest = sha256_file(output)
        manifest = {
            "schemaVersion": "okx_official_v1_partition_manifest_v1",
            "instrumentId": instrument_id,
            "timeframe": timeframe,
            "okxBar": OKX_BAR_VALUES[timeframe],
            "sourceEndpoint": OKX_HISTORY_ENDPOINT,
            "confirmedOnly": True,
            "availableAtRule": "timestamp_ms_plus_bar_duration",
            "ingestedAt": ingested_at,
            "baseClassification": audit.classification,
            "baseOutputPath": audit.outputPath,
            "baseOutputSha256": audit.outputSha256,
            "incompatibleExistingCount": audit.incompatibleExistingCount,
            "requestCount": request_count,
            "downloadedRows": len(incremental),
            "rawRowsPath": raw_path,
            "normalizedIncrementPath": (
                str(normalized_path) if normalized_path is not None else None
            ),
            "rows": len(combined),
            "startTime": quality["startTime"],
            "endTime": quality["endTime"],
            "quality": quality,
            "outputPath": str(output),
            "outputSha256": digest,
        }
        manifest_identity = stable_hash(manifest, prefix="okx_official_v1_manifest")
        manifest_path = self.layout.manifestRoot / (
            f"{instrument_id}-{timeframe}-{manifest_identity[:20]}.json"
        )
        write_json_atomic(manifest_path, manifest)
        checkpoint_path.unlink(missing_ok=True)
        return {**manifest, "manifestPath": str(manifest_path)}

    def run(self) -> dict[str, Any]:
        self.layout.ensure_directories()
        ingested_at = _utc_now()
        metadata = self.client.public_instruments(instrument_type="SWAP")
        selected_metadata = [
            row
            for row in metadata
            if str(row.get("instId") or "") in set(self.instruments)
        ]
        selected_ids = {str(row.get("instId") or "") for row in selected_metadata}
        missing_metadata = sorted(set(self.instruments) - selected_ids)
        if missing_metadata:
            raise RuntimeError(
                "okx_instrument_metadata_missing:" + ",".join(missing_metadata)
            )
        metadata_identity = stable_hash(
            selected_metadata,
            prefix="okx_instrument_metadata",
        )
        metadata_path = (
            self.layout.metadataSnapshotRoot
            / f"instruments-{metadata_identity[:20]}.json"
        )
        if not metadata_path.is_file():
            write_json_atomic(
                metadata_path,
                {
                    "schemaVersion": "okx_official_v1_instrument_metadata_v1",
                    "sourceEndpoint": (
                        f"{self.client.base_url}/api/v5/public/instruments"
                    ),
                    "ingestedAt": ingested_at,
                    "instruments": selected_metadata,
                },
            )
        partitions = [
            self._partition(
                instrument_id=instrument_id,
                timeframe=timeframe,
                ingested_at=ingested_at,
            )
            for instrument_id in self.instruments
            for timeframe in self.timeframes
        ]
        audits = [
            {
                "instrumentId": row["instrumentId"],
                "timeframe": row["timeframe"],
                "classification": row["baseClassification"],
                "incompatibleExistingCount": row["incompatibleExistingCount"],
                "quality": row["quality"],
            }
            for row in partitions
        ]
        data_audit_path = self.layout.auditRoot / "data_audit.json"
        write_json_atomic(
            data_audit_path,
            {
                "schemaVersion": "okx_official_v1_data_audit_v1",
                "generatedAt": _utc_now(),
                "partitions": audits,
            },
        )
        data_manifest_path = self.layout.auditRoot / "data_manifest.json"
        write_json_atomic(
            data_manifest_path,
            {
                "schemaVersion": "okx_official_v1_data_manifest_v1",
                "generatedAt": _utc_now(),
                "instrumentMetadataPath": str(metadata_path),
                "partitions": partitions,
            },
        )
        write_json_atomic(
            self.layout.auditRoot / "existing_catalog_summary.json",
            {
                "schemaVersion": "okx_official_v1_existing_catalog_summary_v1",
                "verifiedExistingOkx": sum(
                    row["baseClassification"] == "verified_existing_okx"
                    for row in partitions
                ),
                "verifiedOkxOfficialV1": sum(
                    row["baseClassification"] == "verified_okx_official_v1"
                    for row in partitions
                ),
                "missingOfficialPartition": sum(
                    row["baseClassification"] == "missing_official_partition"
                    for row in partitions
                ),
                "incompatibleExistingCount": sum(
                    int(row["incompatibleExistingCount"]) for row in partitions
                ),
                "downloadPolicy": "reuse_verified_then_download_missing_only",
            },
        )
        gap_matrix = [
            {
                "instrumentId": row["instrumentId"],
                "timeframe": row["timeframe"],
                "gapEventCount": row["quality"]["gapEventCount"],
                "missingBarCount": row["quality"]["missingBarCount"],
            }
            for row in partitions
        ]
        write_json_atomic(self.layout.auditRoot / "gap_matrix.json", gap_matrix)
        gap_matrix_path = self.layout.auditRoot / "okx_data_gap_matrix.csv"
        pd.DataFrame(gap_matrix).to_csv(gap_matrix_path, index=False)
        provenance_matrix = [
            {
                "instrumentId": row["instrumentId"],
                "timeframe": row["timeframe"],
                "sourceEndpoint": row["sourceEndpoint"],
                "baseClassification": row["baseClassification"],
                "outputSha256": row["outputSha256"],
            }
            for row in partitions
        ]
        write_json_atomic(
            self.layout.auditRoot / "provenance_matrix.json",
            provenance_matrix,
        )
        provenance_matrix_path = (
            self.layout.auditRoot / "okx_data_provenance_matrix.csv"
        )
        pd.DataFrame(provenance_matrix).to_csv(
            provenance_matrix_path,
            index=False,
        )
        quality_matrix = [
            {
                "instrumentId": row["instrumentId"],
                "timeframe": row["timeframe"],
                **row["quality"],
            }
            for row in partitions
        ]
        write_json_atomic(
            self.layout.auditRoot / "quality_matrix.json",
            quality_matrix,
        )
        quality_matrix_path = self.layout.auditRoot / "okx_data_quality_matrix.csv"
        quality_frame = pd.DataFrame(quality_matrix)
        if "errors" in quality_frame.columns:
            quality_frame["errors"] = quality_frame["errors"].map(
                lambda value: json.dumps(value, ensure_ascii=True, sort_keys=True)
            )
        quality_frame.to_csv(quality_matrix_path, index=False)
        catalog_path = self.layout.auditRoot / "okx_data_catalog.parquet"
        pd.DataFrame(
            [
                {
                    "instrumentId": row["instrumentId"],
                    "timeframe": row["timeframe"],
                    "okxBar": row["okxBar"],
                    "rows": row["rows"],
                    "startTime": row["startTime"],
                    "endTime": row["endTime"],
                    "baseClassification": row["baseClassification"],
                    "downloadedRows": row["downloadedRows"],
                    "requestCount": row["requestCount"],
                    "outputPath": row["outputPath"],
                    "outputSha256": row["outputSha256"],
                }
                for row in partitions
            ]
        ).to_parquet(catalog_path, index=False, compression="zstd")
        request_audit_path = self.layout.auditRoot / "okx_request_audit.json"
        write_json_atomic(
            request_audit_path,
            {
                "schemaVersion": "okx_official_v1_request_audit_v1",
                "generatedAt": _utc_now(),
                "publicOnly": True,
                "requests": list(
                    getattr(self.client, "request_audit_records", [])
                ),
            },
        )
        write_json_atomic(
            self.layout.auditRoot / "family_eligibility.json",
            {
                "schemaVersion": "okx_official_v1_family_eligibility_v1",
                "status": "data_ready",
                "eligibleFamilies": [],
                "note": "V34A validates data only; no strategy family is admitted here.",
            },
        )
        write_json_atomic(
            self.layout.auditRoot / "data_readiness.json",
            {
                "schemaVersion": "okx_official_v1_data_readiness_v1",
                "status": "data_ready",
                "requiredPartitionCount": len(self.instruments)
                * len(self.timeframes),
                "validPartitionCount": sum(
                    row["quality"]["status"] == "valid" for row in partitions
                ),
                "candidateGenerationAllowedByThisStage": False,
                "formalRunAllowedByThisStage": False,
            },
        )
        write_json_atomic(
            self.layout.auditRoot / "api_capability_audit.json",
            {
                "schemaVersion": "okx_official_v1_api_capability_audit_v1",
                "publicOnly": True,
                "credentialsRequired": False,
                "endpoints": [
                    {
                        "method": "GET",
                        "path": "/api/v5/public/instruments",
                        "purpose": "instrument_metadata_snapshot",
                    },
                    {
                        "method": "GET",
                        "path": "/api/v5/market/history-candles",
                        "purpose": "confirmed_ohlcv_history",
                    },
                ],
                "tradeApiUsed": False,
                "withdrawApiUsed": False,
                "privateAccountReadUsed": False,
            },
        )
        snapshot_id = stable_hash(
            {
                "schemaVersion": "okx_official_v1_snapshot_v1",
                "metadataIdentity": metadata_identity,
                "partitionSha256": sorted(row["outputSha256"] for row in partitions),
            },
            prefix="okx_official_v1_snapshot",
        )
        snapshot_path = self.layout.manifestRoot / f"snapshot-{snapshot_id}.json"
        if not snapshot_path.is_file():
            write_json_atomic(
                snapshot_path,
                {
                    "schemaVersion": "okx_official_v1_snapshot_v1",
                    "snapshotId": snapshot_id,
                    "generatedAt": _utc_now(),
                    "status": "immutable_data_snapshot",
                    "instrumentMetadataPath": str(metadata_path),
                    "partitions": [
                        {
                            "instrumentId": row["instrumentId"],
                            "timeframe": row["timeframe"],
                            "outputPath": row["outputPath"],
                            "outputSha256": row["outputSha256"],
                        }
                        for row in partitions
                    ],
                },
            )
        result = {
            "schemaVersion": "okx_official_v1_pilot_result_v1",
            "status": "completed",
            "scope": "v34a_data_only",
            "partitionCount": len(partitions),
            "reusedPartitionCount": sum(
                row["baseClassification"]
                in {"verified_existing_okx", "verified_okx_official_v1"}
                for row in partitions
            ),
            "downloadedRowCount": sum(int(row["downloadedRows"]) for row in partitions),
            "candidateCount": 0,
            "formalRunCount": 0,
            "demoReleaseCount": 0,
            "orderCount": 0,
            "dataAuditPath": str(data_audit_path),
            "dataManifestPath": str(data_manifest_path),
            "snapshotManifestPath": str(snapshot_path),
            "catalogPath": str(catalog_path),
            "gapMatrixPath": str(gap_matrix_path),
            "provenanceMatrixPath": str(provenance_matrix_path),
            "qualityMatrixPath": str(quality_matrix_path),
            "requestAuditPath": str(request_audit_path),
            "snapshotId": snapshot_id,
            "partitions": partitions,
        }
        write_json_atomic(self.layout.auditRoot / "pilot_result.json", result)
        return result
