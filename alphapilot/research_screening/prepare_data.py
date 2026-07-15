"""Explicit Phase 3B data preparation. Formal result runs never call this collector."""

from __future__ import annotations

import argparse
import json
import time
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

import pandas as pd
import pyarrow.parquet as pq

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .data_contracts import DatasetManifest, verify_manifest


DEFAULT_DATA_ROOT = Path(r"D:\Codex-Workspace\回测数据")
RESEARCH_INSTRUMENTS = (
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "XRP-USDT-SWAP",
    "LTC-USDT-SWAP",
    "BCH-USDT-SWAP",
    "ETC-USDT-SWAP",
    "ADA-USDT-SWAP",
    "LINK-USDT-SWAP",
)
RESEARCH_TIMEFRAMES = ("1h", "4h", "1d")
BINANCE_FUNDING_URL = "https://fapi.binance.com/fapi/v1/fundingRate"


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _binance_symbol(instrument_id: str) -> str:
    return instrument_id.removesuffix("-SWAP").replace("-", "")


def select_canonical_ohlcv(canonical_root: Path | str, instrument_id: str, timeframe: str) -> Path:
    base = Path(canonical_root) / "user_local" / "swap" / "ohlcv" / instrument_id / timeframe
    candidates = list(base.glob("*.parquet"))
    if not candidates:
        raise FileNotFoundError(f"missing canonical OHLCV: {instrument_id} {timeframe}")
    return max(candidates, key=lambda path: (pq.ParquetFile(path).metadata.num_rows, path.name))


