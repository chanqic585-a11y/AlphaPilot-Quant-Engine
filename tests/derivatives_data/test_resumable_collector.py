from __future__ import annotations

import json

import pytest

from alphapilot.derivatives_data.resumable_collector import (
    CollectionBudgetExceeded,
    CollectorBudget,
    collect_resumable_pages,
)


def _record(timestamp: str, value: int) -> dict[str, object]:
    return {
        "exchange": "OKX",
        "instrumentId": "BTC-USDT-SWAP",
        "dataType": "funding",
        "timestampUtc": timestamp,
        "value": value,
    }


def test_collector_resumes_from_last_verified_cursor_and_deduplicates(tmp_path) -> None:
    checkpoint = tmp_path / "checkpoint.json"
    checkpoint.write_text(
        json.dumps({"lastVerifiedCursor": "cursor-1", "complete": False}),
        encoding="utf-8",
    )
    calls: list[str | None] = []

    def fetch_page(cursor: str | None) -> dict[str, object]:
        calls.append(cursor)
        return {
            "records": [
                _record("2026-01-01T00:00:00Z", 1),
                _record("2026-01-01T00:00:00Z", 2),
                _record("2026-01-01T08:00:00Z", 3),
            ],
            "nextCursor": None,
            "complete": True,
            "responseBytes": 300,
        }

    result = collect_resumable_pages(
        fetch_page=fetch_page,
        checkpoint_path=checkpoint,
        output_dir=tmp_path / "output",
        budget=CollectorBudget(
            maximum_requests_per_minute=30,
            maximum_retries=2,
            maximum_download_bytes=1_000,
            minimum_free_disk_bytes=100,
        ),
        free_disk_bytes=lambda _path: 10_000,
        sleep=lambda _seconds: None,
    )

    assert calls == ["cursor-1"]
    assert result["recordCount"] == 2
    assert result["duplicateCount"] == 1
    assert result["complete"] is True
    assert result["lastVerifiedCursor"] is None
    assert result["outputs"]["csvSha256"]
    assert result["outputs"]["jsonSha256"]


def test_collector_uses_bounded_retry_and_never_deletes_existing_output(tmp_path) -> None:
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    existing = output_dir / "records.json"
    existing.write_text('[{"kept":true}]\n', encoding="utf-8")
    attempts = 0

    def failing_fetch(_cursor: str | None) -> dict[str, object]:
        nonlocal attempts
        attempts += 1
        raise TimeoutError("temporary")

    with pytest.raises(TimeoutError):
        collect_resumable_pages(
            fetch_page=failing_fetch,
            checkpoint_path=tmp_path / "checkpoint.json",
            output_dir=output_dir,
            budget=CollectorBudget(30, 2, 1_000, 100),
            free_disk_bytes=lambda _path: 10_000,
            sleep=lambda _seconds: None,
        )
    assert attempts == 3
    assert existing.read_text(encoding="utf-8") == '[{"kept":true}]\n'


def test_collector_stops_before_disk_or_download_budget_is_exceeded(tmp_path) -> None:
    budget = CollectorBudget(30, 1, 100, 500)

    with pytest.raises(CollectionBudgetExceeded, match="free disk"):
        collect_resumable_pages(
            fetch_page=lambda _cursor: {},
            checkpoint_path=tmp_path / "checkpoint.json",
            output_dir=tmp_path / "output",
            budget=budget,
            free_disk_bytes=lambda _path: 499,
            sleep=lambda _seconds: None,
        )

    def oversized(_cursor: str | None) -> dict[str, object]:
        return {"records": [], "nextCursor": None, "complete": True, "responseBytes": 101}

    with pytest.raises(CollectionBudgetExceeded, match="download"):
        collect_resumable_pages(
            fetch_page=oversized,
            checkpoint_path=tmp_path / "checkpoint-2.json",
            output_dir=tmp_path / "output-2",
            budget=budget,
            free_disk_bytes=lambda _path: 10_000,
            sleep=lambda _seconds: None,
        )
