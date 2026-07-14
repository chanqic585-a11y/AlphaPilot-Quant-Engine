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
from .okx_public import (
    OKX_GLOBAL_API,
    TIMEFRAME_MILLISECONDS,
    OkxHistoryCollectionStopped,
    OkxPublicClient,
)
from .official_partition_index import OfficialPartitionIndex
from .official_resume import OfficialResumeStore, ResumeIdentity
from .warehouse import WarehouseLayout, ensure_capacity


OFFICIAL_COLLECTION_SCHEMA_VERSION = "okx_official_history_collection_v1"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _timestamp_ms(value: str) -> int:
    return int(pd.Timestamp(value).timestamp() * 1000)


def _frame_from_okx_rows(rows: list[list[Any]]) -> pd.DataFrame:
    accepted = [item for item in rows if isinstance(item, list) and len(item) >= 9]
    if not accepted:
        return pd.DataFrame(
            columns=[
                "timestamp_ms",
                "date",
                "open",
                "high",
                "low",
                "close",
                "volume",
                "confirmed",
            ]
        )
    frame = pd.DataFrame(
        {
            "timestamp_ms": [int(item[0]) for item in accepted],
            "open": [float(item[1]) for item in accepted],
            "high": [float(item[2]) for item in accepted],
            "low": [float(item[3]) for item in accepted],
            "close": [float(item[4]) for item in accepted],
            "volume": [float(item[7]) for item in accepted],
            "confirmed": [int(item[8]) for item in accepted],
        }
    )
    frame["date"] = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True)
    return frame[
        [
            "timestamp_ms",
            "date",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "confirmed",
        ]
    ]


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
    fundingPaths: tuple[str, ...] = ()

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
        stop_requested: Callable[[], bool] | None = None,
        capacity_guard: Callable[[WarehouseLayout, int], None] = ensure_capacity,
    ) -> None:
        self.client = client
        self.layout = layout
        self.pause_file = pause_file or layout.checkpointRoot / "PAUSE_REQUESTED"
        self.stop_requested = stop_requested
        self.capacity_guard = capacity_guard

    def _should_stop(self) -> bool:
        return pause_requested(self.pause_file) or bool(
            self.stop_requested is not None and self.stop_requested()
        )

    def _candidate_instruments(self, contract: dict[str, Any]) -> list[str]:
        official_rows = self.client.public_instruments(instrument_type="SWAP")
        official = {
            str(item.get("instId") or "").upper()
            for item in official_rows
            if str(item.get("settleCcy") or "").upper() == "USDT"
            and str(item.get("state") or "").lower() in {"live", "suspend", "preopen"}
            and str(item.get("instCategory") or "1") == "1"
            and str(item.get("instId") or "").upper().endswith("-USDT-SWAP")
        }
        target = int((contract.get("universePolicy") or {}).get("targetMembers", 50))
        target = max(1, target)
        ticker_loader = getattr(self.client, "public_tickers", None)
        ranked: list[str] = []
        if callable(ticker_loader):
            scores: dict[str, float] = {}
            ticker_rows = ticker_loader(instrument_type="SWAP")
            for item in ticker_rows:
                instrument_id = str(item.get("instId") or "").upper()
                if instrument_id not in official:
                    continue
                try:
                    last = float(item.get("last") or 0.0)
                    base_volume = float(item.get("volCcy24h") or 0.0)
                    quote_notional = last * base_volume
                except (TypeError, ValueError, OverflowError):
                    continue
                if (
                    math.isfinite(quote_notional)
                    and last > 0.0
                    and base_volume > 0.0
                    and quote_notional > 0.0
                ):
                    scores[instrument_id] = quote_notional
            ranked = sorted(scores, key=lambda value: (-scores[value], value))
            if not ranked:
                raise RuntimeError("okx_public_ticker_ranking_unavailable")

        # Legacy test clients may not expose tickers. Production clients do, and
        # therefore fail closed instead of silently reverting to alphabetical Top N.
        ordered_official = ranked + sorted(official - set(ranked))
        if len(ordered_official) >= target or not self.layout.rawRoot.exists():
            return ordered_official[:target]

        local = {
            str(asset.instrumentId).upper()
            for asset in discover_raw_assets(self.layout.rawRoot)
            if asset.instrumentId
            and asset.marketType == "swap"
            and str(asset.instrumentId).upper().endswith("-USDT-SWAP")
        }
        local_fallback = sorted(local - set(ordered_official))
        return (ordered_official + local_fallback)[:target]

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

    def _shared_partition_base(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        endpoint: str,
        partition_index: OfficialPartitionIndex,
    ) -> OfficialPartition | None:
        candidate = partition_index.latest_valid(
            instrument_id,
            timeframe,
            endpoint,
        )
        if candidate is None:
            return None
        return OfficialPartition(
            instrumentId=candidate.instrumentId,
            timeframe=candidate.timeframe,
            status="reused",
            rows=candidate.rows,
            startTime=candidate.startTime,
            endTime=candidate.endTime,
            outputPath=candidate.outputPath,
            outputSha256=candidate.outputSha256,
            sourceEndpoint=candidate.sourceEndpoint,
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

    def _collect_funding(
        self, instrument_ids: list[str], *, start_ms: int
    ) -> tuple[str, ...]:
        completed: list[str] = []
        endpoint = f"{self.client.base_url}/api/v5/public/funding-rate-history"
        for instrument_id in instrument_ids:
            if self._should_stop():
                break
            rows: list[dict[str, Any]] = []
            cursor: int | None = None
            seen_cursors: set[int] = set()
            for _ in range(1_000):
                if self._should_stop():
                    break
                page = self.client.funding_rate_history(
                    instrument_id=instrument_id,
                    after_ms=cursor,
                    limit=100,
                )
                if not page:
                    break
                rows.extend(page)
                timestamps = [
                    int(row["fundingTime"])
                    for row in page
                    if row.get("fundingTime") not in {None, ""}
                ]
                if not timestamps:
                    break
                oldest = min(timestamps)
                if oldest <= start_ms or oldest in seen_cursors:
                    break
                seen_cursors.add(oldest)
                cursor = oldest
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
                and int(row["fundingTime"]) >= start_ms
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
            completed.append(str(output))
        return tuple(completed)

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
        checkpoint.setdefault("preparationMode", "initial_download")
        instruments = self._candidate_instruments(contract.contract)
        timeframes = self._timeframes(contract.contract)
        partition_index = OfficialPartitionIndex.from_manifests(
            self.layout.officialRawRoot / "manifests",
            self.layout.canonicalRoot,
        )
        resume_store = OfficialResumeStore(
            self.layout.temporaryRoot / "official-resume"
        )
        partitions: list[OfficialPartition] = []
        collected_at = _utc_now()
        endpoint = f"{self.client.base_url}/api/v5/market/history-candles"
        start_ms = _timestamp_ms(str(contract.contract["requestedStart"])) - 1
        paused = False
        for instrument_id in instruments:
            for timeframe in timeframes:
                if self._should_stop():
                    paused = True
                    break
                key = f"{instrument_id}|{timeframe}"
                reused = self._reuse_partition(checkpoint, key, endpoint)
                if reused is not None:
                    checkpoint["preparationMode"] = "contract_checkpoint_reuse"
                    active = checkpoint.get("inProgress")
                    if isinstance(active, dict) and active.get("key") == key:
                        checkpoint.pop("inProgress", None)
                    write_json_atomic(checkpoint_path, checkpoint)
                    partitions.append(reused)
                    continue
                shared_base = self._shared_partition_base(
                    instrument_id=instrument_id,
                    timeframe=timeframe,
                    endpoint=endpoint,
                    partition_index=partition_index,
                )
                collection_start_ms = start_ms
                if shared_base is not None and shared_base.endTime:
                    collection_start_ms = max(
                        start_ms,
                        _timestamp_ms(shared_base.endTime),
                    )
                preparation_mode = (
                    "shared_incremental_refresh"
                    if shared_base is not None
                    else "initial_download"
                )
                checkpoint["preparationMode"] = preparation_mode
                base_rows = shared_base.rows if shared_base is not None else 0
                base_end_time = (
                    shared_base.endTime if shared_base is not None else None
                )
                interval = TIMEFRAME_MILLISECONDS[timeframe]
                elapsed_ms = max(
                    0,
                    int(datetime.now(UTC).timestamp() * 1000) - collection_start_ms,
                )
                max_pages = min(
                    10_000,
                    max(1, math.ceil(elapsed_ms / interval / 100) + 2),
                )
                resume_identity = ResumeIdentity(
                    strategyDataContractId=contract.strategyDataContractId,
                    key=key,
                    instrumentId=instrument_id,
                    timeframe=timeframe,
                    sourceEndpoint=endpoint,
                    collectionStartMs=collection_start_ms,
                    baseSha256=(
                        shared_base.outputSha256 if shared_base is not None else None
                    ),
                )
                resume = resume_store.load(resume_identity)
                pending_page_rows: list[list[Any]] = []
                latest_total_request_count = resume.requestCount
                latest_oldest_timestamp_ms = resume.oldestTimestampMs
                resume_chunk_count = resume.chunkCount

                def flush_resume_rows() -> None:
                    nonlocal resume_chunk_count
                    if not pending_page_rows:
                        return
                    saved = resume_store.append(
                        resume_identity,
                        _frame_from_okx_rows(pending_page_rows),
                        request_count=latest_total_request_count,
                        oldest_timestamp_ms=latest_oldest_timestamp_ms,
                    )
                    pending_page_rows.clear()
                    resume_chunk_count = saved.chunkCount

                def persist_page_progress(progress: dict[str, Any]) -> None:
                    nonlocal latest_total_request_count, latest_oldest_timestamp_ms
                    request_count = int(progress.get("requestCount") or 0)
                    latest_total_request_count = resume.requestCount + request_count
                    current_oldest = progress.get("oldestTimestampMs")
                    if current_oldest is not None:
                        latest_oldest_timestamp_ms = min(
                            int(current_oldest),
                            latest_oldest_timestamp_ms
                            if latest_oldest_timestamp_ms is not None
                            else int(current_oldest),
                        )
                    page_rows = progress.get("pageRows")
                    if isinstance(page_rows, list):
                        pending_page_rows.extend(
                            item
                            for item in page_rows
                            if isinstance(item, list) and len(item) >= 9
                        )
                    final_page = bool(progress.get("isFinalPage"))
                    if request_count % 25 == 0 or final_page:
                        flush_resume_rows()
                    if request_count != 1 and request_count % 25 != 0 and not final_page:
                        return
                    checkpoint["inProgress"] = {
                        "key": key,
                        "instrumentId": instrument_id,
                        "timeframe": timeframe,
                        "requestCount": latest_total_request_count,
                        "rowCount": len(resume.frame)
                        + int(progress.get("rowCount") or 0),
                        "oldestTimestampMs": latest_oldest_timestamp_ms,
                        "maxPages": int(progress.get("maxPages") or max_pages),
                        "updatedAt": _utc_now(),
                        "mode": (
                            "resuming_partial_download"
                            if resume.chunkCount
                            else preparation_mode
                        ),
                        "baseRows": base_rows,
                        "baseEndTime": base_end_time,
                        "resumeChunkCount": resume_chunk_count,
                    }
                    write_json_atomic(checkpoint_path, checkpoint)

                try:
                    frame, request_count = self.client.history_candles(
                        instrument_id=instrument_id,
                        timeframe=timeframe,
                        start_exclusive_ms=collection_start_ms,
                        max_pages=max(1, max_pages - resume.requestCount),
                        initial_after_ms=resume.oldestTimestampMs,
                        stop_requested=self._should_stop,
                        page_progress=persist_page_progress,
                    )
                    latest_total_request_count = resume.requestCount + request_count
                    flush_resume_rows()
                    incremental_frames = [
                        item for item in (resume.frame, frame) if not item.empty
                    ]
                    incremental = (
                        pd.concat(incremental_frames, ignore_index=True)
                        if incremental_frames
                        else frame
                    )
                    if shared_base is not None and incremental.empty:
                        partition = shared_base
                    else:
                        if shared_base is not None and shared_base.outputPath:
                            columns = [
                                "timestamp_ms",
                                "date",
                                "open",
                                "high",
                                "low",
                                "close",
                                "volume",
                                "confirmed",
                            ]
                            base_frame = pd.read_parquet(shared_base.outputPath)[columns]
                            incremental = pd.concat(
                                [base_frame, incremental], ignore_index=True
                            )
                        partition = self._write_partition(
                            instrument_id=instrument_id,
                            timeframe=timeframe,
                            frame=incremental,
                            request_count=latest_total_request_count,
                            endpoint=endpoint,
                            collected_at=collected_at,
                        )
                except OkxHistoryCollectionStopped:
                    flush_resume_rows()
                    if isinstance(checkpoint.get("inProgress"), dict):
                        checkpoint["inProgress"]["mode"] = (
                            "resuming_partial_download"
                        )
                        checkpoint["inProgress"]["resumeChunkCount"] = (
                            resume_chunk_count
                        )
                        write_json_atomic(checkpoint_path, checkpoint)
                    paused = True
                    break
                except Exception as error:
                    flush_resume_rows()
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
                checkpoint.pop("inProgress", None)
                if partition.outputPath and partition.outputSha256:
                    checkpoint["completed"][key] = asdict(partition)
                    resume_store.clear(resume_identity)
                write_json_atomic(checkpoint_path, checkpoint)
            if paused:
                break
        funding_paths = (
            ()
            if paused
            else self._collect_funding(instruments, start_ms=start_ms + 1)
        )
        if self._should_stop():
            paused = True
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
        if status == "completed":
            checkpoint["preparationMode"] = "shared_cache_ready"
            checkpoint.pop("inProgress", None)
            write_json_atomic(checkpoint_path, checkpoint)
        result = OfficialCollectionResult(
            status=status,
            strategyDataContractId=contract.strategyDataContractId,
            instrumentCount=len(instruments),
            completedPartitionCount=completed,
            reusedPartitionCount=reused_count,
            failedPartitionCount=failed,
            fundingFileCount=len(funding_paths),
            partitions=tuple(partitions),
            checkpointPath=str(checkpoint_path),
            generatedAt=_utc_now(),
            fundingPaths=funding_paths,
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
