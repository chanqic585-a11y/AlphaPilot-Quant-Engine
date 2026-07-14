"""Durable temporary chunks for resumable OKX official history downloads."""

from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .checkpoint import load_json, write_json_atomic


RESUME_SCHEMA_VERSION = "okx_official_resume_v1"
OHLCV_COLUMNS = (
    "timestamp_ms",
    "date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "confirmed",
)


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=list(OHLCV_COLUMNS))


@dataclass(frozen=True)
class ResumeIdentity:
    strategyDataContractId: str
    key: str
    instrumentId: str
    timeframe: str
    sourceEndpoint: str
    collectionStartMs: int
    baseSha256: str | None


@dataclass(frozen=True)
class ResumeSnapshot:
    frame: pd.DataFrame
    requestCount: int
    oldestTimestampMs: int | None
    chunkCount: int


class OfficialResumeStore:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _partition_root(self, identity: ResumeIdentity) -> Path:
        return self.root / stable_hash(identity, prefix="resume")

    @staticmethod
    def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
        if frame.empty:
            return _empty_frame()
        missing = set(OHLCV_COLUMNS) - set(frame.columns)
        if missing:
            raise ValueError(f"resume_frame_missing_columns:{','.join(sorted(missing))}")
        normalized = frame[list(OHLCV_COLUMNS)].copy()
        normalized["timestamp_ms"] = pd.to_numeric(
            normalized["timestamp_ms"], errors="raise"
        ).astype("int64")
        normalized["confirmed"] = pd.to_numeric(
            normalized["confirmed"], errors="raise"
        ).astype("int64")
        if (normalized["confirmed"] != 1).any():
            raise ValueError("resume_frame_contains_unconfirmed_candles")
        normalized["date"] = pd.to_datetime(
            normalized["timestamp_ms"], unit="ms", utc=True
        )
        return (
            normalized.drop_duplicates("timestamp_ms", keep="last")
            .sort_values("timestamp_ms")
            .reset_index(drop=True)
        )

    @staticmethod
    def _empty_snapshot() -> ResumeSnapshot:
        return ResumeSnapshot(
            frame=_empty_frame(),
            requestCount=0,
            oldestTimestampMs=None,
            chunkCount=0,
        )

    def _invalidate(self, partition_root: Path) -> None:
        if not partition_root.exists():
            return
        invalid = partition_root.with_name(f"{partition_root.name}.invalid")
        if invalid.exists():
            shutil.rmtree(invalid)
        os.replace(partition_root, invalid)

    def load(self, identity: ResumeIdentity) -> ResumeSnapshot:
        partition_root = self._partition_root(identity)
        state_path = partition_root / "state.json"
        try:
            state = load_json(state_path)
        except (OSError, ValueError):
            self._invalidate(partition_root)
            return self._empty_snapshot()
        if not state:
            return self._empty_snapshot()
        if (
            state.get("schemaVersion") != RESUME_SCHEMA_VERSION
            or state.get("identity") != asdict(identity)
        ):
            self._invalidate(partition_root)
            return self._empty_snapshot()
        chunks = state.get("chunks")
        if not isinstance(chunks, list) or not chunks:
            return self._empty_snapshot()
        frames: list[pd.DataFrame] = []
        try:
            for item in chunks:
                if not isinstance(item, dict):
                    raise ValueError("invalid_resume_chunk_metadata")
                path = partition_root / str(item.get("fileName") or "")
                expected = str(item.get("sha256") or "")
                if (
                    not path.is_file()
                    or not expected
                    or sha256_file(path) != expected
                ):
                    raise ValueError("invalid_resume_chunk_hash")
                frames.append(self._normalize_frame(pd.read_parquet(path)))
            combined = self._normalize_frame(pd.concat(frames, ignore_index=True))
            request_count = int(state.get("requestCount") or 0)
            oldest = state.get("oldestTimestampMs")
            oldest_ms = int(oldest) if oldest is not None else None
        except (OSError, TypeError, ValueError):
            self._invalidate(partition_root)
            return self._empty_snapshot()
        return ResumeSnapshot(
            frame=combined,
            requestCount=request_count,
            oldestTimestampMs=oldest_ms,
            chunkCount=len(chunks),
        )

    def append(
        self,
        identity: ResumeIdentity,
        frame: pd.DataFrame,
        *,
        request_count: int,
        oldest_timestamp_ms: int | None,
    ) -> ResumeSnapshot:
        normalized = self._normalize_frame(frame)
        if normalized.empty:
            return self.load(identity)
        partition_root = self._partition_root(identity)
        partition_root.mkdir(parents=True, exist_ok=True)
        state_path = partition_root / "state.json"
        state = load_json(state_path)
        if state and state.get("identity") != asdict(identity):
            self._invalidate(partition_root)
            partition_root.mkdir(parents=True, exist_ok=True)
            state = {}
        chunks: list[dict[str, Any]] = list(state.get("chunks") or [])
        sequence = len(chunks) + 1
        output = partition_root / f"chunk-{sequence:06d}.parquet"
        temporary = output.with_suffix(".parquet.tmp")
        normalized.to_parquet(temporary, index=False, compression="zstd")
        digest = sha256_file(temporary)
        os.replace(temporary, output)
        chunks.append(
            {
                "fileName": output.name,
                "rows": len(normalized),
                "sha256": digest,
            }
        )
        write_json_atomic(
            state_path,
            {
                "schemaVersion": RESUME_SCHEMA_VERSION,
                "identity": asdict(identity),
                "requestCount": max(0, int(request_count)),
                "oldestTimestampMs": oldest_timestamp_ms,
                "chunks": chunks,
            },
        )
        return ResumeSnapshot(
            frame=_empty_frame(),
            requestCount=max(0, int(request_count)),
            oldestTimestampMs=oldest_timestamp_ms,
            chunkCount=len(chunks),
        )

    def clear(self, identity: ResumeIdentity) -> None:
        partition_root = self._partition_root(identity)
        if partition_root.is_dir():
            shutil.rmtree(partition_root)
