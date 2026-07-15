from pathlib import Path

from alphapilot.research_screening.data_contracts import DatasetManifest, verify_manifest


def test_dataset_manifest_is_content_addressed(tmp_path: Path) -> None:
    source = tmp_path / "sample.parquet"
    source.write_bytes(b"immutable-sample")
    manifest = DatasetManifest.from_file(
        source,
        dataset_id="sample_1d",
        data_type="ohlcv",
        provider="fixture",
        exchange="fixture",
        market_type="swap",
        symbols=("BTC-USDT-SWAP",),
        timeframe="1d",
        start_time="2024-01-01T00:00:00+00:00",
        end_time="2024-01-02T00:00:00+00:00",
        row_count=2,
        is_point_in_time=False,
        is_proxy=True,
        license_or_usage_note="test fixture",
    )

    assert manifest.timezone == "UTC"
    assert manifest.contentHash
    assert verify_manifest(manifest)
    source.write_bytes(b"changed")
    assert not verify_manifest(manifest)
