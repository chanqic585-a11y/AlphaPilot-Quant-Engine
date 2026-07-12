"""OKX public-only incremental OHLCV collection for V13.16."""

from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash


OKX_GLOBAL_API = "https://openapi.okx.com"
BAR_VALUES = {"5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H", "1d": "1D"}
TIMEFRAME_MILLISECONDS = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}
CANONICAL_SOURCE_NAMES = ("unknown", "okx")


class OkxHistoryCollectionStopped(RuntimeError):
    """Raised when a caller requests a clean stop between history pages."""


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class PublicIncrement:
    instrumentId: str
    timeframe: str
    startExclusiveMs: int
    rows: int
    startTime: str | None
    endTime: str | None
    requestCount: int
    outputPath: str | None
    outputSha256: str | None
    status: str
    sourceEndpoint: str
    expectedNextMs: int | None = None
    firstTimestampMs: int | None = None
    continuityStatus: str | None = None
    gapBars: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "instrumentId": self.instrumentId,
            "timeframe": self.timeframe,
            "startExclusiveMs": self.startExclusiveMs,
            "rows": self.rows,
            "startTime": self.startTime,
            "endTime": self.endTime,
            "requestCount": self.requestCount,
            "outputPath": self.outputPath,
            "outputSha256": self.outputSha256,
            "status": self.status,
            "sourceEndpoint": self.sourceEndpoint,
            "expectedNextMs": self.expectedNextMs,
            "firstTimestampMs": self.firstTimestampMs,
            "continuityStatus": self.continuityStatus,
            "gapBars": self.gapBars,
            "error": self.error,
        }


