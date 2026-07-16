"""Small, fail-closed building blocks for resumable public-data collection."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alphapilot.derivatives_data.checkpoint_store import (
    load_collection_checkpoint,
    scan_existing_partitions,
    write_collection_checkpoint,
)
from alphapilot.derivatives_data.deduplication import (
    PRIMARY_KEY,
    deduplicate_records as _deduplicate_records,
)

class CollectionBudgetExceeded(RuntimeError):
    """Raised before a collector writes output outside the frozen resource budget."""


@dataclass(frozen=True)
class CollectorBudget:
    maximum_requests_per_minute: int
    maximum_retries: int
    maximum_download_bytes: int
    minimum_free_disk_bytes: int
    maximum_total_requests: int = 10_000
    maximum_run_hours: float = 24.0

    def __post_init__(self) -> None:
        if min(
            self.maximum_requests_per_minute,
            self.maximum_download_bytes,
            self.minimum_free_disk_bytes,
            self.maximum_total_requests,
            self.maximum_run_hours,
        ) <= 0:
            raise ValueError("collector budgets must be positive")
        if self.maximum_retries < 0:
            raise ValueError("maximum_retries cannot be negative")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".partial")
    temporary.write_text(content, encoding="utf-8", newline="")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def deduplicate_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    rows, report = _deduplicate_records(records)
    return rows, int(report["duplicateRecordCount"])


def _csv_text(records: list[dict[str, Any]]) -> str:
    if not records:
        return ""
    fields = sorted({field for record in records for field in record})
    from io import StringIO

    stream = StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow(
            {
                field: (
                    json.dumps(record.get(field), ensure_ascii=False, sort_keys=True)
                    if isinstance(record.get(field), (dict, list))
                    else record.get(field)
                )
                for field in fields
            }
        )
    return stream.getvalue()


def collect_resumable_pages(
    *,
    fetch_page: Callable[[str | None], Mapping[str, Any]],
    checkpoint_path: Path,
    output_dir: Path,
    budget: CollectorBudget,
    free_disk_bytes: Callable[[Path], int] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    monotonic: Callable[[], float] = time.monotonic,
) -> dict[str, Any]:
    free_disk_bytes = free_disk_bytes or (lambda path: shutil.disk_usage(path).free)
    disk_probe = output_dir if output_dir.exists() else output_dir.parent
    if free_disk_bytes(disk_probe) < budget.minimum_free_disk_bytes:
        raise CollectionBudgetExceeded("free disk budget is below minimumFreeDiskBytes")

    stale_partial = output_dir / "records.json.partial"
    if stale_partial.exists():
        raise ValueError(f"partial output requires validation before resume: {stale_partial}")

    checkpoint = load_collection_checkpoint(checkpoint_path)
    cursor = checkpoint.get("lastVerifiedCursor")
    existing_json = output_dir / "records.json"
    existing_records: list[dict[str, Any]] = []
    if existing_json.is_file():
        payload = json.loads(existing_json.read_text(encoding="utf-8"))
        if not isinstance(payload, list):
            raise ValueError("existing records.json must contain a JSON array")
        existing_records = [dict(row) for row in payload]
    all_records: list[dict[str, Any]] = list(existing_records)
    downloaded_bytes = 0
    request_count = 0
    retry_count = 0
    started_at = monotonic()
    complete = bool(checkpoint.get("complete", False))
    if complete:
        outputs: dict[str, str] = {}
        csv_path = output_dir / "records.csv"
        if existing_json.is_file():
            outputs.update({"json": str(existing_json), "jsonSha256": _sha256(existing_json)})
        if csv_path.is_file():
            outputs.update({"csv": str(csv_path), "csvSha256": _sha256(csv_path)})
        return {
            "recordCount": len(existing_records),
            "duplicateCount": 0,
            "reusedRecordCount": len(existing_records),
            "complete": True,
            "lastVerifiedCursor": cursor,
            "requestCount": 0,
            "retryCount": 0,
            "downloadedBytes": 0,
            "outputs": outputs,
        }

    while not complete:
        if monotonic() - started_at > budget.maximum_run_hours * 3600:
            raise CollectionBudgetExceeded("run budget exceeded maximumRunHours")
        last_error: Exception | None = None
        page: Mapping[str, Any] | None = None
        for attempt in range(budget.maximum_retries + 1):
            if request_count >= budget.maximum_total_requests:
                raise CollectionBudgetExceeded("request budget reached maximumTotalRequests")
            if monotonic() - started_at > budget.maximum_run_hours * 3600:
                raise CollectionBudgetExceeded("run budget exceeded maximumRunHours")
            request_count += 1
            try:
                page = fetch_page(cursor)
                break
            except Exception as exc:  # bounded retry preserves the original exception type
                last_error = exc
                if attempt >= budget.maximum_retries:
                    raise
                retry_count += 1
                sleep(min(2**attempt, 30))
        if page is None:
            assert last_error is not None
            raise last_error

        page_bytes = int(page.get("responseBytes") or len(json.dumps(page).encode("utf-8")))
        if downloaded_bytes + page_bytes > budget.maximum_download_bytes:
            raise CollectionBudgetExceeded("download budget would exceed maximumDownloadBytes")
        downloaded_bytes += page_bytes
        records = page.get("records") or []
        if not isinstance(records, list):
            raise ValueError("page records must be a list")
        all_records.extend(dict(row) for row in records)
        complete = bool(page.get("complete", False))
        next_cursor = page.get("nextCursor")
        if not complete and next_cursor == cursor:
            raise ValueError("collector cursor did not advance")
        cursor = str(next_cursor) if next_cursor is not None else None
        write_collection_checkpoint(
            checkpoint_path,
            {
                "lastVerifiedCursor": cursor,
                "complete": complete,
                "totalDownloadedBytes": int(checkpoint.get("totalDownloadedBytes", 0))
                + downloaded_bytes,
                "totalRequestCount": int(checkpoint.get("totalRequestCount", 0)) + request_count,
                "totalRetryCount": int(checkpoint.get("totalRetryCount", 0)) + retry_count,
                "resumeCount": int(checkpoint.get("resumeCount", 0)) + 1,
            },
        )
        if not complete:
            sleep(60 / budget.maximum_requests_per_minute)

    records, duplicate_count = deduplicate_records(all_records)
    json_path = output_dir / "records.json"
    csv_path = output_dir / "records.csv"
    _atomic_write(
        json_path,
        json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(csv_path, _csv_text(records))
    return {
        "recordCount": len(records),
        "duplicateCount": duplicate_count,
        "reusedRecordCount": len(existing_records),
        "complete": complete,
        "lastVerifiedCursor": cursor,
        "requestCount": request_count,
        "retryCount": retry_count,
        "downloadedBytes": downloaded_bytes,
        "outputs": {
            "json": str(json_path),
            "jsonSha256": _sha256(json_path),
            "csv": str(csv_path),
            "csvSha256": _sha256(csv_path),
        },
    }
