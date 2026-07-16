from __future__ import annotations

import json

from alphapilot.derivatives_data.checkpoint_store import (
    load_collection_checkpoint,
    write_collection_checkpoint,
)


def test_checkpoint_store_writes_atomically_and_preserves_cumulative_counters(tmp_path) -> None:
    path = tmp_path / "checkpoint.json"
    write_collection_checkpoint(
        path,
        {
            "lastVerifiedCursor": "cursor-2",
            "complete": False,
            "totalRequestCount": 12,
            "totalDownloadedBytes": 345,
        },
    )

    assert not path.with_suffix(".json.partial").exists()
    assert load_collection_checkpoint(path) == json.loads(path.read_text("utf-8"))


def test_checkpoint_store_rejects_non_object_payload(tmp_path) -> None:
    path = tmp_path / "checkpoint.json"
    path.write_text("[]", encoding="utf-8")

    try:
        load_collection_checkpoint(path)
    except ValueError as error:
        assert "JSON object" in str(error)
    else:
        raise AssertionError("invalid checkpoint was accepted")
