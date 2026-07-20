"""Incremental, content-addressed public OKX collection for V34C."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from alphapilot.data_foundation.checkpoint import load_json, write_json_atomic
from alphapilot.data_foundation.okx_official_v1 import OkxOfficialV1Layout
from alphapilot.data_foundation.okx_official_v1_forward import (
    normalize_funding_rows,
    normalize_instrument_metadata,
)
from alphapilot.data_foundation.okx_public import OkxPublicClient
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash


SUPPORTED_TASKS = (
    "instrument_metadata",
    "funding_increment",
    "instrument_state",
    "current_funding",
    "open_interest",
    "mark_price",
    "index_price",
    "ticker_spread",
    "order_book_summary",
)


def _iso_utc(value: str) -> str:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed.astimezone(UTC).isoformat()


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


@dataclass(frozen=True)
class TaskCollectionResult:
    task_name: str
    status: str
    observed_at: str
    artifact_path: str | None
    artifact_sha256: str | None
    row_count: int
    source_timestamp: str | None
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class OkxOfficialV1IncrementalCollector:
    """Collect one due public stream without mutating V34A/V34B artifacts."""

    def __init__(
        self,
        *,
        warehouse_root: Path | str,
        client: OkxPublicClient,
        instruments: tuple[str, ...],
    ) -> None:
        if not instruments:
            raise ValueError("v34c_instruments_must_not_be_empty")
        self.layout = OkxOfficialV1Layout.from_warehouse(warehouse_root)
        self.layout.ensure_directories()
        self.client = client
        self.instruments = tuple(dict.fromkeys(instruments))
        self.index_path = self.layout.manifestRoot / "v34c" / "artifact_index.json"
        self.funding_state_path = (
            self.layout.manifestRoot / "v34c" / "funding_high_water.json"
        )

    def collect_task(self, task_name: str, observed_at: str) -> TaskCollectionResult:
        if task_name not in SUPPORTED_TASKS:
            raise ValueError(f"unsupported_v34c_collection_task:{task_name}")
        observed_at = _iso_utc(observed_at)
        if task_name == "instrument_metadata":
            return self._collect_metadata(observed_at)
        if task_name == "funding_increment":
            return self._collect_funding_increment(observed_at)
        if task_name == "instrument_state":
            return self._collect_instrument_state(observed_at)
        if task_name == "ticker_spread":
            return self._collect_ticker_spread(observed_at)
        if task_name == "order_book_summary":
            return self._collect_order_book_summary(observed_at)
        methods: dict[str, Callable[..., list[dict[str, Any]]]] = {
            "current_funding": self.client.current_funding_rate,
            "open_interest": self.client.open_interest,
            "mark_price": self.client.mark_price,
            "index_price": self.client.index_ticker,
        }
        return self._collect_per_instrument(task_name, observed_at, methods[task_name])

    def _latest_receipt(self) -> dict[str, Any]:
        records = getattr(self.client, "request_audit_records", [])
        if not records:
            raise RuntimeError("okx_public_request_receipt_missing")
        receipt = dict(records[-1])
        source_hash = str(receipt.get("rawPayloadSha256") or "")
        if len(source_hash) != 64:
            raise RuntimeError("okx_public_response_hash_missing")
        endpoint = str(receipt.get("path") or "")
        if not endpoint.startswith("/api/v5/"):
            raise RuntimeError("okx_public_source_endpoint_missing")
        return receipt

    @staticmethod
    def _provenance(receipt: dict[str, Any], observed_at: str) -> dict[str, Any]:
        return {
            "sourceEndpoint": str(receipt["path"]),
            "sourceHash": str(receipt["rawPayloadSha256"]),
            "retrievedAt": _iso_utc(
                str(receipt.get("requestCompletedAt") or observed_at)
            ),
            "observedAt": observed_at,
        }

    def _write_json_artifact(
        self,
        task_name: str,
        observed_at: str,
        payload: dict[str, Any],
    ) -> tuple[Path, str, bool]:
        identity = stable_hash(payload, prefix=f"v34c_{task_name}")
        path = (
            self.layout.forwardCollectionRoot
            / "v34c"
            / task_name
            / observed_at[:10]
            / f"{identity}.json"
        )
        reused = path.is_file()
        if reused:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if existing != payload:
                raise RuntimeError("v34c_content_addressed_artifact_mismatch")
        else:
            write_json_atomic(path, payload)
        digest = sha256_file(path)
        self._append_artifact_index(
            {
                "taskName": task_name,
                "observedAt": observed_at,
                "path": str(path.resolve()),
                "sha256": digest,
                "rowCount": len(payload.get("records") or []),
            }
        )
        return path, digest, reused

    def _append_artifact_index(self, entry: dict[str, Any]) -> None:
        index = load_json(self.index_path)
        if not index:
            index = {
                "schemaVersion": "okx_official_v1_v34c_artifact_index_v1",
                "appendOnly": True,
                "entries": [],
            }
        entries = index.get("entries")
        if not isinstance(entries, list):
            raise RuntimeError("v34c_artifact_index_invalid")
        path = str(entry["path"])
        existing = next(
            (item for item in entries if isinstance(item, dict) and item.get("path") == path),
            None,
        )
        if existing is not None:
            if existing != entry:
                raise RuntimeError("v34c_artifact_index_entry_mismatch")
            return
        entries.append(entry)
        write_json_atomic(self.index_path, index)

    def _snapshot_result(
        self,
        task_name: str,
        observed_at: str,
        records: list[dict[str, Any]],
    ) -> TaskCollectionResult:
        payload = {
            "schemaVersion": f"okx_official_v1_v34c_{task_name}_v1",
            "taskName": task_name,
            "observedAt": observed_at,
            "instruments": list(self.instruments),
            "appendOnly": True,
            "publicDataOnly": True,
            "records": records,
        }
        path, digest, reused = self._write_json_artifact(
            task_name, observed_at, payload
        )
        source_timestamps = [
            str(record.get("retrievedAt"))
            for record in records
            if record.get("retrievedAt")
        ]
        return TaskCollectionResult(
            task_name=task_name,
            status="collected",
            observed_at=observed_at,
            artifact_path=str(path.resolve()),
            artifact_sha256=digest,
            row_count=len(records),
            source_timestamp=max(source_timestamps) if source_timestamps else None,
            details={"artifactReused": reused},
        )

    def _collect_metadata(self, observed_at: str) -> TaskCollectionResult:
        rows = self.client.public_instruments(instrument_type="SWAP")
        receipt = self._latest_receipt()
        provenance = self._provenance(receipt, observed_at)
        normalized = normalize_instrument_metadata(
            rows,
            retrieved_at=provenance["retrievedAt"],
            source_hash=provenance["sourceHash"],
        )
        selected = [row for row in normalized if row["instId"] in self.instruments]
        missing = sorted(set(self.instruments) - {str(row["instId"]) for row in selected})
        if missing:
            raise RuntimeError("v34c_instrument_metadata_missing:" + ",".join(missing))
        payload = {
            "schemaVersion": "okx_official_v1_v34c_instrument_metadata_v1",
            "taskName": "instrument_metadata",
            "observedAt": observed_at,
            "pitHistoryBeginsAt": observed_at,
            "historicalStateReconstructed": False,
            "appendOnly": True,
            "publicDataOnly": True,
            "sourceEndpoint": provenance["sourceEndpoint"],
            "sourceResponseHash": provenance["sourceHash"],
            "retrievedAt": provenance["retrievedAt"],
            "instruments": selected,
            "records": selected,
        }
        path, digest, reused = self._write_json_artifact(
            "instrument_metadata", observed_at, payload
        )
        return TaskCollectionResult(
            task_name="instrument_metadata",
            status="collected",
            observed_at=observed_at,
            artifact_path=str(path.resolve()),
            artifact_sha256=digest,
            row_count=len(selected),
            source_timestamp=provenance["retrievedAt"],
            details={
                "artifactReused": reused,
                "historicalStateReconstructed": False,
            },
        )

    def _collect_instrument_state(self, observed_at: str) -> TaskCollectionResult:
        rows = self.client.public_instruments(instrument_type="SWAP")
        receipt = self._latest_receipt()
        provenance = self._provenance(receipt, observed_at)
        records = []
        for row in rows:
            instrument_id = str(row.get("instId") or "")
            if instrument_id in self.instruments:
                records.append(
                    {"instrumentId": instrument_id, "payload": dict(row), **provenance}
                )
        return self._snapshot_result("instrument_state", observed_at, records)

    def _collect_per_instrument(
        self,
        task_name: str,
        observed_at: str,
        method: Callable[..., list[dict[str, Any]]],
    ) -> TaskCollectionResult:
        records: list[dict[str, Any]] = []
        for instrument_id in self.instruments:
            request_id = (
                instrument_id.removesuffix("-SWAP")
                if task_name == "index_price"
                else instrument_id
            )
            rows = method(instrument_id=request_id)
            receipt = self._latest_receipt()
            provenance = self._provenance(receipt, observed_at)
            records.extend(
                {
                    "instrumentId": instrument_id,
                    "payload": dict(row),
                    **provenance,
                }
                for row in rows
            )
        return self._snapshot_result(task_name, observed_at, records)

    def _collect_ticker_spread(self, observed_at: str) -> TaskCollectionResult:
        rows = self.client.public_tickers(instrument_type="SWAP")
        receipt = self._latest_receipt()
        provenance = self._provenance(receipt, observed_at)
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
                    **provenance,
                }
            )
        return self._snapshot_result("ticker_spread", observed_at, records)

    def _collect_order_book_summary(self, observed_at: str) -> TaskCollectionResult:
        records = []
        for instrument_id in self.instruments:
            rows = self.client.order_book(instrument_id=instrument_id, depth=5)
            receipt = self._latest_receipt()
            provenance = self._provenance(receipt, observed_at)
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
                        **provenance,
                    }
                )
        return self._snapshot_result("order_book_summary", observed_at, records)

    def _funding_high_water(self) -> dict[str, int]:
        state = load_json(self.funding_state_path)
        high_water = {
            str(key): int(value)
            for key, value in (state.get("highWaterByInstrument") or {}).items()
        }
        for instrument_id in self.instruments:
            path_root = (
                self.layout.canonicalRoot
                / "okx"
                / "swap"
                / "funding"
                / instrument_id
            )
            for path in path_root.glob("funding-history-*.parquet"):
                try:
                    frame = pd.read_parquet(path, columns=["fundingTime"])
                except (OSError, ValueError, KeyError):
                    continue
                if not frame.empty:
                    high_water[instrument_id] = max(
                        high_water.get(instrument_id, -1),
                        int(frame["fundingTime"].max()),
                    )
        return high_water

    def _collect_funding_increment(self, observed_at: str) -> TaskCollectionResult:
        high_water = self._funding_high_water()
        new_rows: list[dict[str, Any]] = []
        for instrument_id in self.instruments:
            cursor: int | None = None
            known = high_water.get(instrument_id, -1)
            seen_oldest: set[int] = set()
            for _ in range(100):
                page = self.client.funding_rate_history(
                    instrument_id=instrument_id,
                    after_ms=cursor,
                    limit=100,
                )
                receipt = self._latest_receipt()
                if not page:
                    break
                normalized = normalize_funding_rows(
                    page,
                    instrument_id=instrument_id,
                    retrieved_at=str(receipt.get("requestCompletedAt") or observed_at),
                    source_hash=str(receipt["rawPayloadSha256"]),
                )
                for row in normalized:
                    if int(row["fundingTime"]) > known:
                        new_rows.append(
                            {
                                **row,
                                "sourceEndpoint": str(receipt["path"]),
                                "observedAt": observed_at,
                            }
                        )
                oldest = min(int(row["fundingTime"]) for row in page)
                if len(page) < 100 or oldest <= known or oldest in seen_oldest:
                    break
                seen_oldest.add(oldest)
                cursor = oldest
        deduplicated = {
            (str(row["instrumentId"]), int(row["fundingTime"])): row
            for row in new_rows
        }
        rows = [deduplicated[key] for key in sorted(deduplicated)]
        if not rows:
            return TaskCollectionResult(
                task_name="funding_increment",
                status="no_new_rows",
                observed_at=observed_at,
                artifact_path=None,
                artifact_sha256=None,
                row_count=0,
                source_timestamp=None,
                details={"highWaterByInstrument": high_water},
            )

        identity = stable_hash(rows, prefix="v34c_funding_increment")
        path = (
            self.layout.forwardCollectionRoot
            / "v34c"
            / "funding_increment"
            / observed_at[:10]
            / f"{identity}.parquet"
        )
        reused = path.is_file()
        if not reused:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix(".parquet.tmp")
            pd.DataFrame(rows).to_parquet(temporary, index=False, compression="zstd")
            temporary.replace(path)
        digest = sha256_file(path)
        for row in rows:
            instrument_id = str(row["instrumentId"])
            high_water[instrument_id] = max(
                high_water.get(instrument_id, -1), int(row["fundingTime"])
            )
        write_json_atomic(
            self.funding_state_path,
            {
                "schemaVersion": "okx_official_v1_v34c_funding_high_water_v1",
                "updatedAt": observed_at,
                "highWaterByInstrument": high_water,
            },
        )
        self._append_artifact_index(
            {
                "taskName": "funding_increment",
                "observedAt": observed_at,
                "path": str(path.resolve()),
                "sha256": digest,
                "rowCount": len(rows),
            }
        )
        return TaskCollectionResult(
            task_name="funding_increment",
            status="collected",
            observed_at=observed_at,
            artifact_path=str(path.resolve()),
            artifact_sha256=digest,
            row_count=len(rows),
            source_timestamp=max(str(row["retrievedAt"]) for row in rows),
            details={
                "artifactReused": reused,
                "highWaterByInstrument": high_water,
            },
        )
