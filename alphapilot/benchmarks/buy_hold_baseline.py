"""Report-only benchmark baselines for V13.4.23."""

from __future__ import annotations

from typing import Any

import pandas as pd

from alphapilot.factors.factor_schema import FactorDataPanelConfig
from alphapilot.factors.ohlcv_loader import load_local_ohlcv


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def build_no_trade_baseline() -> dict[str, Any]:
    return {
        "benchmarkId": "benchmark_no_trade",
        "name": "Benchmark No Trade",
        "type": "report_only_baseline",
        "totalReturnPct": 0.0,
        "slippageAdjustedTotalReturnPct": 0.0,
        "maxDrawdownPct": 0.0,
        "profitFactor": None,
        "slippageAdjustedProfitFactor": None,
        "winRate": None,
        "tradeCount": 0,
        "maxConsecutiveLosses": 0,
        "averageHoldingMinutes": None,
        "feesPaid": 0.0,
        "slippageCost": 0.0,
        "monthlyStability": None,
        "pairStability": None,
        "status": "research_only",
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }


def _drawdown_from_close(close: pd.Series) -> float | None:
    if close.empty:
        return None
    equity = close / close.iloc[0]
    drawdown = (equity.cummax() - equity) / equity.cummax() * 100
    return _round(drawdown.max())


def build_buy_hold_btc_baseline(timerange: str, timeframe: str = "1h", data_path: str = "user_data/data/okx/futures") -> dict[str, Any]:
    config = FactorDataPanelConfig(timerange=timerange, timeframe=timeframe, pairs=["BTC/USDT:USDT"], dataPath=data_path)
    loaded = load_local_ohlcv(config)
    frame = loaded.frames.get("BTC/USDT:USDT")
    warnings = list(loaded.report.warnings)
    if frame is None or frame.empty:
        return {
            "benchmarkId": "benchmark_buy_hold_btc",
            "name": "Benchmark Buy Hold BTC",
            "type": "report_only_baseline",
            "status": "unavailable",
            "warnings": warnings + ["BTC OHLCV unavailable for buy-and-hold baseline."],
            "dryRunApproved": False,
            "liveTradingApproved": False,
        }

    close = frame["close"].astype(float)
    total_return = (close.iloc[-1] / close.iloc[0] - 1) * 100 if close.iloc[0] else None
    return {
        "benchmarkId": "benchmark_buy_hold_btc",
        "name": "Benchmark Buy Hold BTC",
        "type": "report_only_baseline",
        "timerange": timerange,
        "timeframe": timeframe,
        "startClose": _round(close.iloc[0], 8),
        "endClose": _round(close.iloc[-1], 8),
        "totalReturnPct": _round(total_return),
        "slippageAdjustedTotalReturnPct": _round(total_return),
        "maxDrawdownPct": _drawdown_from_close(close),
        "profitFactor": None,
        "slippageAdjustedProfitFactor": None,
        "winRate": None,
        "tradeCount": 1,
        "maxConsecutiveLosses": None,
        "averageHoldingMinutes": None,
        "feesPaid": None,
        "slippageCost": 0.0,
        "monthlyStability": None,
        "pairStability": "single_pair_reference",
        "status": "research_only",
        "warnings": warnings,
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }
