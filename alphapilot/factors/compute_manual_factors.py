"""Compute Manual Factor Library V01 on the local FactorDataPanel.

All factors are point-in-time research features. Rolling calculations use only
current and historical rows. Cross-sectional ranks are computed within the same
timestamp. The module does not run backtests, create strategy entries, or trade.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import pandas as pd

from alphapilot.factors.manual_factor_library import build_manual_factor_library_v01, manual_factor_output_columns

REPORT_ID = "v13_4_21_manual_factor_library_report"
REPORT_VERSION = "V13.4.21"


@dataclass
class ManualFactorComputationResult:
    panel: pd.DataFrame
    report: dict[str, Any]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _safe_div_series(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    denominator = denominator.replace(0, pd.NA)
    return numerator / denominator


def _coverage(panel: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, Any]]:
    total = len(panel)
    coverage: dict[str, dict[str, Any]] = {}
    for column in columns:
        non_null = int(panel[column].notna().sum()) if column in panel else 0
        coverage[column] = {
            "nonNullCount": non_null,
            "rowCount": total,
            "coveragePct": round((non_null / total) * 100, 4) if total else 0.0,
        }
    return coverage


def _rank_percent(values: pd.Series) -> pd.Series:
    return values.rank(method="average", pct=True) * 100


def _compute_pair_factors(pair_frame: pd.DataFrame) -> pd.DataFrame:
    frame = pair_frame.sort_values("timestamp").copy()
    close = frame["close"]
    high = frame["high"]
    low = frame["low"]
    volume = frame["volume"]
    returns = frame["returns_1"]

    frame["momentum_3"] = frame["returns_3"]
    frame["momentum_12"] = frame["returns_12"]
    frame["reversal_3"] = -frame["returns_3"]
    frame["volume_mean_24"] = volume.rolling(24, min_periods=6).mean()
    frame["volume_mean_72"] = volume.rolling(72, min_periods=24).mean()
    frame["volume_expansion_24h"] = _safe_div_series(volume, frame["volume_mean_24"])
    frame["volume_expansion_3d"] = _safe_div_series(frame["volume_mean_24"], frame["volume_mean_72"])

    frame["ema20"] = close.ewm(span=20, adjust=False, min_periods=1).mean()
    frame["ema50"] = close.ewm(span=50, adjust=False, min_periods=1).mean()
    frame["distance_to_ema20"] = _safe_div_series(close - frame["ema20"], frame["ema20"])
    frame["distance_to_ema50"] = _safe_div_series(close - frame["ema50"], frame["ema50"])

    mean_20 = close.rolling(20, min_periods=10).mean()
    std_20 = close.rolling(20, min_periods=10).std(ddof=0)
    frame["upper_band"] = mean_20 + (std_20 * 2)
    frame["lower_band"] = mean_20 - (std_20 * 2)
    frame["bollinger_position"] = _safe_div_series(close - frame["lower_band"], frame["upper_band"] - frame["lower_band"])

    frame["volatility_24h"] = returns.rolling(24, min_periods=6).std(ddof=0)
    frame["volatility_3d"] = returns.rolling(72, min_periods=24).std(ddof=0)

    previous_close = close.shift(1)
    true_range = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    frame["atr"] = true_range.rolling(14, min_periods=5).mean()
    frame["atr_pct"] = _safe_div_series(frame["atr"], close)
    frame["trend_strength"] = _safe_div_series(frame["ema20"] - frame["ema50"], close)

    mean_24 = close.rolling(24, min_periods=6).mean()
    std_24 = close.rolling(24, min_periods=6).std(ddof=0)
    frame["mean_reversion_distance"] = -((close - mean_24).abs() / std_24.replace(0, pd.NA))

    frame["recent_high_24"] = high.rolling(24, min_periods=6).max()
    frame["breakout_price_pressure_raw"] = _safe_div_series(close, frame["recent_high_24"])
    return frame


def compute_manual_factors(panel: pd.DataFrame) -> ManualFactorComputationResult:
    warnings = [
        "Research-only factor computation. No backtest was run.",
        "No factor output is a trade signal, order, or live execution instruction.",
    ]
    if panel.empty:
        report = {
            "reportId": REPORT_ID,
            "version": REPORT_VERSION,
            "status": "blocked_empty_panel",
            "factorCount": len(manual_factor_output_columns()),
            "computedFactors": [],
            "factorCoverage": {},
            "noLookaheadRules": no_lookahead_rules(),
            "warnings": warnings + ["Input FactorDataPanel was empty."],
            "generatedAt": utc_now(),
        }
        return ManualFactorComputationResult(panel=panel.copy(), report=report)

    working = panel.copy()
    working = working.sort_values(["pair", "timestamp"]).reset_index(drop=True)
    pair_frames = [_compute_pair_factors(pair_frame) for _, pair_frame in working.groupby("pair", sort=False)]
    working = pd.concat(pair_frames, ignore_index=True).reset_index(drop=True)

    btc_map = working[working["pair"] == "BTC/USDT:USDT"].set_index("timestamp")["momentum_12"].to_dict()
    working["btc_momentum_12"] = working["timestamp"].map(btc_map)
    working["relative_strength_vs_btc"] = working["momentum_12"] - working["btc_momentum_12"]
    working["liquidity_rank"] = working.groupby("timestamp")["quoteVolume"].transform(_rank_percent)

    working["breakout_price_rank"] = working.groupby("timestamp")["breakout_price_pressure_raw"].transform(_rank_percent)
    working["volume_expansion_rank"] = working.groupby("timestamp")["volume_expansion_24h"].transform(_rank_percent)
    working["breakout_pressure"] = working["breakout_price_rank"] + working["volume_expansion_rank"]

    factor_columns = manual_factor_output_columns()
    coverage = _coverage(working, factor_columns)
    missing_factor_columns = [column for column in factor_columns if column not in working.columns]
    if missing_factor_columns:
        warnings.append(f"Missing computed factor columns: {', '.join(missing_factor_columns)}")

    coverage_values = [row["coveragePct"] for row in coverage.values()]
    average_coverage = round(sum(coverage_values) / len(coverage_values), 4) if coverage_values else 0.0
    report = {
        "reportId": REPORT_ID,
        "version": REPORT_VERSION,
        "status": "success",
        "factorCount": len(factor_columns),
        "computedFactors": factor_columns,
        "factorDefinitions": build_manual_factor_library_v01(),
        "factorCoverage": coverage,
        "averageCoveragePct": average_coverage,
        "rowCount": len(working),
        "pairCount": int(working["pair"].nunique()),
        "timestampCount": int(working["timestamp"].nunique()),
        "noLookaheadRules": no_lookahead_rules(),
        "warnings": warnings,
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "generatedAt": utc_now(),
    }
    return ManualFactorComputationResult(panel=working, report=report)


def no_lookahead_rules() -> list[str]:
    return [
        "Rolling features use only the current row and historical rows within each pair.",
        "Forward returns are not computed in V13.4.21 factor outputs.",
        "Cross-sectional ranks are computed only across pairs sharing the same timestamp.",
        "BTC relative strength context is matched by exact timestamp only.",
        "Missing values remain null; no future data is filled backward into earlier rows.",
    ]


def sanitize_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized: list[dict[str, Any]] = []
    for row in records:
        output: dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, float):
                output[key] = None if math.isnan(value) or math.isinf(value) else round(value, 10)
            else:
                output[key] = value
        sanitized.append(output)
    return sanitized
