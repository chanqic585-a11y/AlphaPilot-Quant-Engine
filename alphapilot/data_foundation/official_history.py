"""Resumable official OKX public history collection for formal research."""

from __future__ import annotations

import math
import os
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.workflow.types import StrategyDataContractRecord

from .catalog import discover_raw_assets
from .checkpoint import load_json, pause_requested, write_json_atomic
from .okx_public import OKX_GLOBAL_API, TIMEFRAME_MILLISECONDS, OkxPublicClient
from .warehouse import WarehouseLayout, ensure_capacity


OFFICIAL_COLLECTION_SCHEMA_VERSION = "okx_official_history_collection_v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _timestamp_ms(value: str) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


@dataclass(frozen=True)
class OfficialPartition:
    instrumentId: str
    timeframe: str
    status: str
    rows: int
    startTime: str | None
    endTime: str | None
    outputPath: str | None
    outputSha256: str | None
    sourceEndpoint: str
    requestCount: int
    provenanceStatus: str
    reused: bool = False
    error: str | None = None


@dataclass(frozen=True)
class OfficialCollectionResult:
    status: str
    strategyDataContractId: str
    instrumentCount: int
    completedPartitionCount: int
    reusedPartitionCount: int
    failedPartitionCount: int
    fundingFileCount: int
    partitions: tuple[OfficialPartition, ...]
    checkpointPath: str
    generatedAt: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["partitions"] = [asdict(item) for item in self.partitions]
        return value


