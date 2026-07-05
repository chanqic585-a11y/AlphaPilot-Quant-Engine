"""Report-only low-frequency baselines for V13.4.32."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.factors.ohlcv_loader import _read_ohlcv_file, pair_to_freqtrade_stem, parse_timerange
from alphapilot.low_frequency.low_frequency_data_schema import DEFAULT_LOW_FREQUENCY_PAIRS, TIMEFRAME_MINUTES


REGIME_REPORT_PATH = Path("reports/v13_4_27_market_regime_data_integrity_report.json")


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        if value is None:
            return None
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return round(number, digits)


def _safe_pct_return(first: float, last: float) -> float | None:
    if first == 0:
        return None
    return (last / first - 1) * 100


def _max_drawdown_pct(equity: pd.Series) -> float | None:
    if equity.empty:
        return None
    drawdown = (equity.cummax() - equity) / equity.cummax() * 100
    return _round(drawdown.max())


def _best_drawup_pct(equity: pd.Series) -> float | None:
    if equity.empty:
        return None
    drawup = (equity / equity.cummin() - 1) * 100
    return _round(drawup.max())


def _annualized_volatility_pct(close: pd.Series, timeframe: str) -> float | None:
    returns = close.pct_change().dropna()
    if returns.empty:
        return None
    periods_per_year = 365 * 24 * 60 / TIMEFRAME_MINUTES.get(timeframe, 1440)
    return _round(returns.std() * math.sqrt(periods_per_year) * 100)


def _read_frame(pair: str, timeframe: str, timerange: str, data_path: str) -> pd.DataFrame:
    path = Path(data_path) / f"{pair_to_freqtrade_stem(pair)}-{timeframe}-futures.feather"
    raw = _read_ohlcv_file(path)
    frame = raw.loc[:, ["date", "open", "high", "low", "close", "volume"]].copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    frame = frame.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    start, end = parse_timerange(timerange)
    if start is not None:
        frame = frame[frame["date"] >= start]
    if end is not None:
        frame = frame[frame["date"] < end]
    if frame.empty:
        raise ValueError(f"empty_frame_after_filter: {pair} {timeframe}")
    return frame.reset_index(drop=True)


def build_no_trade_baseline(timerange: str) -> dict[str, Any]:
    return {
        "baselineId": "low_frequency_no_trade",
        "name": "NoTrade",
        "type": "report_only_baseline",
        "timerange": timerange,
        "totalReturnPct": 0.0,
        "maxDrawdownPct": 0.0,
        "volatilityPct": 0.0,
        "bestDrawupPct": 0.0,
        "worstDrawdownPct": 0.0,
        "tradeCount": 0,
        "syntheticHoldingCount": 0,
        "exposureTimePct": 0.0,
        "status": "research_only",
        "interpretation": "NoTrade is an active benchmark for capital preservation and opportunity cost.",
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }


def build_buy_hold_baseline(pair: str, timeframe: str, timerange: str, data_path: str) -> dict[str, Any]:
    frame = _read_frame(pair, timeframe, timerange, data_path)
    close = frame["close"].astype(float)
    equity = close / close.iloc[0]
    total_return = _safe_pct_return(close.iloc[0], close.iloc[-1])
    return {
        "baselineId": f"low_frequency_buy_hold_{pair_to_freqtrade_stem(pair).lower()}_{timeframe}",
        "name": f"BuyHold {pair}",
        "pair": pair,
        "timeframe": timeframe,
        "timerange": timerange,
        "firstTimestamp": pd.Timestamp(frame["date"].iloc[0]).isoformat(),
        "lastTimestamp": pd.Timestamp(frame["date"].iloc[-1]).isoformat(),
        "candleCount": int(len(frame)),
        "startClose": _round(close.iloc[0], 8),
        "endClose": _round(close.iloc[-1], 8),
        "totalReturnPct": _round(total_return),
        "maxDrawdownPct": _max_drawdown_pct(equity),
        "volatilityPct": _annualized_volatility_pct(close, timeframe),
        "bestDrawupPct": _best_drawup_pct(equity),
        "worstDrawdownPct": _max_drawdown_pct(equity),
        "tradeCount": 0,
        "syntheticHoldingCount": 1,
        "exposureTimePct": 100.0,
        "status": "research_only",
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }


def build_equal_weight_baseline(
    pairs: list[str],
    timeframe: str,
    timerange: str,
    data_path: str,
) -> dict[str, Any]:
    normalized_frames: list[pd.DataFrame] = []
    warnings: list[str] = []
    for pair in pairs:
        try:
            frame = _read_frame(pair, timeframe, timerange, data_path)
        except Exception as exc:  # noqa: BLE001 - report-only unavailable branch.
            warnings.append(f"{pair} unavailable for equal-weight baseline: {exc}")
            continue
        normalized = frame[["date", "close"]].copy()
        normalized[pair] = normalized["close"].astype(float) / float(normalized["close"].iloc[0])
        normalized_frames.append(normalized[["date", pair]])

    if len(normalized_frames) != len(pairs):
        return {
            "baselineId": f"low_frequency_equal_weight_{timeframe}",
            "name": f"EqualWeight BTC/ETH/SOL {timeframe}",
            "timeframe": timeframe,
            "timerange": timerange,
            "status": "unavailable",
            "warnings": warnings + ["Equal-weight baseline requires all requested pairs."],
            "dryRunApproved": False,
            "liveTradingApproved": False,
        }

    merged = normalized_frames[0]
    for frame in normalized_frames[1:]:
        merged = merged.merge(frame, on="date", how="inner")
    if merged.empty:
        return {
            "baselineId": f"low_frequency_equal_weight_{timeframe}",
            "name": f"EqualWeight BTC/ETH/SOL {timeframe}",
            "timeframe": timeframe,
            "timerange": timerange,
            "status": "unavailable",
            "warnings": warnings + ["No overlapping candles for equal-weight baseline."],
            "dryRunApproved": False,
            "liveTradingApproved": False,
        }

    equity = merged[pairs].mean(axis=1)
    returns = equity.pct_change().dropna()
    periods_per_year = 365 * 24 * 60 / TIMEFRAME_MINUTES.get(timeframe, 1440)
    return {
        "baselineId": f"low_frequency_equal_weight_{timeframe}",
        "name": f"EqualWeight BTC/ETH/SOL {timeframe}",
        "pairs": pairs,
        "timeframe": timeframe,
        "timerange": timerange,
        "firstTimestamp": pd.Timestamp(merged["date"].iloc[0]).isoformat(),
        "lastTimestamp": pd.Timestamp(merged["date"].iloc[-1]).isoformat(),
        "candleCount": int(len(merged)),
        "totalReturnPct": _round((equity.iloc[-1] - 1) * 100),
        "maxDrawdownPct": _max_drawdown_pct(equity),
        "volatilityPct": _round(returns.std() * math.sqrt(periods_per_year) * 100) if not returns.empty else None,
        "bestDrawupPct": _best_drawup_pct(equity),
        "worstDrawdownPct": _max_drawdown_pct(equity),
        "tradeCount": 0,
        "syntheticHoldingCount": len(pairs),
        "exposureTimePct": 100.0,
        "status": "research_only",
        "warnings": warnings,
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }


def _load_regime_labels() -> pd.DataFrame | None:
    if not REGIME_REPORT_PATH.exists():
        return None
    data = json.loads(REGIME_REPORT_PATH.read_text(encoding="utf-8"))
    labels = data.get("btcRegime", {}).get("labels")
    if not isinstance(labels, list) or not labels:
        return None
    frame = pd.DataFrame(labels)
    if "timestamp" not in frame or "primaryLabel" not in frame:
        return None
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["timestamp"]).sort_values("timestamp")
    frame["timestamp"] = frame["timestamp"].astype("datetime64[ns, UTC]")
    return frame[["timestamp", "primaryLabel"]].reset_index(drop=True)


def build_regime_breakdown(
    pairs: list[str],
    timeframe: str,
    timerange: str,
    data_path: str,
) -> dict[str, Any]:
    labels = _load_regime_labels()
    if labels is None or labels.empty:
        return {
            "status": "unavailable",
            "source": REGIME_REPORT_PATH.as_posix(),
            "warnings": ["BTC regime labels are unavailable."],
        }

    breakdown: dict[str, Any] = {
        "status": "available",
        "source": REGIME_REPORT_PATH.as_posix(),
        "timeframe": timeframe,
        "timerange": timerange,
        "pairs": {},
        "warnings": [],
    }
    for pair in pairs:
        try:
            frame = _read_frame(pair, timeframe, timerange, data_path)
        except Exception as exc:  # noqa: BLE001 - report-only warning.
            breakdown["warnings"].append(f"{pair} skipped for regime breakdown: {exc}")
            continue
        returns = frame[["date", "close"]].copy()
        returns["date"] = pd.to_datetime(returns["date"], utc=True, errors="coerce").astype("datetime64[ns, UTC]")
        returns["periodReturnPct"] = returns["close"].astype(float).pct_change() * 100
        merged = pd.merge_asof(
            returns.sort_values("date"),
            labels,
            left_on="date",
            right_on="timestamp",
            direction="backward",
            tolerance=pd.Timedelta("8h") if timeframe == "4h" else pd.Timedelta("2d"),
        )
        merged["primaryLabel"] = merged["primaryLabel"].fillna("unknown")
        rows = []
        for label, group in merged.dropna(subset=["periodReturnPct"]).groupby("primaryLabel"):
            period_returns = group["periodReturnPct"] / 100
            rows.append(
                {
                    "regime": str(label),
                    "candleCount": int(len(group)),
                    "averagePeriodReturnPct": _round(group["periodReturnPct"].mean()),
                    "cumulativeReturnPct": _round(((1 + period_returns).prod() - 1) * 100),
                    "positiveReturnPct": _round((group["periodReturnPct"] > 0).mean() * 100),
                }
            )
        breakdown["pairs"][pair] = sorted(rows, key=lambda item: item["regime"])
    return breakdown


def build_low_frequency_baselines(
    *,
    timerange: str,
    pairs: list[str] | None = None,
    timeframes: list[str] | None = None,
    data_path: str = "user_data/data/okx/futures",
) -> dict[str, Any]:
    selected_pairs = pairs or list(DEFAULT_LOW_FREQUENCY_PAIRS)
    selected_timeframes = timeframes or ["4h", "1d"]
    buy_hold = []
    warnings: list[str] = []
    for timeframe in selected_timeframes:
        for pair in selected_pairs:
            try:
                buy_hold.append(build_buy_hold_baseline(pair, timeframe, timerange, data_path))
            except Exception as exc:  # noqa: BLE001 - baseline report records unavailable rows.
                warnings.append(f"{pair} {timeframe} buy-hold baseline unavailable: {exc}")
                buy_hold.append(
                    {
                        "baselineId": f"low_frequency_buy_hold_{pair_to_freqtrade_stem(pair).lower()}_{timeframe}",
                        "name": f"BuyHold {pair}",
                        "pair": pair,
                        "timeframe": timeframe,
                        "timerange": timerange,
                        "status": "unavailable",
                        "warnings": [str(exc)],
                        "dryRunApproved": False,
                        "liveTradingApproved": False,
                    }
                )

    equal_weight = [build_equal_weight_baseline(selected_pairs, timeframe, timerange, data_path) for timeframe in selected_timeframes]
    return {
        "noTrade": build_no_trade_baseline(timerange),
        "buyHold": buy_hold,
        "equalWeight": equal_weight,
        "regimeBreakdown": build_regime_breakdown(selected_pairs, "4h", timerange, data_path),
        "warnings": warnings,
    }