class OkxPublicClient:
    def __init__(
        self,
        *,
        base_url: str = OKX_GLOBAL_API,
        opener: Callable[..., Any] = urllib.request.urlopen,
        throttle_seconds: float = 0.12,
        max_rate_limit_retries: int = 3,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.opener = opener
        self.throttle_seconds = max(0.0, throttle_seconds)
        self.max_rate_limit_retries = max(0, int(max_rate_limit_retries))

    def _get(self, path: str, parameters: dict[str, Any]) -> list[Any]:
        query = urllib.parse.urlencode(parameters)
        request = urllib.request.Request(
            f"{self.base_url}{path}?{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": "AlphaPilot-Quant-Engine/13.16",
            },
            method="GET",
        )
        payload: dict[str, Any] = {}
        for attempt in range(self.max_rate_limit_retries + 1):
            with self.opener(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            code = str(payload.get("code"))
            if code == "0":
                break
            if code != "50011" or attempt >= self.max_rate_limit_retries:
                raise RuntimeError(
                    f"OKX public request failed: {code} {payload.get('msg')}"
                )
            time.sleep(max(self.throttle_seconds, 0.25) * (2**attempt))
        data = payload.get("data")
        if not isinstance(data, list):
            raise RuntimeError("OKX public response data is not an array")
        return data

    def public_instruments(
        self, *, instrument_type: str = "SWAP"
    ) -> list[dict[str, Any]]:
        return [
            dict(item)
            for item in self._get(
                "/api/v5/public/instruments",
                {"instType": instrument_type},
            )
            if isinstance(item, dict)
        ]

    def funding_rate_history(
        self,
        *,
        instrument_id: str,
        before_ms: int | None = None,
        after_ms: int | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        parameters: dict[str, Any] = {
            "instId": instrument_id,
            "limit": max(1, min(int(limit), 100)),
        }
        if before_ms is not None:
            parameters["before"] = int(before_ms)
        if after_ms is not None:
            parameters["after"] = int(after_ms)
        return [
            dict(item)
            for item in self._get(
                "/api/v5/public/funding-rate-history", parameters
            )
            if isinstance(item, dict)
        ]

    def history_candle_page(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        after_ms: int | None,
        limit: int = 100,
    ) -> list[list[Any]]:
        if timeframe not in BAR_VALUES:
            raise ValueError(f"Unsupported OKX timeframe: {timeframe}")
        parameters: dict[str, Any] = {
            "instId": instrument_id,
            "bar": BAR_VALUES[timeframe],
            "limit": max(1, min(int(limit), 100)),
        }
        if after_ms is not None:
            parameters["after"] = int(after_ms)
        return [
            list(item)
            for item in self._get("/api/v5/market/history-candles", parameters)
            if isinstance(item, list)
        ]

    def history_candles(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        start_exclusive_ms: int,
        max_pages: int = 500,
        page_limit: int = 100,
        stop_requested: Callable[[], bool] | None = None,
        page_progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[pd.DataFrame, int]:
        if timeframe not in BAR_VALUES:
            raise ValueError(f"Unsupported OKX timeframe: {timeframe}")
        if start_exclusive_ms < 0:
            raise ValueError("start_exclusive_ms must be non-negative")
        cursor: int | None = None
        request_count = 0
        rows: list[list[Any]] = []
        seen_cursors: set[int] = set()
        for _ in range(max_pages):
            if stop_requested is not None and stop_requested():
                raise OkxHistoryCollectionStopped("official_history_collection_stopped")
            parameters: dict[str, Any] = {
                "instId": instrument_id,
                "bar": BAR_VALUES[timeframe],
                "limit": max(1, min(page_limit, 100)),
            }
            if cursor is not None:
                parameters["after"] = cursor
            data = self._get("/api/v5/market/history-candles", parameters)
            request_count += 1
            if not data:
                if page_progress is not None:
                    page_progress({
                        "requestCount": request_count,
                        "rowCount": len(rows),
                        "oldestTimestampMs": None,
                        "maxPages": max_pages,
                        "isFinalPage": True,
                    })
                break
            parsed_timestamps = [int(item[0]) for item in data if isinstance(item, list) and item]
            if not parsed_timestamps:
                if page_progress is not None:
                    page_progress({
                        "requestCount": request_count,
                        "rowCount": len(rows),
                        "oldestTimestampMs": None,
                        "maxPages": max_pages,
                        "isFinalPage": True,
                    })
                break
            for item in data:
                if not isinstance(item, list) or len(item) < 9:
                    continue
                timestamp = int(item[0])
                if timestamp > start_exclusive_ms and str(item[8]) == "1":
                    rows.append(item)
            oldest = min(parsed_timestamps)
            final_page = (
                oldest <= start_exclusive_ms
                or oldest in seen_cursors
                or request_count >= max_pages
            )
            if page_progress is not None:
                page_progress({
                    "requestCount": request_count,
                    "rowCount": len(rows),
                    "oldestTimestampMs": oldest,
                    "maxPages": max_pages,
                    "isFinalPage": final_page,
                })
            if final_page:
                break
            seen_cursors.add(oldest)
            cursor = oldest
            if self.throttle_seconds:
                time.sleep(self.throttle_seconds)
        if not rows:
            return pd.DataFrame(columns=["timestamp_ms", "date", "open", "high", "low", "close", "volume", "confirmed"]), request_count
        frame = pd.DataFrame(
            {
                "timestamp_ms": [int(item[0]) for item in rows],
                "open": [float(item[1]) for item in rows],
                "high": [float(item[2]) for item in rows],
                "low": [float(item[3]) for item in rows],
                "close": [float(item[4]) for item in rows],
                "volume": [float(item[7]) for item in rows],
                "confirmed": [int(item[8]) for item in rows],
            }
        )
        frame["date"] = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True)
        frame = frame.drop_duplicates(subset=["timestamp_ms"], keep="last").sort_values("timestamp_ms").reset_index(drop=True)
        return frame[["timestamp_ms", "date", "open", "high", "low", "close", "volume", "confirmed"]], request_count

    def latest_completed_candles(
        self,
        *,
        instrument_id: str,
        timeframe: str,
        limit: int = 300,
    ) -> pd.DataFrame:
        """Return only exchange-confirmed public candles for forward observation."""

        if timeframe not in BAR_VALUES:
            raise ValueError(f"Unsupported OKX timeframe: {timeframe}")
        data = self._get(
            "/api/v5/market/candles",
            {
                "instId": instrument_id,
                "bar": BAR_VALUES[timeframe],
                "limit": max(1, min(int(limit), 300)),
            },
        )
        rows = [item for item in data if isinstance(item, list) and len(item) >= 9 and str(item[8]) == "1"]
        if not rows:
            return pd.DataFrame(
                columns=["timestamp_ms", "date", "open", "high", "low", "close", "volume", "confirmed"]
            )
        frame = pd.DataFrame(
            {
                "timestamp_ms": [int(item[0]) for item in rows],
                "open": [float(item[1]) for item in rows],
                "high": [float(item[2]) for item in rows],
                "low": [float(item[3]) for item in rows],
                "close": [float(item[4]) for item in rows],
                "volume": [float(item[7]) for item in rows],
                "confirmed": [int(item[8]) for item in rows],
            }
        )
        frame["date"] = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True)
        frame = frame.drop_duplicates("timestamp_ms", keep="last").sort_values("timestamp_ms")
        return frame.reset_index(drop=True)[
            ["timestamp_ms", "date", "open", "high", "low", "close", "volume", "confirmed"]
        ]


def latest_canonical_timestamp(
    canonical_root: Path | str,
    *,
    market_type: str,
    instrument_id: str,
    timeframe: str,
) -> int | None:
    root = Path(canonical_root)
    candidates = [
        path
        for source_name in CANONICAL_SOURCE_NAMES
        for path in (root / source_name / market_type / "ohlcv" / instrument_id / timeframe).glob("*.parquet")
    ]
    latest: int | None = None
    for path in candidates:
        frame = pd.read_parquet(path, columns=["timestamp_ms"])
        if frame.empty:
            continue
        value = int(frame["timestamp_ms"].max())
        latest = value if latest is None else max(latest, value)
    return latest


def collect_public_increment(
    *,
    client: OkxPublicClient,
    canonical_root: Path | str,
    instrument_id: str,
    timeframe: str,
    market_type: str = "swap",
    start_exclusive_ms: int | None = None,
) -> PublicIncrement:
    if timeframe not in BAR_VALUES:
        raise ValueError(f"Unsupported OKX timeframe: {timeframe}")
    endpoint = f"{client.base_url}/api/v5/market/history-candles"
    start = start_exclusive_ms
    if start is None:
        start = latest_canonical_timestamp(
            canonical_root,
            market_type=market_type,
            instrument_id=instrument_id,
            timeframe=timeframe,
        )
    if start is None:
        return PublicIncrement(
            instrumentId=instrument_id,
            timeframe=timeframe,
            startExclusiveMs=0,
            rows=0,
            startTime=None,
            endTime=None,
            requestCount=0,
            outputPath=None,
            outputSha256=None,
            status="blocked_missing_local_cutoff",
            sourceEndpoint=endpoint,
            error="No canonical local timestamp was found",
        )
    try:
        frame, request_count = client.history_candles(
            instrument_id=instrument_id,
            timeframe=timeframe,
            start_exclusive_ms=start,
        )
        if frame.empty:
            return PublicIncrement(
                instrumentId=instrument_id,
                timeframe=timeframe,
                startExclusiveMs=start,
                rows=0,
                startTime=None,
                endTime=None,
                requestCount=request_count,
                outputPath=None,
                outputSha256=None,
                status="up_to_date_or_unavailable",
                sourceEndpoint=endpoint,
            )
        frame["exchange"] = "okx"
        frame["market_type"] = market_type
        frame["instrument_id"] = instrument_id
        frame["timeframe"] = timeframe
        frame["source_endpoint"] = endpoint
        frame["collected_at"] = _utc_now()
        interval_ms = TIMEFRAME_MILLISECONDS[timeframe]
        first_timestamp_ms = int(frame["timestamp_ms"].min())
        expected_next_ms = start + interval_ms
        delta_ms = first_timestamp_ms - expected_next_ms
        if delta_ms == 0:
            continuity_status = "contiguous"
            gap_bars = 0
        elif delta_ms > 0 and delta_ms % interval_ms == 0:
            continuity_status = "gap"
            gap_bars = delta_ms // interval_ms
        else:
            continuity_status = "misaligned"
            gap_bars = None
        identity = stable_hash(
            {
                "schemaVersion": "okx_public_increment_v1",
                "instrumentId": instrument_id,
                "timeframe": timeframe,
                "startExclusiveMs": start,
                "first": int(frame["timestamp_ms"].min()),
                "last": int(frame["timestamp_ms"].max()),
                "rows": len(frame),
            }
        )[:16]
        output = (
            Path(canonical_root)
            / "okx"
            / market_type
            / "ohlcv"
            / instrument_id
            / timeframe
            / f"increment-{int(frame['timestamp_ms'].min())}-{int(frame['timestamp_ms'].max())}-{identity}.parquet"
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_name(f"{output.name}.tmp")
        frame.to_parquet(temporary, index=False, compression="zstd")
        os.replace(temporary, output)
        return PublicIncrement(
            instrumentId=instrument_id,
            timeframe=timeframe,
            startExclusiveMs=start,
            rows=len(frame),
            startTime=frame["date"].min().isoformat(),
            endTime=frame["date"].max().isoformat(),
            requestCount=request_count,
            outputPath=str(output),
            outputSha256=sha256_file(output),
            status="collected",
            sourceEndpoint=endpoint,
            expectedNextMs=expected_next_ms,
            firstTimestampMs=first_timestamp_ms,
            continuityStatus=continuity_status,
            gapBars=gap_bars,
        )
    except Exception as exc:  # noqa: BLE001 - isolate per-instrument public failures.
        return PublicIncrement(
            instrumentId=instrument_id,
            timeframe=timeframe,
            startExclusiveMs=start,
            rows=0,
            startTime=None,
            endTime=None,
            requestCount=0,
            outputPath=None,
            outputSha256=None,
            status="failed",
            sourceEndpoint=endpoint,
            error=str(exc),
        )
