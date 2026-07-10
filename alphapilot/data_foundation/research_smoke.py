"""Implementation smoke checks over third-party local historical files."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.workflow.types import StrategyDataContractRecord

from .catalog import discover_raw_assets
from .checkpoint import write_json_atomic
from .quality import inspect_quality
from .readers import clean_ohlcv_frame
from .types import RawDataAsset
from .warehouse import WarehouseLayout


RESEARCH_SMOKE_SCHEMA_VERSION = "research_smoke_v1"
PREFERRED_SYMBOLS = ("BTC", "ETH", "SOL")
MAX_SMOKE_SYMBOLS = 5
MAX_SAMPLE_ROWS = 5_000
MINIMUM_WARMUP_ROWS = 200


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _sample_ohlcv(path: Path, *, max_rows: int = MAX_SAMPLE_ROWS):
    suffix = path.suffix.lower()
    if suffix == ".csv":
        raw = pd.read_csv(path, nrows=max_rows)
    elif suffix == ".xlsx":
        raw = pd.read_excel(path, nrows=max_rows)
    else:
        raise ValueError(f"unsupported_smoke_format:{suffix or 'missing'}")
    return clean_ohlcv_frame(raw)


def _required_timeframes(contract: dict[str, Any]) -> set[str]:
    return {
        str(value)
        for value in (
            contract.get("signalTimeframe"),
            contract.get("executionTimeframe"),
            contract.get("executionFallbackTimeframe"),
        )
        if value
    }


def _select_assets(
    assets: list[RawDataAsset], contract: dict[str, Any]
) -> list[RawDataAsset]:
    required_timeframes = _required_timeframes(contract)
    market_type = str(contract.get("marketType") or "")
    eligible = [
        asset
        for asset in assets
        if asset.selected
        and asset.dataKind == "ohlcv"
        and asset.timeframe in required_timeframes
        and asset.marketType in {market_type, "unknown"}
        and asset.symbol
    ]
    symbol_rank = {
        symbol: index for index, symbol in enumerate(PREFERRED_SYMBOLS)
    }
    eligible.sort(
        key=lambda asset: (
            symbol_rank.get(str(asset.symbol), len(symbol_rank)),
            str(asset.symbol),
            str(asset.timeframe),
            asset.relativePath,
        )
    )
    selected_symbols: set[str] = set()
    selected: list[RawDataAsset] = []
    for asset in eligible:
        symbol = str(asset.symbol)
        if symbol not in selected_symbols and len(selected_symbols) >= MAX_SMOKE_SYMBOLS:
            continue
        selected_symbols.add(symbol)
        selected.append(asset)
    return selected


def run_research_smoke(
    contract: StrategyDataContractRecord,
    layout: WarehouseLayout,
    output_path: Path | str,
) -> dict[str, Any]:
    layout.ensure_directories()
    assets = _select_assets(
        discover_raw_assets(layout.rawRoot), contract.contract
    )
    asset_rows: list[dict[str, Any]] = []
    blockers: list[str] = []
    if not assets:
        blockers.append("local_research_assets_missing")
    for asset in assets:
        source = Path(asset.sourcePath)
        try:
            read_result = _sample_ohlcv(source)
            quality = inspect_quality(read_result, str(asset.timeframe))
            valid = not quality.errors and quality.rows >= MINIMUM_WARMUP_ROWS
            row_blockers = list(quality.errors)
            if quality.rows < MINIMUM_WARMUP_ROWS:
                row_blockers.append("insufficient_indicator_warmup_rows")
            if not valid:
                blockers.extend(
                    f"{asset.relativePath}:{value}" for value in row_blockers
                )
            asset_rows.append(
                {
                    "relativePath": asset.relativePath,
                    "symbol": asset.symbol,
                    "marketType": asset.marketType,
                    "timeframe": asset.timeframe,
                    "sourceProvenance": "third_party_unverified",
                    "sourceSha256": sha256_file(source),
                    "implementationValid": valid,
                    "quality": quality.to_dict(),
                    "blockers": row_blockers,
                }
            )
        except Exception as error:
            blocker = f"{asset.relativePath}:smoke_read_failed:{type(error).__name__}"
            blockers.append(blocker)
            asset_rows.append(
                {
                    "relativePath": asset.relativePath,
                    "symbol": asset.symbol,
                    "marketType": asset.marketType,
                    "timeframe": asset.timeframe,
                    "sourceProvenance": "third_party_unverified",
                    "sourceSha256": sha256_file(source),
                    "implementationValid": False,
                    "quality": None,
                    "blockers": [blocker],
                }
            )
    implementation_valid = bool(asset_rows) and not blockers
    core = {
        "schemaVersion": RESEARCH_SMOKE_SCHEMA_VERSION,
        "strategyDataContractId": contract.strategyDataContractId,
        "strategyVersionId": contract.strategyVersionId,
        "status": "completed" if implementation_valid else "blocked",
        "implementationValid": implementation_valid,
        "evidenceClass": "research_smoke",
        "formalPromotionEligible": False,
        "sourceProvenance": "third_party_unverified",
        "selectedAssetCount": len(asset_rows),
        "assets": asset_rows,
        "blockers": sorted(set(blockers)),
        "generatedAt": _utc_now(),
    }
    report = {**core, "reportHash": stable_hash(core, prefix="research_smoke")}
    write_json_atomic(Path(output_path), report)
    return report
