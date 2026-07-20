"""Audited V34B funding, PIT metadata, and resumable public forward snapshots."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .checkpoint import load_json, pause_requested, write_json_atomic
from .okx_official_v1 import OkxOfficialV1Layout, PILOT_INSTRUMENTS
from .okx_public import OkxPublicClient


METADATA_FIELDS = (
    "instId",
    "instType",
    "instFamily",
    "uly",
    "settleCcy",
    "ctVal",
    "ctMult",
    "ctValCcy",
    "ctType",
    "listTime",
    "expTime",
    "tickSz",
    "lotSz",
    "minSz",
    "state",
    "ruleType",
)

FORWARD_STREAMS = (
    "instrument_state",
    "current_funding",
    "open_interest",
    "mark_price",
    "index_price",
    "ticker_spread",
    "order_book_summary",
)


class ForwardCollectionPaused(RuntimeError):
    """Raised after durable checkpointing when a pause marker is present."""


def _iso_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC).isoformat()


def _timestamp_iso(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, tz=UTC).isoformat()


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def normalize_funding_rows(
    rows: list[dict[str, Any]],
    *,
    instrument_id: str,
    retrieved_at: str,
    source_hash: str,
) -> list[dict[str, Any]]:
    """Normalize settled funding without exposing realized values before funding time."""

    if len(source_hash) != 64:
        raise ValueError("funding_source_hash_must_be_sha256")
    normalized: dict[int, dict[str, Any]] = {}
    for row in rows:
        if row.get("fundingTime") in {None, ""} or row.get("fundingRate") in {
            None,
            "",
        }:
            continue
        funding_time = int(row["fundingTime"])
        normalized[funding_time] = {
            "instrumentId": instrument_id,
            "fundingTime": funding_time,
            "fundingRate": float(row["fundingRate"]),
            "realizedRate": _optional_float(row.get("realizedRate")),
            "formulaType": str(row.get("formulaType") or "") or None,
            "method": str(row.get("method") or "") or None,
            "realizedRateAvailableAt": _timestamp_iso(funding_time),
            "retrievedAt": _iso_utc(retrieved_at),
            "sourceHash": source_hash,
        }
    return [normalized[key] for key in sorted(normalized)]


def _upcoming_changes(value: Any) -> list[dict[str, Any]]:
    if value is None or value == "":
        return []
    parsed = value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [{"raw": value}]
    if not isinstance(parsed, list):
        return [{"raw": parsed}]
    return [dict(item) for item in parsed if isinstance(item, dict)]


def normalize_instrument_metadata(
    rows: list[dict[str, Any]],
    *,
    retrieved_at: str,
    source_hash: str,
) -> list[dict[str, Any]]:
    normalized = []
    for row in rows:
        instrument_id = str(row.get("instId") or "").strip()
        if not instrument_id:
            continue
        item = {field: row.get(field) for field in METADATA_FIELDS}
        item.update(
            {
                "upcomingParameterChanges": _upcoming_changes(row.get("upcChg")),
                "retrievedAt": _iso_utc(retrieved_at),
                "availableAt": _iso_utc(retrieved_at),
                "sourceHash": source_hash,
            }
        )
        normalized.append(item)
    return sorted(normalized, key=lambda item: str(item["instId"]))


class OkxOfficialV1ForwardCollector:
    """Create one immutable, resumable V34B public-data observation."""

    def __init__(
        self,
        *,
        warehouse_root: Path | str,
        client: OkxPublicClient,
        instruments: tuple[str, ...] = PILOT_INSTRUMENTS,
        observed_at: str | None = None,
        pause_file: Path | None = None,
        base_snapshot_id: str | None = None,
    ) -> None:
        if not instruments:
            raise ValueError("v34b_instruments_must_not_be_empty")
        self.layout = OkxOfficialV1Layout.from_warehouse(warehouse_root)
        self.client = client
        self.instruments = tuple(dict.fromkeys(instruments))
        self.observed_at = _iso_utc(observed_at or datetime.now(UTC).isoformat())
        self.pause_file = pause_file or self.layout.checkpointRoot / "V34B_PAUSE_REQUESTED"
        self.base_snapshot_id = str(base_snapshot_id or "").strip() or None
        self.collection_id = stable_hash(
            {
                "schemaVersion": "okx_official_v1_v34b_collection_identity_v1",
                "observedAt": self.observed_at,
                "instruments": self.instruments,
            },
            prefix="v34b_collection",
        )
        self.checkpoint_path = (
            self.layout.checkpointRoot / "v34b" / f"{self.collection_id}.json"
        )

    def _base_snapshot_integrity(self) -> dict[str, Any] | None:
        if not self.base_snapshot_id:
            return None
        snapshot_path = (
            self.layout.manifestRoot / f"snapshot-{self.base_snapshot_id}.json"
        )
        if not snapshot_path.is_file():
            raise FileNotFoundError("v34a_registered_snapshot_manifest_missing")
        payload = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if payload.get("snapshotId") != self.base_snapshot_id:
            raise RuntimeError("v34a_registered_snapshot_identity_mismatch")
        artifacts = [
            {
                "role": "snapshot_manifest",
                "path": str(snapshot_path.resolve()),
                "sha256": sha256_file(snapshot_path),
            }
        ]
        metadata_path = Path(str(payload.get("instrumentMetadataPath") or ""))
        if not metadata_path.is_file():
            raise FileNotFoundError("v34a_registered_metadata_snapshot_missing")
        artifacts.append(
            {
                "role": "instrument_metadata",
                "path": str(metadata_path.resolve()),
                "sha256": sha256_file(metadata_path),
            }
        )
        for partition in payload.get("partitions") or []:
            path = Path(str(partition.get("outputPath") or ""))
            expected = str(partition.get("outputSha256") or "")
            if not path.is_file():
                raise FileNotFoundError("v34a_registered_partition_missing")
            actual = sha256_file(path)
            if actual != expected:
                raise RuntimeError("v34a_registered_partition_hash_mismatch")
            artifacts.append(
                {
                    "role": "ohlcv_partition",
                    "instrumentId": partition.get("instrumentId"),
                    "timeframe": partition.get("timeframe"),
                    "path": str(path.resolve()),
                    "sha256": actual,
                }
            )
        return {
            "snapshotId": self.base_snapshot_id,
            "status": "valid_and_unchanged",
            "artifactCount": len(artifacts),
            "artifacts": artifacts,
        }

    def _latest_receipt(self) -> dict[str, Any]:
        records = getattr(self.client, "request_audit_records", [])
        if not records:
            raise RuntimeError("okx_public_request_receipt_missing")
        receipt = dict(records[-1])
        source_hash = str(receipt.get("rawPayloadSha256") or "")
        if len(source_hash) != 64:
            raise RuntimeError("okx_public_response_hash_missing")
        return receipt

    @staticmethod
    def _artifact_valid(entry: dict[str, Any] | None) -> bool:
        if not isinstance(entry, dict):
            return False
        path = Path(str(entry.get("path") or ""))
        expected = str(entry.get("sha256") or "")
        if not (path.is_file() and len(expected) == 64 and sha256_file(path) == expected):
            return False
        for artifact in entry.get("dataArtifacts") or []:
            data_path = Path(str(artifact.get("path") or ""))
            data_hash = str(artifact.get("sha256") or "")
            if not (
                data_path.is_file()
                and len(data_hash) == 64
                and sha256_file(data_path) == data_hash
            ):
                return False
        return True

    @staticmethod
    def _write_immutable_json(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
        if not path.is_file():
            write_json_atomic(path, payload)
        digest = sha256_file(path)
        return {"path": str(path.resolve()), "sha256": digest}

    def _payload_path(self, stream: str, payload: dict[str, Any]) -> Path:
        identity = stable_hash(payload, prefix=f"v34b_{stream}")
        return (
            self.layout.forwardCollectionRoot
            / stream
            / self.observed_at[:10]
            / f"{identity}.json"
        )

    def _write_stream_payload(
        self, stream: str, records: list[dict[str, Any]]
    ) -> dict[str, Any]:
        payload = {
            "schemaVersion": f"okx_official_v1_v34b_{stream}_v1",
            "collectionId": self.collection_id,
            "observedAt": self.observed_at,
            "appendOnly": True,
            "publicDataOnly": True,
            "records": records,
        }
        return self._write_immutable_json(self._payload_path(stream, payload), payload)

    def _request_records(
        self,
        method: Callable[..., list[dict[str, Any]]],
        *,
        instrument_id: str,
        request_instrument_id: str | None = None,
    ) -> list[dict[str, Any]]:
        rows = method(instrument_id=request_instrument_id or instrument_id)
        receipt = self._latest_receipt()
        retrieved_at = str(receipt.get("requestCompletedAt") or self.observed_at)
        source_hash = str(receipt["rawPayloadSha256"])
        return [
            {
                "instrumentId": instrument_id,
                "retrievedAt": _iso_utc(retrieved_at),
                "sourceHash": source_hash,
                "sourcePath": receipt.get("path"),
                "payload": dict(row),
            }
            for row in rows
        ]

    def _collect_metadata(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        rows = self.client.public_instruments(instrument_type="SWAP")
        receipt = self._latest_receipt()
        retrieved_at = str(receipt.get("requestCompletedAt") or self.observed_at)
        normalized = normalize_instrument_metadata(
            rows,
            retrieved_at=retrieved_at,
            source_hash=str(receipt["rawPayloadSha256"]),
        )
        available = {str(row["instId"]) for row in normalized}
        missing = sorted(set(self.instruments) - available)
        if missing:
            raise RuntimeError("v34b_instrument_metadata_missing:" + ",".join(missing))
        payload = {
            "schemaVersion": "okx_official_v1_v34b_instrument_metadata_v1",
            "collectionId": self.collection_id,
            "observedAt": self.observed_at,
            "pitHistoryBeginsAt": self.observed_at,
            "historicalStateReconstructed": False,
            "publicDataOnly": True,
            "sourceEndpoint": "/api/v5/public/instruments",
            "sourceResponseHash": receipt["rawPayloadSha256"],
            "instruments": normalized,
        }
        identity = stable_hash(payload, prefix="v34b_instrument_metadata")
        path = (
            self.layout.metadataSnapshotRoot
            / "pit"
            / self.observed_at[:10]
            / f"instruments-{identity}.json"
        )
        return self._write_immutable_json(path, payload), normalized

    def _collect_funding(self) -> tuple[dict[str, Any], list[str]]:
        paths: list[str] = []
        artifacts: list[dict[str, Any]] = []
        for instrument_id in self.instruments:
            normalized: dict[int, dict[str, Any]] = {}
            cursor: int | None = None
            seen: set[int] = set()
            for _ in range(100):
                page = self.client.funding_rate_history(
                    instrument_id=instrument_id,
                    after_ms=cursor,
                    limit=100,
                )
                receipt = self._latest_receipt()
                if not page:
                    break
                for item in normalize_funding_rows(
                    page,
                    instrument_id=instrument_id,
                    retrieved_at=str(
                        receipt.get("requestCompletedAt") or self.observed_at
                    ),
                    source_hash=str(receipt["rawPayloadSha256"]),
                ):
                    normalized[int(item["fundingTime"])] = item
                oldest = min(int(row["fundingTime"]) for row in page)
                if len(page) < 100 or oldest in seen:
                    break
                seen.add(oldest)
                cursor = oldest
            rows = [normalized[key] for key in sorted(normalized)]
            if not rows:
                continue
            identity = stable_hash(rows, prefix="v34b_funding_history")
            path = (
                self.layout.canonicalRoot
                / "okx"
                / "swap"
                / "funding"
                / instrument_id
                / f"funding-history-{identity}.parquet"
            )
            if not path.is_file():
                path.parent.mkdir(parents=True, exist_ok=True)
                temporary = path.with_suffix(".parquet.tmp")
                pd.DataFrame(rows).to_parquet(
                    temporary,
                    index=False,
                    compression="zstd",
                )
                temporary.replace(path)
            digest = sha256_file(path)
            paths.append(str(path.resolve()))
            artifacts.append(
                {
                    "instrumentId": instrument_id,
                    "path": str(path.resolve()),
                    "sha256": digest,
                    "rows": len(rows),
                    "startFundingTime": int(rows[0]["fundingTime"]),
                    "endFundingTime": int(rows[-1]["fundingTime"]),
                }
            )
        payload = {
            "schemaVersion": "okx_official_v1_v34b_funding_manifest_v1",
            "collectionId": self.collection_id,
            "observedAt": self.observed_at,
            "publicDataOnly": True,
            "recentHistoryOnly": True,
            "historicalCoverageWarning": (
                "OKX funding-rate-history is bounded recent public history; "
                "no unavailable long history is fabricated."
            ),
            "artifacts": artifacts,
        }
        identity = stable_hash(payload, prefix="v34b_funding_manifest")
        path = self.layout.manifestRoot / "v34b" / f"funding-{identity}.json"
        entry = self._write_immutable_json(path, payload)
        entry["dataPaths"] = paths
        entry["dataArtifacts"] = artifacts
        return entry, paths

    def _collect_instrument_state(
        self, metadata_rows: list[dict[str, Any]]
    ) -> dict[str, Any]:
        selected = [
            row for row in metadata_rows if str(row["instId"]) in self.instruments
        ]
        return self._write_stream_payload("instrument_state", selected)

    def _collect_per_instrument(
        self,
        stream: str,
        method: Callable[..., list[dict[str, Any]]],
        *,
        metadata_by_id: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        records: list[dict[str, Any]] = []
        for instrument_id in self.instruments:
            request_id = instrument_id
            if stream == "index_price":
                metadata = (metadata_by_id or {}).get(instrument_id, {})
                request_id = str(metadata.get("uly") or instrument_id.removesuffix("-SWAP"))
            records.extend(
                self._request_records(
                    method,
                    instrument_id=instrument_id,
                    request_instrument_id=request_id,
                )
            )
        return self._write_stream_payload(stream, records)

    def _collect_ticker_spread(self) -> dict[str, Any]:
        rows = self.client.public_tickers(instrument_type="SWAP")
        receipt = self._latest_receipt()
        source_hash = str(receipt["rawPayloadSha256"])
        retrieved_at = _iso_utc(
            str(receipt.get("requestCompletedAt") or self.observed_at)
        )
        records = []
        for row in rows:
            instrument_id = str(row.get("instId") or "")
            if instrument_id not in self.instruments:
                continue
            bid = _optional_float(row.get("bidPx"))
            ask = _optional_float(row.get("askPx"))
            midpoint = (bid + ask) / 2 if bid is not None and ask is not None else None
            spread = ask - bid if bid is not None and ask is not None else None
            records.append(
                {
                    "instrumentId": instrument_id,
                    "bidPx": bid,
                    "askPx": ask,
                    "lastPx": _optional_float(row.get("last")),
                    "spread": spread,
                    "spreadBps": (
                        spread / midpoint * 10_000
                        if spread is not None and midpoint not in {None, 0}
                        else None
                    ),
                    "exchangeTimestampMs": int(row["ts"]) if row.get("ts") else None,
                    "retrievedAt": retrieved_at,
                    "sourceHash": source_hash,
                }
            )
        return self._write_stream_payload("ticker_spread", records)

    def _collect_order_book_summary(self) -> dict[str, Any]:
        records = []
        for instrument_id in self.instruments:
            rows = self.client.order_book(instrument_id=instrument_id, depth=5)
            receipt = self._latest_receipt()
            for row in rows:
                asks = row.get("asks") if isinstance(row.get("asks"), list) else []
                bids = row.get("bids") if isinstance(row.get("bids"), list) else []
                records.append(
                    {
                        "instrumentId": instrument_id,
                        "bestAsk": _optional_float(asks[0][0]) if asks else None,
                        "bestBid": _optional_float(bids[0][0]) if bids else None,
                        "askDepthSize": sum(float(level[1]) for level in asks),
                        "bidDepthSize": sum(float(level[1]) for level in bids),
                        "exchangeTimestampMs": int(row["ts"]) if row.get("ts") else None,
                        "retrievedAt": _iso_utc(
                            str(receipt.get("requestCompletedAt") or self.observed_at)
                        ),
                        "sourceHash": receipt["rawPayloadSha256"],
                    }
                )
        return self._write_stream_payload("order_book_summary", records)

    def _save_checkpoint(self, checkpoint: dict[str, Any]) -> None:
        checkpoint["completedStreams"] = sorted(
            str(key) for key in (checkpoint.get("artifacts") or {})
        )
        write_json_atomic(self.checkpoint_path, checkpoint)

    def run(self) -> dict[str, Any]:
        self.layout.ensure_directories()
        base_before = self._base_snapshot_integrity()
        base_audit_hash = (
            stable_hash(base_before, prefix="v34a_base_snapshot_integrity")
            if base_before
            else None
        )
        checkpoint = load_json(self.checkpoint_path)
        if checkpoint.get("status") == "completed" and isinstance(
            checkpoint.get("finalResult"), dict
        ):
            final_result = dict(checkpoint["finalResult"])
            final_manifest = {
                "path": final_result.get("snapshotManifestPath"),
                "sha256": final_result.get("snapshotManifestSha256"),
            }
            if (
                final_result.get("baseSnapshotAuditHash") == base_audit_hash
                and self._artifact_valid(final_manifest)
                and all(
                self._artifact_valid(entry)
                for entry in (checkpoint.get("artifacts") or {}).values()
                )
            ):
                return final_result
            checkpoint["status"] = "interrupted"
            checkpoint["lastError"] = {
                "type": "ArtifactIntegrityError",
                "message": "v34b_completed_artifact_integrity_failed",
            }
        checkpoint.setdefault(
            "schemaVersion", "okx_official_v1_v34b_checkpoint_v1"
        )
        checkpoint.setdefault("collectionId", self.collection_id)
        checkpoint.setdefault("observedAt", self.observed_at)
        checkpoint.setdefault("instruments", list(self.instruments))
        checkpoint.setdefault("artifacts", {})
        checkpoint["status"] = "running"
        checkpoint.pop("lastError", None)
        self._save_checkpoint(checkpoint)

        artifacts: dict[str, dict[str, Any]] = checkpoint["artifacts"]
        metadata_rows: list[dict[str, Any]] = []
        funding_paths: list[str] = []
        try:
            if self._artifact_valid(artifacts.get("instrument_metadata")):
                metadata_payload = json.loads(
                    Path(artifacts["instrument_metadata"]["path"]).read_text(
                        encoding="utf-8"
                    )
                )
                metadata_rows = list(metadata_payload["instruments"])
            else:
                artifacts["instrument_metadata"], metadata_rows = self._collect_metadata()
                self._save_checkpoint(checkpoint)

            if self._artifact_valid(artifacts.get("funding_history")):
                funding_paths = list(artifacts["funding_history"].get("dataPaths") or [])
            else:
                artifacts["funding_history"], funding_paths = self._collect_funding()
                self._save_checkpoint(checkpoint)

            metadata_by_id = {
                str(row["instId"]): row for row in metadata_rows
            }
            collectors: tuple[tuple[str, Callable[[], dict[str, Any]]], ...] = (
                (
                    "instrument_state",
                    lambda: self._collect_instrument_state(metadata_rows),
                ),
                (
                    "current_funding",
                    lambda: self._collect_per_instrument(
                        "current_funding", self.client.current_funding_rate
                    ),
                ),
                (
                    "open_interest",
                    lambda: self._collect_per_instrument(
                        "open_interest", self.client.open_interest
                    ),
                ),
                (
                    "mark_price",
                    lambda: self._collect_per_instrument(
                        "mark_price", self.client.mark_price
                    ),
                ),
                (
                    "index_price",
                    lambda: self._collect_per_instrument(
                        "index_price",
                        self.client.index_ticker,
                        metadata_by_id=metadata_by_id,
                    ),
                ),
                ("ticker_spread", self._collect_ticker_spread),
                ("order_book_summary", self._collect_order_book_summary),
            )
            for stream, collect in collectors:
                if pause_requested(self.pause_file):
                    checkpoint["status"] = "paused"
                    self._save_checkpoint(checkpoint)
                    raise ForwardCollectionPaused("v34b_forward_collection_paused")
                if self._artifact_valid(artifacts.get(stream)):
                    continue
                artifacts[stream] = collect()
                self._save_checkpoint(checkpoint)
        except Exception as error:
            checkpoint["status"] = (
                "paused" if isinstance(error, ForwardCollectionPaused) else "interrupted"
            )
            checkpoint["lastError"] = {
                "type": type(error).__name__,
                "message": str(error),
            }
            self._save_checkpoint(checkpoint)
            raise

        manifest_payload = {
            "schemaVersion": "okx_official_v1_v34b_snapshot_v1",
            "collectionId": self.collection_id,
            "observedAt": self.observed_at,
            "scope": "v34b_public_data_only",
            "status": "immutable_data_extension_snapshot",
            "instruments": list(self.instruments),
            "artifacts": artifacts,
            "baseSnapshotIntegrity": base_before,
            "causalSemantics": {
                "instrumentMetadataAvailableAt": "retrievedAt",
                "realizedFundingAvailableAt": "fundingTime",
                "historicalInstrumentStateReconstructed": False,
            },
            "candidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "privateAccountReadUsed": False,
        }
        base_after = self._base_snapshot_integrity()
        if base_before != base_after:
            raise RuntimeError("v34a_base_snapshot_changed_during_v34b_run")
        snapshot_id = stable_hash(manifest_payload, prefix="okx_official_v1_v34b_snapshot")
        manifest_payload["snapshotId"] = snapshot_id
        manifest_path = (
            self.layout.manifestRoot / "v34b" / f"snapshot-{snapshot_id}.json"
        )
        manifest_entry = self._write_immutable_json(manifest_path, manifest_payload)
        result = {
            "schemaVersion": "okx_official_v1_v34b_result_v1",
            "status": "completed",
            "scope": "v34b_public_data_only",
            "collectionId": self.collection_id,
            "observedAt": self.observed_at,
            "snapshotId": snapshot_id,
            "snapshotManifestPath": manifest_entry["path"],
            "snapshotManifestSha256": manifest_entry["sha256"],
            "checkpointPath": str(self.checkpoint_path.resolve()),
            "instrumentMetadataPath": artifacts["instrument_metadata"]["path"],
            "instrumentMetadataCount": len(metadata_rows),
            "fundingInstrumentCount": len(funding_paths),
            "fundingPaths": funding_paths,
            "forwardStreamsCompleted": sorted(FORWARD_STREAMS),
            "candidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "privateAccountReadUsed": False,
            "baseSnapshotId": self.base_snapshot_id,
            "baseSnapshotAuditHash": base_audit_hash,
            "baseSnapshotUnchanged": base_before == base_after,
            "baseSnapshotArtifactCount": int(
                (base_before or {}).get("artifactCount") or 0
            ),
        }
        checkpoint["status"] = "completed"
        checkpoint["finalResult"] = result
        self._save_checkpoint(checkpoint)
        return result


__all__ = [
    "FORWARD_STREAMS",
    "ForwardCollectionPaused",
    "OkxOfficialV1ForwardCollector",
    "normalize_funding_rows",
    "normalize_instrument_metadata",
]
