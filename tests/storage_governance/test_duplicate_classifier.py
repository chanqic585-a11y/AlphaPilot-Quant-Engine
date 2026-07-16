from pathlib import Path

import pandas as pd

import alphapilot.storage_governance.duplicate_classifier as duplicate_classifier
from alphapilot.storage_governance.duplicate_classifier import classify_duplicates
from alphapilot.storage_governance.reference_graph import build_reference_graph


def _write_parquet(path: Path, rows: int) -> None:
    frame = pd.DataFrame(
        {
            "timestamp_ms": [1_000 * index for index in range(rows)],
            "open": [float(index + 1) for index in range(rows)],
            "high": [float(index + 2) for index in range(rows)],
            "low": [float(index) for index in range(rows)],
            "close": [float(index + 1.5) for index in range(rows)],
            "volume": [100.0 + index for index in range(rows)],
            "confirmed": [1] * rows,
        }
    )
    frame.to_parquet(path, index=False)


def test_classifier_detects_byte_identical_files(tmp_path: Path) -> None:
    data_root = tmp_path / "data"
    data_root.mkdir()
    (data_root / "a.bin").write_bytes(b"same")
    (data_root / "b.bin").write_bytes(b"same")

    graph = build_reference_graph(data_root)
    result = classify_duplicates(graph, data_root=data_root)

    group = next(item for item in result["groups"] if item["duplicateClass"] == "byte_identical")
    assert len(group["members"]) == 2
    assert Path(group["authoritativePath"]).exists()


def test_classifier_only_supersedes_exact_parquet_prefix(tmp_path: Path) -> None:
    identity = tmp_path / "data" / "_alphapilot" / "canonical" / "okx" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "4h"
    identity.mkdir(parents=True)
    old = identity / "0-2000-old.parquet"
    latest = identity / "0-4000-latest.parquet"
    _write_parquet(old, 3)
    _write_parquet(latest, 5)

    graph = build_reference_graph(tmp_path / "data")
    result = classify_duplicates(graph, data_root=tmp_path / "data")

    group = next(item for item in result["groups"] if item["duplicateClass"] == "rolling_snapshot_superseded")
    assert group["authoritativePath"] == str(latest.resolve())
    assert group["members"] == [str(old.resolve())]
    assert group["contentVerified"] is True


def test_classifier_keeps_conflicting_parquet(tmp_path: Path) -> None:
    identity = tmp_path / "data" / "_alphapilot" / "canonical" / "okx" / "swap" / "ohlcv" / "BTC-USDT-SWAP" / "1h"
    identity.mkdir(parents=True)
    old = identity / "0-2000-old.parquet"
    latest = identity / "0-4000-latest.parquet"
    _write_parquet(old, 3)
    _write_parquet(latest, 5)
    changed = pd.read_parquet(old)
    changed.loc[1, "close"] = 999.0
    changed.to_parquet(old, index=False)

    graph = build_reference_graph(tmp_path / "data")
    result = classify_duplicates(graph, data_root=tmp_path / "data")

    assert any(
        item["duplicateClass"] == "conflicting" and str(old.resolve()) in item["members"]
        for item in result["groups"]
    )


def test_classifier_reads_group_authority_only_once(tmp_path: Path, monkeypatch) -> None:
    identity = tmp_path / "data" / "_alphapilot" / "canonical" / "okx" / "swap" / "ohlcv" / "ETH-USDT-SWAP" / "4h"
    identity.mkdir(parents=True)
    first = identity / "0-1000-first.parquet"
    second = identity / "0-2000-second.parquet"
    authority = identity / "0-4000-authority.parquet"
    _write_parquet(first, 2)
    _write_parquet(second, 3)
    _write_parquet(authority, 5)
    graph = build_reference_graph(tmp_path / "data")
    original = duplicate_classifier._table_profile
    calls: list[str] = []

    def counted(path: Path):
        calls.append(str(path.resolve()))
        return original(path)

    monkeypatch.setattr(duplicate_classifier, "_table_profile", counted)

    classify_duplicates(graph, data_root=tmp_path / "data")

    assert calls.count(str(authority.resolve())) == 1
