"""Auditable OKX public historical funding archive backfill."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from io import BytesIO
import hashlib
import json
from pathlib import Path
from typing import Any
import urllib.parse
import urllib.request
from zipfile import BadZipFile, ZipFile

import pandas as pd

from alphapilot.data_foundation.okx_public import OkxPublicClient
from alphapilot.evolution.registry.hashing import stable_hash


class HistoricalFundingArchiveError(RuntimeError):
    """Raised when an official funding archive cannot be safely normalized."""


def _timestamp_ms(value: str) -> int:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return int(timestamp.timestamp() * 1000)


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _load_archive(url: str) -> bytes:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "static.okx.com":
        raise HistoricalFundingArchiveError("funding_archive_url_not_official")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/zip,application/octet-stream",
            "User-Agent": "AlphaPilot-Quant-Engine/13.27.1.36",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def parse_historical_funding_archive(
    payload: bytes,
    *,
    instrument_id: str,
    source_url: str,
    retrieved_at: str,
) -> pd.DataFrame:
    """Normalize one immutable OKX monthly funding ZIP without zero filling."""

    digest = hashlib.sha256(payload).hexdigest()
    try:
        with ZipFile(BytesIO(payload)) as archive:
            csv_names = [name for name in archive.namelist() if name.endswith(".csv")]
            if len(csv_names) != 1:
                raise HistoricalFundingArchiveError(
                    "funding_archive_csv_count_invalid"
                )
            with archive.open(csv_names[0]) as source:
                frame = pd.read_csv(source)
    except BadZipFile as error:
        raise HistoricalFundingArchiveError("funding_archive_zip_invalid") from error

    required = {"instrument_name", "funding_rate", "funding_time"}
    if not required.issubset(frame.columns):
        raise HistoricalFundingArchiveError("funding_archive_schema_invalid")
    instruments = set(frame["instrument_name"].dropna().astype(str).unique())
    if instruments != {instrument_id}:
        raise HistoricalFundingArchiveError(
            "funding_archive_instrument_mismatch"
        )

    rates = pd.to_numeric(frame["funding_rate"], errors="coerce")
    timestamps = pd.to_numeric(frame["funding_time"], errors="coerce")
    if rates.isna().any() or timestamps.isna().any():
        raise HistoricalFundingArchiveError("funding_archive_values_invalid")

    normalized = pd.DataFrame(
        {
            "instrument_id": instrument_id,
            "funding_rate": rates.astype(float),
            "timestamp_ms": timestamps.astype("int64"),
        }
    )
    normalized = normalized.sort_values("timestamp_ms").drop_duplicates(
        subset=["instrument_id", "timestamp_ms"], keep="last"
    )
    normalized["available_at"] = pd.to_datetime(
        normalized["timestamp_ms"], unit="ms", utc=True
    ).map(lambda value: value.isoformat())
    normalized["source_endpoint"] = source_url
    normalized["archive_filename"] = Path(
        urllib.parse.urlparse(source_url).path
    ).name
    normalized["archive_sha256"] = digest
    normalized["collected_at"] = retrieved_at
    return normalized.reset_index(drop=True)


def _archive_descriptors(payload: Iterable[dict[str, Any]]) -> list[dict[str, str]]:
    descriptors: list[dict[str, str]] = []
    for aggregation in payload:
        for detail in aggregation.get("details", []):
            if not isinstance(detail, dict):
                continue
            for group in detail.get("groupDetails", []):
                if not isinstance(group, dict):
                    continue
                url = str(group.get("url") or "")
                filename = str(group.get("filename") or "")
                if url and filename:
                    descriptors.append(
                        {
                            "url": url,
                            "filename": Path(filename).name,
                            "dateTs": str(group.get("dateTs") or ""),
                        }
                    )
    return descriptors


class OkxHistoricalFundingBackfill:
    """Download missing official monthly funding archives with resume evidence."""

    def __init__(
        self,
        *,
        warehouse_root: Path | str,
        client: OkxPublicClient,
        instruments: tuple[str, ...],
        begin: str,
        end: str,
        observed_at: str,
        archive_loader: Callable[[str], bytes] = _load_archive,
        pause_marker: Path | str | None = None,
        include_recent_tail: bool = False,
    ) -> None:
        self.warehouse_root = Path(warehouse_root).resolve()
        self.client = client
        self.instruments = tuple(sorted(set(instruments)))
        self.begin = begin
        self.end = end
        self.observed_at = observed_at
        self.archive_loader = archive_loader
        self.pause_marker = Path(pause_marker).resolve() if pause_marker else None
        self.include_recent_tail = bool(include_recent_tail)
        self.identity = stable_hash(
            {
                "source": "okx_public_historical_market_data",
                "module": 3,
                "instruments": self.instruments,
                "begin": self.begin,
                "end": self.end,
            },
            prefix="okx_funding_backfill",
        )
        audit_root = self.warehouse_root / "_alphapilot"
        self.raw_root = audit_root / "raw" / "okx" / "swap" / "funding_history"
        self.canonical_root = (
            audit_root / "canonical" / "okx" / "swap" / "funding"
        )
        evidence_root = audit_root / "evidence" / "okx" / "funding_history"
        self.manifest_path = evidence_root / "manifests" / f"{self.identity}.json"
        self.checkpoint_path = evidence_root / "checkpoints" / f"{self.identity}.json"

    def _discover(self, instrument_id: str) -> list[dict[str, str]]:
        family = instrument_id.removesuffix("-SWAP")
        response = self.client.historical_market_data(
            module=3,
            instrument_type="SWAP",
            instrument_family_list=(family,),
            date_aggregation_type="monthly",
            begin_ms=_timestamp_ms(self.begin),
            end_ms=_timestamp_ms(self.end),
        )
        return [
            item
            for item in _archive_descriptors(response)
            if item["filename"].startswith(f"{instrument_id}-fundingrates-")
        ]

    def _artifact_paths(
        self, instrument_id: str, filename: str
    ) -> tuple[Path, Path]:
        raw = self.raw_root / instrument_id / filename
        canonical = (
            self.canonical_root / instrument_id / f"{Path(filename).stem}.parquet"
        )
        return raw, canonical

    @staticmethod
    def _artifact_is_valid(raw: Path, canonical: Path) -> bool:
        if not raw.is_file() or not canonical.is_file():
            return False
        try:
            return bool(raw.stat().st_size and len(pd.read_parquet(canonical)))
        except (OSError, ValueError):
            return False

    def _latest_funding_timestamp(self, instrument_id: str) -> int:
        latest = -1
        for path in (self.canonical_root / instrument_id).glob("*.parquet"):
            try:
                frame = pd.read_parquet(path)
            except (OSError, ValueError):
                continue
            timestamp_column = next(
                (
                    column
                    for column in ("timestamp_ms", "fundingTime")
                    if column in frame.columns
                ),
                None,
            )
            if timestamp_column is None or frame.empty:
                continue
            timestamps = pd.to_numeric(frame[timestamp_column], errors="coerce")
            if timestamps.notna().any():
                latest = max(latest, int(timestamps.max()))
        return latest

    def _collect_recent_tail(self) -> tuple[list[dict[str, Any]], int]:
        artifacts: list[dict[str, Any]] = []
        total_rows = 0
        endpoint = (
            f"{str(getattr(self.client, 'base_url', 'https://openapi.okx.com')).rstrip('/')}"
            "/api/v5/public/funding-rate-history"
        )
        for instrument_id in self.instruments:
            known = self._latest_funding_timestamp(instrument_id)
            cursor: int | None = None
            seen_oldest: set[int] = set()
            rows: list[dict[str, Any]] = []
            for _ in range(100):
                page = self.client.funding_rate_history(
                    instrument_id=instrument_id,
                    after_ms=cursor,
                    limit=100,
                )
                if not page:
                    break
                for item in page:
                    timestamp = int(item["fundingTime"])
                    if timestamp > known:
                        rows.append(
                            {
                                "instrument_id": instrument_id,
                                "funding_rate": float(item["fundingRate"]),
                                "timestamp_ms": timestamp,
                                "available_at": pd.Timestamp(
                                    timestamp, unit="ms", tz="UTC"
                                ).isoformat(),
                                "source_endpoint": endpoint,
                                "archive_filename": None,
                                "archive_sha256": None,
                                "collected_at": self.observed_at,
                            }
                        )
                oldest = min(int(item["fundingTime"]) for item in page)
                if len(page) < 100 or oldest <= known or oldest in seen_oldest:
                    break
                seen_oldest.add(oldest)
                cursor = oldest
            if not rows:
                continue
            frame = pd.DataFrame(rows).sort_values("timestamp_ms").drop_duplicates(
                subset=["instrument_id", "timestamp_ms"], keep="last"
            )
            identity = stable_hash(
                frame.to_dict(orient="records"), prefix="funding_recent"
            )
            output = (
                self.canonical_root
                / instrument_id
                / f"funding-recent-{identity[-16:]}.parquet"
            )
            if not output.is_file():
                output.parent.mkdir(parents=True, exist_ok=True)
                temporary = output.with_suffix(".parquet.tmp")
                frame.to_parquet(temporary, index=False)
                temporary.replace(output)
            artifacts.append(
                {
                    "artifactType": "recentFundingTail",
                    "instrumentId": instrument_id,
                    "canonicalPath": str(output.resolve()),
                    "rowCount": int(len(frame)),
                    "startTimestampMs": int(frame["timestamp_ms"].min()),
                    "endTimestampMs": int(frame["timestamp_ms"].max()),
                    "sourceEndpoint": endpoint,
                }
            )
            total_rows += len(frame)
        return artifacts, total_rows

    def run(self) -> dict[str, Any]:
        descriptors: list[tuple[str, dict[str, str]]] = []
        for instrument_id in self.instruments:
            descriptors.extend(
                (instrument_id, item) for item in self._discover(instrument_id)
            )
        descriptors.sort(key=lambda item: (item[0], item[1]["filename"]))

        artifacts: list[dict[str, Any]] = []
        downloaded = 0
        status = "completed"
        for instrument_id, descriptor in descriptors:
            if self.pause_marker and self.pause_marker.exists():
                status = "paused"
                break
            raw, canonical = self._artifact_paths(
                instrument_id, descriptor["filename"]
            )
            if not self._artifact_is_valid(raw, canonical):
                payload = self.archive_loader(descriptor["url"])
                normalized = parse_historical_funding_archive(
                    payload,
                    instrument_id=instrument_id,
                    source_url=descriptor["url"],
                    retrieved_at=self.observed_at,
                )
                _atomic_write_bytes(raw, payload)
                canonical.parent.mkdir(parents=True, exist_ok=True)
                temporary = canonical.with_suffix(".parquet.tmp")
                normalized.to_parquet(temporary, index=False)
                temporary.replace(canonical)
                downloaded += 1
            canonical_frame = pd.read_parquet(canonical)
            artifacts.append(
                {
                    "artifactType": "monthlyFundingArchive",
                    "instrumentId": instrument_id,
                    "archiveFilename": descriptor["filename"],
                    "sourceUrl": descriptor["url"],
                    "rawPath": str(raw.resolve()),
                    "canonicalPath": str(canonical.resolve()),
                    "archiveSha256": hashlib.sha256(raw.read_bytes()).hexdigest(),
                    "rowCount": int(len(canonical_frame)),
                    "startTimestampMs": int(canonical_frame["timestamp_ms"].min()),
                    "endTimestampMs": int(canonical_frame["timestamp_ms"].max()),
                }
            )

        completed_archive_count = len(artifacts)
        recent_tail_rows = 0
        if status == "completed" and self.include_recent_tail:
            tail_artifacts, recent_tail_rows = self._collect_recent_tail()
            artifacts.extend(tail_artifacts)

        manifest: dict[str, Any] = {
            "schemaVersion": "v36_okx_historical_funding_v1",
            "backfillId": self.identity,
            "status": status,
            "sourceEndpoint": "/api/v5/public/market-data-history",
            "module": 3,
            "instruments": list(self.instruments),
            "begin": self.begin,
            "end": self.end,
            "observedAt": self.observed_at,
            "archiveCount": len(descriptors),
            "completedArchiveCount": completed_archive_count,
            "downloadedArchiveCount": downloaded,
            "recentTailRowCount": recent_tail_rows,
            "publicDataOnly": True,
            "sameExchangeOnly": True,
            "zeroFillUsed": False,
            "mixedExchangeFundingUsed": False,
            "artifacts": artifacts,
        }
        _atomic_write_json(self.manifest_path, manifest)
        _atomic_write_json(
            self.checkpoint_path,
            {
                "schemaVersion": "v36_okx_historical_funding_checkpoint_v1",
                "backfillId": self.identity,
                "status": status,
                "completedArchiveCount": completed_archive_count,
                "archiveCount": len(descriptors),
                "recentTailRowCount": recent_tail_rows,
                "manifestPath": str(self.manifest_path.resolve()),
            },
        )
        return {
            **manifest,
            "manifestPath": str(self.manifest_path.resolve()),
            "checkpointPath": str(self.checkpoint_path.resolve()),
        }