def _fetch_binance_page(symbol: str, start_ms: int, end_ms: int) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {"symbol": symbol, "startTime": start_ms, "endTime": end_ms, "limit": 1000}
    )
    request = urllib.request.Request(
        f"{BINANCE_FUNDING_URL}?{query}",
        headers={"User-Agent": "AlphaPilot-Research/Phase3B"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS host.
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError("unexpected Binance funding response")
    return payload


def collect_binance_funding(
    *,
    instrument_id: str,
    output_path: Path | str,
    start_ms: int,
    end_ms: int,
    fetch_page: Callable[[str, int, int], list[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    output = Path(output_path)
    if output.is_file():
        existing = json.loads(output.read_text(encoding="utf-8"))
        if int(existing.get("startMs", -1)) <= start_ms and int(existing.get("completeThroughMs", -1)) >= end_ms:
            return {"records": len(existing.get("data", [])), "reused": True, "path": str(output)}
    fetch = fetch_page or _fetch_binance_page
    cursor = start_ms
    records: dict[int, dict[str, Any]] = {}
    while cursor <= end_ms:
        page = fetch(_binance_symbol(instrument_id), cursor, end_ms)
        if not page:
            break
        for item in page:
            timestamp = int(item["fundingTime"])
            if start_ms <= timestamp <= end_ms:
                records[timestamp] = {
                    "fundingTime": timestamp,
                    "fundingRate": str(item["fundingRate"]),
                }
        next_cursor = max(int(item["fundingTime"]) for item in page) + 1
        if next_cursor <= cursor:
            raise RuntimeError("funding pagination did not advance")
        cursor = next_cursor
        if fetch_page is None:
            time.sleep(0.08)
    output.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        output,
        {
            "schemaVersion": "binance_public_funding_raw_v1",
            "provider": "binance_public_rest",
            "sourceUrl": BINANCE_FUNDING_URL,
            "instrumentId": instrument_id,
            "startMs": start_ms,
            "completeThroughMs": end_ms,
            "collectedAt": _utc_now(),
            "licenseOrUsageNote": "Public market data; Binance API terms apply; no credentials used.",
            "data": [records[key] for key in sorted(records)],
        },
    )
    return {"records": len(records), "reused": False, "path": str(output)}


def normalize_funding(raw_path: Path | str, output_path: Path | str) -> Path:
    raw = json.loads(Path(raw_path).read_text(encoding="utf-8"))
    frame = pd.DataFrame(raw.get("data", []))
    if frame.empty:
        raise ValueError(f"funding data is empty: {raw_path}")
    frame["timestampUtc"] = pd.to_datetime(frame["fundingTime"].astype("int64"), unit="ms", utc=True)
    frame["sourceTimestamp"] = frame["timestampUtc"]
    frame["instrumentId"] = raw["instrumentId"]
    frame["fundingRate"] = frame["fundingRate"].astype(float)
    frame["exchange"] = "binance"
    frame["marketType"] = "swap"
    normalized = frame[
        ["timestampUtc", "sourceTimestamp", "exchange", "marketType", "instrumentId", "fundingRate"]
    ].drop_duplicates(["timestampUtc", "instrumentId"]).sort_values("timestampUtc")
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp.parquet")
    normalized.to_parquet(temporary, index=False, compression="zstd")
    temporary.replace(output)
    return output


def _parquet_identity(path: Path, date_column: str) -> tuple[str, str, int]:
    frame = pd.read_parquet(path, columns=[date_column])
    dates = pd.to_datetime(frame[date_column], utc=True)
    return dates.min().isoformat(), dates.max().isoformat(), len(frame)


def _manifest_for_ohlcv(path: Path, instrument: str, timeframe: str) -> DatasetManifest:
    start, end, rows = _parquet_identity(path, "date")
    return DatasetManifest.from_file(
        path,
        dataset_id=f"user_local_{instrument}_{timeframe}",
        data_type="ohlcv",
        provider="user_confirmed_local_history",
        exchange="unverified_local_exchange",
        market_type="swap",
        symbols=(instrument,),
        timeframe=timeframe,
        start_time=start,
        end_time=end,
        row_count=rows,
        is_point_in_time=False,
        is_proxy=True,
        license_or_usage_note="User-provided local history; exchange provenance is not independently verified.",
    )


def _manifest_for_funding(path: Path, instrument: str) -> DatasetManifest:
    start, end, rows = _parquet_identity(path, "timestampUtc")
    return DatasetManifest.from_file(
        path,
        dataset_id=f"binance_{instrument}_funding",
        data_type="funding",
        provider="binance_public_rest",
        exchange="binance",
        market_type="swap",
        symbols=(instrument,),
        timeframe=None,
        start_time=start,
        end_time=end,
        row_count=rows,
        is_point_in_time=True,
        is_proxy=False,
        license_or_usage_note="Public market data; Binance API terms apply; no credentials used.",
    )


def _source_audit(funding_ready: bool) -> list[dict[str, Any]]:
    return [
        {"dataType": "OHLCV", "status": "ready_proxy", "realOrProxy": "proxy", "reason": "local history exchange provenance unverified"},
        {"dataType": "VWAP / Amount", "status": "derived", "realOrProxy": "proxy", "reason": "derived from OHLCV"},
        {"dataType": "perpetual volume", "status": "ready_proxy", "realOrProxy": "proxy", "reason": "local swap OHLCV volume"},
        {"dataType": "Funding", "status": "ready" if funding_ready else "unavailable", "realOrProxy": "real", "reason": "Binance public funding history"},
        {"dataType": "Open Interest", "status": "unavailable", "realOrProxy": "unavailable", "reason": "not present in frozen snapshot"},
        {"dataType": "spot price", "status": "available_not_selected", "realOrProxy": "proxy", "reason": "local spot files exist but are not used in first campaign"},
        {"dataType": "perpetual price", "status": "ready_proxy", "realOrProxy": "proxy", "reason": "local swap close"},
        {"dataType": "Basis", "status": "unavailable", "realOrProxy": "unavailable", "reason": "synchronized spot/perpetual basis not frozen"},
        {"dataType": "liquidation", "status": "unavailable", "realOrProxy": "unavailable", "reason": "no real liquidation series"},
        {"dataType": "liquidation proxy", "status": "available_diagnostic", "realOrProxy": "proxy", "reason": "range-volume shock only; not real liquidation"},
        {"dataType": "spread / slippage / depth", "status": "available_diagnostic", "realOrProxy": "proxy", "reason": "OHLCV range proxy; no historical L2"},
        {"dataType": "Point-in-Time universe", "status": "diagnostic_proxy", "realOrProxy": "proxy", "reason": "fixed continuously covered instruments; listing-state history incomplete"},
        {"dataType": "market breadth", "status": "derived", "realOrProxy": "proxy", "reason": "derived from frozen universe returns"},
        {"dataType": "BTC / ETH benchmark", "status": "ready_proxy", "realOrProxy": "proxy", "reason": "local BTC and ETH OHLCV"},
        {"dataType": "category / correlation cluster", "status": "derived", "realOrProxy": "proxy", "reason": "deterministic return-correlation clusters"},
    ]


def prepare_phase3b_data(
    *,
    data_root: Path | str,
    repo_root: Path | str,
    collect: bool,
) -> dict[str, Any]:
    root = Path(data_root).resolve()
    repo = Path(repo_root).resolve()
    raw_root = root / "raw"
    normalized_root = root / "normalized"
    derived_root = root / "derived"
    manifests_root = root / "manifests"
    snapshots_root = root / "snapshots"
    for path in (raw_root, normalized_root, derived_root, manifests_root, snapshots_root):
        path.mkdir(parents=True, exist_ok=True)
    canonical_root = root / "_alphapilot" / "canonical"
    start_ms = int(datetime(2020, 1, 1, tzinfo=UTC).timestamp() * 1000)
    end_ms = int(datetime.now(UTC).timestamp() * 1000)

    funding_paths: dict[str, Path] = {}
    funding_collection: list[dict[str, Any]] = []
    for instrument in RESEARCH_INSTRUMENTS:
        raw_path = raw_root / "binance" / "swap" / "funding" / f"{instrument}.json"
        normalized_path = normalized_root / "binance" / "swap" / "funding" / f"{instrument}.parquet"
        if collect or raw_path.is_file():
            if collect:
                funding_collection.append(
                    {"instrumentId": instrument, **collect_binance_funding(instrument_id=instrument, output_path=raw_path, start_ms=start_ms, end_ms=end_ms)}
                )
            if raw_path.is_file():
                funding_paths[instrument] = normalize_funding(raw_path, normalized_path)

    ohlcv_paths: dict[str, dict[str, Path]] = {}
    manifests: list[DatasetManifest] = []
    for timeframe in RESEARCH_TIMEFRAMES:
        ohlcv_paths[timeframe] = {}
        for instrument in RESEARCH_INSTRUMENTS:
            path = select_canonical_ohlcv(canonical_root, instrument, timeframe)
            ohlcv_paths[timeframe][instrument] = path
            manifests.append(_manifest_for_ohlcv(path, instrument, timeframe))
    for instrument, path in sorted(funding_paths.items()):
        manifests.append(_manifest_for_funding(path, instrument))

    manifest_records = [item.to_dict() for item in manifests]
    manifest_verified = all(verify_manifest(item) for item in manifests)
    manifest_core = {
        "schemaVersion": "phase3b_dataset_catalog_v1",
        "generatedAt": _utc_now(),
        "formalResultRunsMustBeOffline": True,
        "datasets": manifest_records,
    }
    manifest_hash = stable_hash(manifest_core, prefix="data_manifest")
    manifest_payload = {**manifest_core, "dataManifestHash": manifest_hash, "verified": manifest_verified}
    write_json_atomic(manifests_root / "phase3b_dataset_catalog.json", manifest_payload)

    source_audit = _source_audit(len(funding_paths) == len(RESEARCH_INSTRUMENTS))
    write_json_atomic(manifests_root / "phase3b_data_source_audit.json", {"schemaVersion": "phase3b_data_source_audit_v1", "sources": source_audit})
    repo_readiness = repo / "reports" / "backtest_screening" / "data_readiness"
    repo_readiness.mkdir(parents=True, exist_ok=True)
    write_json_atomic(repo_readiness / "data_source_audit.json", {"schemaVersion": "phase3b_data_source_audit_v1", "sources": source_audit})
    write_json_atomic(repo_readiness / "dataset_catalog.json", manifest_payload)

    snapshot_core = {
        "schemaVersion": "phase3b_data_snapshot_v1",
        "dataManifestHash": manifest_hash,
        "datasetContentHashes": sorted(item.contentHash for item in manifests),
        "instruments": list(RESEARCH_INSTRUMENTS),
        "timeframes": list(RESEARCH_TIMEFRAMES),
        "pitStatus": "diagnostic_proxy",
        "pitReason": "Historical listing, delisting, suspension, and liquidity snapshots are incomplete; cross-sectional outputs remain diagnostic.",
        "resultRunNetworkPolicy": "offline_required",
    }
    snapshot_id = stable_hash(snapshot_core, prefix="data_snapshot")
    snapshot = {**snapshot_core, "snapshotId": snapshot_id, "createdAt": _utc_now()}
    write_json_atomic(snapshots_root / f"{snapshot_id}.json", snapshot)
    repo_snapshot = repo / "research" / "data_snapshots" / f"{snapshot_id}.json"
    repo_snapshot.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(repo_snapshot, snapshot)
    return {
        "snapshot": snapshot,
        "manifest": manifest_payload,
        "sourceAudit": source_audit,
        "ohlcvPaths": {timeframe: {instrument: str(path) for instrument, path in paths.items()} for timeframe, paths in ohlcv_paths.items()},
        "fundingPaths": {instrument: str(path) for instrument, path in funding_paths.items()},
        "fundingCollection": funding_collection,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--collect", action="store_true")
    args = parser.parse_args()
    result = prepare_phase3b_data(data_root=args.data_root, repo_root=args.repo_root, collect=args.collect)
    print(json.dumps({"snapshotId": result["snapshot"]["snapshotId"], "manifestHash": result["manifest"]["dataManifestHash"], "datasetCount": len(result["manifest"]["datasets"]), "fundingDatasetCount": len(result["fundingPaths"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
