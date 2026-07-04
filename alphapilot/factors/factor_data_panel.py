"""Build the V13.4.21 FactorDataPanel from local OHLCV.

This module is research-only. It reads local public OHLCV files and optional
historical dynamic universe snapshots. It does not download data, run a
backtest, enter Dry-run, call exchange APIs, read accounts, create orders, or
auto trade.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.factors.factor_schema import FactorDataPanelConfig
from alphapilot.factors.ohlcv_loader import OhlcvLoadReport, load_local_ohlcv


@dataclass
class FactorDataPanelBuild:
    panel: pd.DataFrame
    loadReport: OhlcvLoadReport
    warnings: list[str]
    universeMembershipAvailable: bool
    universeMembershipSource: str
    dynamicUniverseSnapshotsUsed: int


def _round_float(value: Any, digits: int = 10) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _load_dynamic_universe(path: str | None) -> tuple[dict[str, set[str]], list[str], bool, int]:
    if not path:
        return {}, ["Dynamic universe snapshots path was not provided."], False, 0
    snapshot_path = Path(path)
    if not snapshot_path.exists():
        return {}, [f"Dynamic universe snapshots not found: {snapshot_path.as_posix()}"], False, 0
    try:
        snapshots = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {}, [f"Dynamic universe snapshots could not be parsed: {exc}"], False, 0
    membership: dict[str, set[str]] = {}
    for snapshot in snapshots:
        date_key = snapshot.get("snapshotDate")
        selected_pairs = snapshot.get("selectedPairs", [])
        if isinstance(date_key, str) and isinstance(selected_pairs, list):
            membership[date_key] = {str(pair) for pair in selected_pairs}
    if not membership:
        return {}, ["Dynamic universe snapshots contained no selected pair membership."], False, len(snapshots)
    return membership, [], True, len(snapshots)


def _bucket_by_pair_average(panel: pd.DataFrame, field_name: str, output_field: str) -> pd.DataFrame:
    averages = panel.groupby("pair")[field_name].mean(numeric_only=True).sort_values()
    if averages.empty:
        panel[output_field] = "unknown"
        return panel
    pairs = list(averages.index)
    labels: dict[str, str] = {}
    for idx, pair in enumerate(pairs):
        percentile = (idx + 1) / len(pairs)
        if percentile <= 1 / 3:
            labels[pair] = "low"
        elif percentile <= 2 / 3:
            labels[pair] = "medium"
        else:
            labels[pair] = "high"
    panel[output_field] = panel["pair"].map(labels).fillna("unknown")
    return panel


def _regime_label(market_return: float | None, volatility_bucket: str) -> str:
    if market_return is None:
        return "unknown"
    if volatility_bucket == "high" and abs(market_return) < 0.002:
        return "volatile_range"
    if market_return > 0.003:
        return "trend_up"
    if market_return < -0.003:
        return "trend_down"
    return "range"


def build_factor_data_panel(config: FactorDataPanelConfig) -> FactorDataPanelBuild:
    loaded = load_local_ohlcv(config)
    warnings = list(loaded.report.warnings)
    if not loaded.frames:
        return FactorDataPanelBuild(
            panel=pd.DataFrame(),
            loadReport=loaded.report,
            warnings=warnings,
            universeMembershipAvailable=False,
            universeMembershipSource="unavailable",
            dynamicUniverseSnapshotsUsed=0,
        )

    frames: list[pd.DataFrame] = []
    for pair, frame in loaded.frames.items():
        pair_frame = frame.copy()
        pair_frame = pair_frame.sort_values("date")
        pair_frame["quoteVolume"] = pair_frame["close"] * pair_frame["volume"]
        pair_frame["quoteVolumeEstimated"] = True
        pair_frame["vwap"] = (pair_frame["high"] + pair_frame["low"] + pair_frame["close"]) / 3
        pair_frame["vwapEstimated"] = True
        for periods in (1, 3, 6, 12):
            pair_frame[f"returns_{periods}"] = pair_frame["close"].pct_change(periods=periods)
        pair_frame["pair"] = pair
        frames.append(pair_frame)

    panel = pd.concat(frames, ignore_index=True).sort_values(["date", "pair"]).reset_index(drop=True)
    market_returns = panel.groupby("date")["returns_1"].mean(numeric_only=True)
    panel["marketReturn"] = panel["date"].map(market_returns)

    btc_rows = panel[panel["pair"] == "BTC/USDT:USDT"].set_index("date")
    if not btc_rows.empty:
        panel["btcReturn"] = panel["date"].map(btc_rows["returns_1"])
        panel["btcReturn_12"] = panel["date"].map(btc_rows["returns_12"])
    else:
        panel["btcReturn"] = None
        panel["btcReturn_12"] = None
        warnings.append("BTC/USDT:USDT was not loaded, so btcReturn fields are unavailable.")

    panel["rollingVolatility24h"] = panel.groupby("pair")["returns_1"].transform(lambda values: values.rolling(24, min_periods=6).std(ddof=0))
    panel = _bucket_by_pair_average(panel, "quoteVolume", "liquidityBucket")
    panel = _bucket_by_pair_average(panel, "rollingVolatility24h", "volatilityBucket")
    panel["regimeLabel"] = [
        _regime_label(_round_float(row.marketReturn), str(row.volatilityBucket))
        for row in panel[["marketReturn", "volatilityBucket"]].itertuples(index=False)
    ]

    dynamic_membership: dict[str, set[str]] = {}
    universe_available = False
    universe_source = "local_loaded_pairs_fallback"
    snapshots_used = 0
    if config.useDynamicUniverse:
        dynamic_membership, universe_warnings, universe_available, snapshots_used = _load_dynamic_universe(config.universeSnapshotsPath)
        warnings.extend(universe_warnings)
        universe_source = "historical_dynamic_universe_v13_4_13" if universe_available else "unavailable"

    panel["snapshotDate"] = panel["date"].dt.strftime("%Y-%m-%d")
    if universe_available:
        panel["universeMember"] = [
            str(row.pair) in dynamic_membership.get(str(row.snapshotDate), set())
            for row in panel[["pair", "snapshotDate"]].itertuples(index=False)
        ]
        panel["universeMembershipSource"] = universe_source
    else:
        panel["universeMember"] = True
        panel["universeMembershipSource"] = universe_source
        if config.useDynamicUniverse:
            warnings.append("Dynamic universe membership was requested but unavailable; rows use local loaded pair fallback membership.")
        else:
            warnings.append("Dynamic universe membership not requested; rows use local loaded pair fallback membership.")

    panel["timestamp"] = panel["date"].dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")
    ordered_columns = [
        "timestamp",
        "pair",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "quoteVolume",
        "quoteVolumeEstimated",
        "vwap",
        "vwapEstimated",
        "returns_1",
        "returns_3",
        "returns_6",
        "returns_12",
        "marketReturn",
        "btcReturn",
        "btcReturn_12",
        "universeMember",
        "universeMembershipSource",
        "regimeLabel",
        "liquidityBucket",
        "volatilityBucket",
    ]
    panel = panel[ordered_columns]
    return FactorDataPanelBuild(
        panel=panel,
        loadReport=loaded.report,
        warnings=warnings,
        universeMembershipAvailable=universe_available,
        universeMembershipSource=universe_source,
        dynamicUniverseSnapshotsUsed=snapshots_used,
    )


def panel_to_records(panel: pd.DataFrame) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for row in panel.to_dict(orient="records"):
        records.append({key: _round_float(value) if isinstance(value, float) else value for key, value in row.items()})
    return records