class OkxOfficialHistoryCollector:
    def __init__(
        self,
        *,
        client: OkxPublicClient,
        layout: WarehouseLayout,
        pause_file: Path | None = None,
        capacity_guard: Callable[[WarehouseLayout, int], None] = ensure_capacity,
    ) -> None:
        self.client = client
        self.layout = layout
        self.pause_file = pause_file or layout.checkpointRoot / "PAUSE_REQUESTED"
        self.capacity_guard = capacity_guard

    def _candidate_instruments(self, contract: dict[str, Any]) -> list[str]:
        official_rows = self.client.public_instruments(instrument_type="SWAP")
        official = {
            str(item.get("instId") or "").upper()
            for item in official_rows
            if str(item.get("settleCcy") or "").upper() == "USDT"
            and str(item.get("state") or "").lower() in {"live", "suspend", "preopen"}
            and str(item.get("instId") or "").upper().endswith("-USDT-SWAP")
        }
        local = {
            str(asset.instrumentId).upper()
            for asset in discover_raw_assets(self.layout.rawRoot)
            if asset.instrumentId
            and asset.marketType == "swap"
            and str(asset.instrumentId).upper().endswith("-USDT-SWAP")
        }
        target = int((contract.get("universePolicy") or {}).get("targetMembers", 50))
        ordered = sorted(official | local)
        preferred = [
            value
            for symbol in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
            for value in ordered
            if value == symbol
        ]
        remaining = [value for value in ordered if value not in preferred]
        return (preferred + remaining)[: max(1, target)]

    @staticmethod
    def _timeframes(contract: dict[str, Any]) -> list[str]:
        return sorted(
            {
                str(value)
                for value in (
                    contract.get("signalTimeframe"),
                    contract.get("executionTimeframe"),
                    contract.get("executionFallbackTimeframe"),
                )
                if value
            },
            key=lambda value: TIMEFRAME_MILLISECONDS[value],
        )

    @staticmethod
    def _validate_frame(frame: pd.DataFrame, timeframe: str) -> str | None:
        required = {
            "timestamp_ms",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "confirmed",
        }
        missing = sorted(required - set(frame.columns))
        if missing:
            return f"missing_columns:{','.join(missing)}"
        if frame.empty:
            return "empty_official_history"
        if (pd.to_numeric(frame["confirmed"], errors="coerce") != 1).any():
            return "unconfirmed_candles_present"
        numeric = frame[["open", "high", "low", "close", "volume"]].apply(
            pd.to_numeric, errors="coerce"
        )
        if numeric.isna().any().any():
            return "non_numeric_ohlcv"
        invalid = (
            (numeric["low"] > numeric["high"])
            | (numeric["open"] < numeric["low"])
            | (numeric["open"] > numeric["high"])
            | (numeric["close"] < numeric["low"])
            | (numeric["close"] > numeric["high"])
            | (numeric["volume"] < 0)
        )
        if invalid.any():
            return "invalid_ohlcv"
        timestamps = pd.to_numeric(frame["timestamp_ms"], errors="coerce")
        if timestamps.isna().any() or timestamps.duplicated().any():
            return "invalid_or_duplicate_timestamps"
        differences = timestamps.sort_values().diff().dropna()
        interval = TIMEFRAME_MILLISECONDS[timeframe]
        if (differences <= 0).any() or (differences % interval != 0).any():
            return "misaligned_timestamps"
        return None

    def _reuse_partition(
        self,
        checkpoint: dict[str, Any],
        key: str,
        endpoint: str,
    ) -> OfficialPartition | None:
        row = (checkpoint.get("completed") or {}).get(key)
        if not isinstance(row, dict):
            return None
        path = Path(str(row.get("outputPath") or ""))
        expected = str(row.get("outputSha256") or "")
        if not path.is_file() or not expected or sha256_file(path) != expected:
            return None
        return OfficialPartition(
            instrumentId=str(row["instrumentId"]),
            timeframe=str(row["timeframe"]),
            status="reused",
            rows=int(row["rows"]),
            startTime=row.get("startTime"),
            endTime=row.get("endTime"),
            outputPath=str(path),
            outputSha256=expected,
            sourceEndpoint=endpoint,
            requestCount=0,
            provenanceStatus="official_okx_public",
            reused=True,
        )

    def _write_partition(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        frame: pd.DataFrame,
        request_count: int,
        endpoint: str,
        collected_at: str,
    ) -> OfficialPartition:
        error = self._validate_frame(frame, timeframe)
        if error:
            quarantine = (
                self.layout.officialRawRoot
                / "quarantine"
                / f"{instrument_id}-{timeframe}-{stable_hash(error)[:12]}.json"
            )
            write_json_atomic(
                quarantine,
                {
                    "instrumentId": instrument_id,
                    "timeframe": timeframe,
                    "sourceEndpoint": endpoint,
                    "error": error,
                    "collectedAt": collected_at,
                },
            )
            return OfficialPartition(
                instrumentId=instrument_id,
                timeframe=timeframe,
                status="quarantined",
                rows=len(frame),
                startTime=None,
                endTime=None,
                outputPath=None,
                outputSha256=None,
                sourceEndpoint=endpoint,
                requestCount=request_count,
                provenanceStatus="official_okx_public",
                error=error,
            )
        ordered = frame.drop_duplicates("timestamp_ms", keep="last").sort_values(
            "timestamp_ms"
        ).reset_index(drop=True)
        ordered = ordered.copy()
        ordered["exchange"] = "okx"
        ordered["market_type"] = "swap"
        ordered["instrument_id"] = instrument_id
        ordered["timeframe"] = timeframe
        ordered["source_endpoint"] = endpoint
        ordered["collected_at"] = collected_at
        self.capacity_guard(self.layout, max(32 * 1024**2, len(ordered) * 160))
        temporary = (
            self.layout.temporaryRoot
            / f"{instrument_id}-{timeframe}-{stable_hash(collected_at)[:12]}.parquet"
        )
        temporary.parent.mkdir(parents=True, exist_ok=True)
        ordered.to_parquet(temporary, index=False, compression="zstd")
        digest = sha256_file(temporary)
        first_ms = int(ordered["timestamp_ms"].min())
        last_ms = int(ordered["timestamp_ms"].max())
        output = (
            self.layout.canonicalRoot
            / "okx"
            / "swap"
            / "ohlcv"
            / instrument_id
            / timeframe
            / f"{first_ms}-{last_ms}-{digest[:16]}.parquet"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        os.replace(temporary, output)
        start_time = pd.Timestamp(first_ms, unit="ms", tz="UTC").isoformat()
        end_time = pd.Timestamp(last_ms, unit="ms", tz="UTC").isoformat()
        write_json_atomic(
            self.layout.officialRawRoot
            / "manifests"
            / f"{instrument_id}-{timeframe}-{digest[:16]}.json",
            {
                "schemaVersion": "okx_official_partition_manifest_v1",
                "instrumentId": instrument_id,
                "timeframe": timeframe,
                "sourceEndpoint": endpoint,
                "requestParameters": {
                    "instId": instrument_id,
                    "bar": timeframe,
                    "confirmedOnly": True,
                },
                "collectedAt": collected_at,
                "rows": len(ordered),
                "startTime": start_time,
                "endTime": end_time,
                "outputPath": str(output),
                "outputSha256": digest,
            },
        )
        return OfficialPartition(
            instrumentId=instrument_id,
            timeframe=timeframe,
            status="collected",
            rows=len(ordered),
            startTime=start_time,
            endTime=end_time,
            outputPath=str(output),
            outputSha256=digest,
            sourceEndpoint=endpoint,
            requestCount=request_count,
            provenanceStatus="official_okx_public",
        )

    def _collect_funding(self, instrument_ids: list[str]) -> int:
        completed = 0
        endpoint = f"{self.client.base_url}/api/v5/public/funding-rate-history"
        for instrument_id in instrument_ids:
            if pause_requested(self.pause_file):
                break
            rows = self.client.funding_rate_history(
                instrument_id=instrument_id, limit=100
            )
            parsed = [
                {
                    "instrument_id": instrument_id,
                    "funding_rate": float(row["fundingRate"]),
                    "timestamp_ms": int(row["fundingTime"]),
                    "source_endpoint": endpoint,
                    "collected_at": _utc_now(),
                }
                for row in rows
                if row.get("fundingRate") not in {None, ""}
                and row.get("fundingTime") not in {None, ""}
            ]
            if not parsed:
                continue
            frame = pd.DataFrame(parsed).sort_values("timestamp_ms")
            digest = stable_hash(parsed, prefix="funding")
            output = (
                self.layout.canonicalRoot
                / "okx"
                / "swap"
                / "funding"
                / instrument_id
                / f"funding-{digest[-16:]}.parquet"
            )
            if not output.is_file():
                self.capacity_guard(self.layout, max(1024**2, len(frame) * 100))
                output.parent.mkdir(parents=True, exist_ok=True)
                frame.to_parquet(output, index=False, compression="zstd")
            completed += 1
        return completed

    def collect(
        self, contract: StrategyDataContractRecord
    ) -> OfficialCollectionResult:
        self.layout.ensure_directories()
        checkpoint_path = (
            self.layout.checkpointRoot
            / f"official-{contract.strategyDataContractId}.json"
        )
        checkpoint = load_json(checkpoint_path)
        checkpoint.setdefault("schemaVersion", OFFICIAL_COLLECTION_SCHEMA_VERSION)
        checkpoint.setdefault("completed", {})
        instruments = self._candidate_instruments(contract.contract)
        timeframes = self._timeframes(contract.contract)
        partitions: list[OfficialPartition] = []
        collected_at = _utc_now()
        endpoint = f"{self.client.base_url}/api/v5/market/history-candles"
        start_ms = _timestamp_ms(str(contract.contract["requestedStart"])) - 1
        paused = False
        for instrument_id in instruments:
            for timeframe in timeframes:
                if pause_requested(self.pause_file):
                    paused = True
                    break
                key = f"{instrument_id}|{timeframe}"
                reused = self._reuse_partition(checkpoint, key, endpoint)
                if reused is not None:
                    partitions.append(reused)
                    continue
                interval = TIMEFRAME_MILLISECONDS[timeframe]
                elapsed_ms = max(0, int(datetime.now(UTC).timestamp() * 1000) - start_ms)
                max_pages = min(10_000, max(1, math.ceil(elapsed_ms / interval / 100) + 2))
                try:
                    frame, request_count = self.client.history_candles(
                        instrument_id=instrument_id,
                        timeframe=timeframe,
                        start_exclusive_ms=start_ms,
                        max_pages=max_pages,
                    )
                    partition = self._write_partition(
                        instrument_id=instrument_id,
                        timeframe=timeframe,
                        frame=frame,
                        request_count=request_count,
                        endpoint=endpoint,
                        collected_at=collected_at,
                    )
                except Exception as error:
                    partition = OfficialPartition(
                        instrumentId=instrument_id,
                        timeframe=timeframe,
                        status="failed",
                        rows=0,
                        startTime=None,
                        endTime=None,
                        outputPath=None,
                        outputSha256=None,
                        sourceEndpoint=endpoint,
                        requestCount=0,
                        provenanceStatus="official_okx_public",
                        error=f"{type(error).__name__}:{error}",
                    )
                partitions.append(partition)
                if partition.outputPath and partition.outputSha256:
                    checkpoint["completed"][key] = asdict(partition)
                    write_json_atomic(checkpoint_path, checkpoint)
            if paused:
                break
        funding_count = 0 if paused else self._collect_funding(instruments)
        completed = sum(
            1 for item in partitions if item.status in {"collected", "reused"}
        )
        reused_count = sum(1 for item in partitions if item.reused)
        failed = len(partitions) - completed
        required = int(
            (contract.contract.get("universePolicy") or {}).get(
                "minimumMembers", 1
            )
        ) * len(timeframes)
        if paused:
            status = "paused"
        elif failed or completed < required:
            status = "blocked"
        else:
            status = "completed"
        result = OfficialCollectionResult(
            status=status,
            strategyDataContractId=contract.strategyDataContractId,
            instrumentCount=len(instruments),
            completedPartitionCount=completed,
            reusedPartitionCount=reused_count,
            failedPartitionCount=failed,
            fundingFileCount=funding_count,
            partitions=tuple(partitions),
            checkpointPath=str(checkpoint_path),
            generatedAt=_utc_now(),
        )
        write_json_atomic(
            self.layout.reportRoot
            / f"official-{contract.strategyDataContractId}.json",
            result.to_dict(),
        )
        return result


def default_official_history_collector(
    layout: WarehouseLayout,
) -> OkxOfficialHistoryCollector:
    return OkxOfficialHistoryCollector(
        client=OkxPublicClient(base_url=OKX_GLOBAL_API),
        layout=layout,
    )
