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


PRIMARY_KEY = ("exchange", "instrumentId", "dataType", "timestampUtc")


class CollectionBudgetExceeded(RuntimeError):
    """Raised before a collector writes output outside the frozen resource budget."""


@dataclass(frozen=True)
class CollectorBudget:
    maximum_requests_per_minute: int
    maximum_retries: int
    maximum_download_bytes: int
    minimum_free_disk_bytes: int

    def __post_init__(self) -> None:
        if min(
            self.maximum_requests_per_minute,
            self.maximum_download_bytes,
            self.minimum_free_disk_bytes,
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


def _record_key(record: Mapping[str, Any]) -> tuple[str, str, str, str]:
    missing = [field for field in PRIMARY_KEY if not record.get(field)]
    if missing:
        raise ValueError(f"record missing primary key fields: {', '.join(missing)}")
    return tuple(str(record[field]) for field in PRIMARY_KEY)  # type: ignore[return-value]


def deduplicate_records(records: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    duplicates = 0
    for record in records:
        key = _record_key(record)
        if key in unique:
            duplicates += 1
            continue
        unique[key] = dict(record)
    return [unique[key] for key in sorted(unique)], duplicates


def _load_checkpoint(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"lastVerifiedCursor": None, "complete": False}
    return json.loads(path.read_text(encoding="utf-8"))


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
) -> dict[str, Any]:
    free_disk_bytes = free_disk_bytes or (lambda path: shutil.disk_usage(path).free)
    disk_probe = output_dir if output_dir.exists() else output_dir.parent
    if free_disk_bytes(disk_probe) < budget.minimum_free_disk_bytes:
        raise CollectionBudgetExceeded("free disk budget is below minimumFreeDiskBytes")

    checkpoint = _load_checkpoint(checkpoint_path)
    cursor = checkpoint.get("lastVerifiedCursor")
    all_records: list[dict[str, Any]] = []
    downloaded_bytes = 0
    request_count = 0
    complete = bool(checkpoint.get("complete", False))
    if complete:
        return {
            "recordCount": 0,
            "duplicateCount": 0,
            "complete": True,
            "lastVerifiedCursor": cursor,
            "requestCount": 0,
            "downloadedBytes": 0,
            "outputs": {},
        }

    while not complete:
        last_error: Exception | None = None
        page: Mapping[str, Any] | None = None
        for attempt in range(budget.maximum_retries + 1):
            try:
                page = fetch_page(cursor)
                request_count += 1
                break
            except Exception as exc:  # bounded retry preserves the original exception type
                last_error = exc
                if attempt >= budget.maximum_retries:
                    raise
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
        _atomic_write(
            checkpoint_path,
            json.dumps(
                {
                    "lastVerifiedCursor": cursor,
                    "complete": complete,
                    "downloadedBytes": downloaded_bytes,
                    "requestCount": request_count,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
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
        "complete": complete,
        "lastVerifiedCursor": cursor,
        "requestCount": request_count,
        "downloadedBytes": downloaded_bytes,
        "outputs": {
            "json": str(json_path),
            "jsonSha256": _sha256(json_path),
            "csv": str(csv_path),
            "csvSha256": _sha256(csv_path),
        },
    }
