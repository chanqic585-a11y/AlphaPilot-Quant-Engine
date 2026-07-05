"""Exchange-aware feature-panel helpers for public local data.

The helpers wrap the existing derivative feature-panel builder and select a
local exchange data directory. They do not request exchange data, use API keys,
read accounts, create orders, or auto trade.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd

from alphapilot.derivatives.feature_panel import FeaturePanelResult, build_derivatives_feature_panel


DEFAULT_DATA_ROOT = Path("user_data/data")


@dataclass(frozen=True)
class ExchangeFeaturePanelResult:
    exchange: str
    data_dir: Path
    rows: pd.DataFrame
    loaded_pairs: list[str]
    missing_pairs: list[str]
    missing_optional_sources: dict[str, list[str]]


def get_exchange_futures_data_dir(exchange: str, data_root: Path = DEFAULT_DATA_ROOT) -> Path:
    return data_root / exchange / "futures"


def discover_exchange_pairs(exchange: str, timeframe: str = "4h", data_root: Path = DEFAULT_DATA_ROOT) -> list[str]:
    data_dir = get_exchange_futures_data_dir(exchange, data_root=data_root)
    suffix = f"-{timeframe}-futures.feather"
    pairs: list[str] = []
    for path in sorted(data_dir.glob(f"*{suffix}")):
        symbol = path.name.removesuffix(suffix)
        parts = symbol.split("_")
        if len(parts) >= 3 and parts[-2:] == ["USDT", "USDT"]:
            base = "_".join(parts[:-2])
            pairs.append(f"{base}/USDT:USDT")
    return pairs


def build_exchange_feature_panel(
    exchange: str,
    pairs: Iterable[str],
    timeframe: str = "4h",
    data_root: Path = DEFAULT_DATA_ROOT,
) -> ExchangeFeaturePanelResult:
    data_dir = get_exchange_futures_data_dir(exchange, data_root=data_root)
    panel: FeaturePanelResult = build_derivatives_feature_panel(pairs=pairs, timeframe=timeframe, data_dir=data_dir)
    rows = panel.rows.copy()
    if not rows.empty:
        rows["exchange"] = exchange
    return ExchangeFeaturePanelResult(
        exchange=exchange,
        data_dir=data_dir,
        rows=rows,
        loaded_pairs=panel.loaded_pairs,
        missing_pairs=panel.missing_pairs,
        missing_optional_sources=panel.missing_optional_sources,
    )


def build_multi_exchange_feature_panel(
    exchanges: Iterable[str],
    pairs: Iterable[str],
    timeframe: str = "4h",
    data_root: Path = DEFAULT_DATA_ROOT,
) -> tuple[pd.DataFrame, list[ExchangeFeaturePanelResult]]:
    results: list[ExchangeFeaturePanelResult] = []
    rows: list[pd.DataFrame] = []
    for exchange in exchanges:
        result = build_exchange_feature_panel(exchange, pairs=pairs, timeframe=timeframe, data_root=data_root)
        results.append(result)
        if not result.rows.empty:
            rows.append(result.rows)
    if not rows:
        return pd.DataFrame(), results
    return pd.concat(rows, ignore_index=True), results
