"""Deterministic research backtest for factor-confluence low-frequency rules.

This module reads local public OHLCV files only. It does not download market
data, call exchange APIs, read accounts or positions, create orders, run
exchange Dry-run, or automate trading.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.factors.ohlcv_loader import _read_ohlcv_file, discover_ohlcv_files, parse_timerange


DEFAULT_DATA_PATH = Path("user_data/data/okx/futures")
DEFAULT_TIMERANGE = "20200101-"
DEFAULT_TIMEFRAME = "4h"
DEFAULT_STARTING_EQUITY = 10_000.0
DEFAULT_RISK_PER_TRADE_PCT = 1.0
DEFAULT_FEE_RATE = 0.0005
DEFAULT_SLIPPAGE_RATE = 0.0005
DEFAULT_ATR_MULTIPLIER = 1.5
DEFAULT_REWARD_RISK = 2.0
DEFAULT_MAX_HOLD_BARS = 42
ALLOWED_BTC_REGIMES = {"sideways"}
BLOCKED_BTC_REGIMES = {"crash", "high_volatility", "bear", "unknown"}


@dataclass(frozen=True)
class FactorConfluenceBacktestConfig:
    data_path: Path = DEFAULT_DATA_PATH
    timerange: str = DEFAULT_TIMERANGE
    timeframe: str = DEFAULT_TIMEFRAME
    starting_equity: float = DEFAULT_STARTING_EQUITY
    risk_per_trade_pct: float = DEFAULT_RISK_PER_TRADE_PCT
    fee_rate: float = DEFAULT_FEE_RATE
    slippage_rate: float = DEFAULT_SLIPPAGE_RATE
    atr_multiplier: float = DEFAULT_ATR_MULTIPLIER
    reward_risk: float = DEFAULT_REWARD_RISK
    max_hold_bars: int = DEFAULT_MAX_HOLD_BARS
    pairs: tuple[str, ...] = ()


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


def _iso(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat()


def _normalize_ohlcv(raw: pd.DataFrame, pair: str, timerange: str) -> pd.DataFrame:
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
    frame["pair"] = pair
    return frame.reset_index(drop=True)


def _load_frames(config: FactorConfluenceBacktestConfig) -> tuple[dict[str, pd.DataFrame], list[str]]:
    warnings: list[str] = []
    discovered = discover_ohlcv_files(config.data_path, config.timeframe)
    requested = list(config.pairs) if config.pairs else sorted(discovered.keys())
    frames: dict[str, pd.DataFrame] = {}
    for pair in requested:
        path = discovered.get(pair)
        if path is None:
            warnings.append(f"{pair} skipped: missing local {config.timeframe} OHLCV file.")
            continue
        try:
            frame = _normalize_ohlcv(_read_ohlcv_file(path), pair, config.timerange)
        except Exception as exc:  # noqa: BLE001 - research report records skipped pairs.
            warnings.append(f"{pair} skipped: {exc}")
            continue
        if len(frame) < 260:
            warnings.append(f"{pair} skipped: fewer than 260 candles after timerange filter.")
            continue
        frames[pair] = frame
    if not frames:
        warnings.append("No local 4h OHLCV frames were available for the deterministic backtest.")
    return frames, warnings


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    return 100 - (100 / (1 + rs))


def _prepare_indicators(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    close = data["close"].astype(float)
    high = data["high"].astype(float)
    low = data["low"].astype(float)
    volume = data["volume"].astype(float)
    data["ema20"] = close.ewm(span=20, adjust=False, min_periods=20).mean()
    data["ema50"] = close.ewm(span=50, adjust=False, min_periods=50).mean()
    data["ema200"] = close.ewm(span=200, adjust=False, min_periods=200).mean()
    data["rsi14"] = _rsi(close)
    ema12 = close.ewm(span=12, adjust=False, min_periods=12).mean()
    ema26 = close.ewm(span=26, adjust=False, min_periods=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9, adjust=False, min_periods=9).mean()
    data["macdHist"] = macd - signal
    previous_close = close.shift(1)
    tr = pd.concat(
        [
            high - low,
            (high - previous_close).abs(),
            (low - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    data["atr14"] = tr.ewm(alpha=1 / 14, adjust=False, min_periods=14).mean()
    data["atrPct"] = data["atr14"] / close * 100
    data["volumeRatio"] = volume / volume.rolling(20, min_periods=20).mean()
    bb_mean = close.rolling(20, min_periods=20).mean()
    bb_std = close.rolling(20, min_periods=20).std()
    data["bbWidthPct"] = ((bb_mean + 2 * bb_std) - (bb_mean - 2 * bb_std)) / close * 100
    data["bbWidthMedian120"] = data["bbWidthPct"].rolling(120, min_periods=60).median()
    return data


def _build_btc_regime_proxy(btc: pd.DataFrame) -> pd.DataFrame:
    data = _prepare_indicators(btc)
    data["return24h"] = data["close"].pct_change(6)
    data["return3d"] = data["close"].pct_change(18)
    data["return7d"] = data["close"].pct_change(42)
    rolling_vol = data["close"].pct_change().rolling(42, min_periods=24).std()
    vol_threshold = rolling_vol.quantile(0.80)
    rows: list[dict[str, Any]] = []
    for row in data.itertuples(index=False):
        labels: list[str] = []
        close = float(row.close)
        if pd.notna(row.ema20) and pd.notna(row.ema50) and pd.notna(row.ema200):
            if close > row.ema200 and row.ema20 > row.ema50:
                labels.append("bull")
            if close < row.ema200 and row.ema20 < row.ema50:
                labels.append("bear")
            if abs((row.ema20 / row.ema50) - 1.0) <= 0.01:
                labels.append("sideways")
        if pd.notna(getattr(row, "return3d")) and row.return3d <= -0.10:
            labels.append("crash")
        if pd.notna(getattr(row, "return7d")) and row.return7d >= 0.10 and pd.notna(row.ema20) and close > row.ema20:
            labels.append("recovery")
        current_vol = rolling_vol.loc[data["date"] == row.date]
        if not current_vol.empty and pd.notna(vol_threshold) and pd.notna(current_vol.iloc[0]) and current_vol.iloc[0] >= vol_threshold:
            labels.append("high_volatility")
        if not labels:
            labels.append("unknown")
        primary = next((item for item in ["crash", "bear", "recovery", "bull", "high_volatility", "sideways"] if item in labels), "unknown")
        rows.append(
            {
                "date": row.date,
                "btcPrimaryRegime": primary,
                "btcLabels": sorted(set(labels)),
                "btcReturn24hPct": _round(getattr(row, "return24h", None) * 100 if pd.notna(getattr(row, "return24h", None)) else None),
                "btcReturn3dPct": _round(getattr(row, "return3d", None) * 100 if pd.notna(getattr(row, "return3d", None)) else None),
            }
        )
    return pd.DataFrame(rows).sort_values("date").reset_index(drop=True)


def _align_btc_context(data: pd.DataFrame, btc_regime: pd.DataFrame) -> pd.DataFrame:
    merged = pd.merge_asof(
        data.sort_values("date"),
        btc_regime.sort_values("date"),
        on="date",
        direction="backward",
        tolerance=pd.Timedelta("8h"),
    )
    merged["btcPrimaryRegime"] = merged["btcPrimaryRegime"].fillna("unknown")
    merged["btcLabels"] = merged["btcLabels"].apply(lambda value: value if isinstance(value, list) else ["unknown"])
    return merged


def _entry_diagnostics(row: Any, previous: Any) -> dict[str, bool]:
    trend = bool(
        pd.notna(row.ema20)
        and pd.notna(row.ema50)
        and pd.notna(row.ema200)
        and row.close > row.ema50
        and row.ema20 > row.ema50
        and row.ema50 > row.ema200
    )
    pullback = bool(pd.notna(row.ema20) and row.low <= row.ema20 * 1.012 and row.close >= row.ema20 * 0.99 and row.close <= row.ema20 * 1.025)
    rsi_ok = bool(pd.notna(row.rsi14) and 48 <= row.rsi14 <= 62)
    macd_improving = bool(
        pd.notna(row.macdHist)
        and (
            row.macdHist > 0
            and previous is not None
            and pd.notna(previous.macdHist)
            and row.macdHist > previous.macdHist
        )
    )
    volume_ok = bool(pd.notna(row.volumeRatio) and row.volumeRatio >= 1.05)
    volatility_ok = bool(
        pd.notna(row.bbWidthPct)
        and pd.notna(row.bbWidthMedian120)
        and row.bbWidthPct <= row.bbWidthMedian120 * 1.35
    )
    btc_regime_ok = bool(row.btcPrimaryRegime in ALLOWED_BTC_REGIMES)
    btc_drop_ok = bool(
        (pd.isna(row.btcReturn24hPct) or row.btcReturn24hPct > -8)
        and (pd.isna(row.btcReturn3dPct) or row.btcReturn3dPct > -10)
    )
    factor_votes = sum([trend, rsi_ok and macd_improving, volume_ok, volatility_ok])
    return {
        "trend": trend,
        "pullback": pullback,
        "rsiOk": rsi_ok,
        "macdImproving": macd_improving,
        "volumeOk": volume_ok,
        "volatilityOk": volatility_ok,
        "btcRegimeOk": btc_regime_ok,
        "btcDropOk": btc_drop_ok,
        "factorVotesAtLeastThree": factor_votes >= 3,
    }


def _entry_signal(row: Any, previous: Any) -> tuple[bool, dict[str, bool]]:
    checks = _entry_diagnostics(row, previous)
    return all(checks.values()), checks


def _simulate_pair(
    pair: str,
    raw_frame: pd.DataFrame,
    btc_regime: pd.DataFrame,
    config: FactorConfluenceBacktestConfig,
) -> list[dict[str, Any]]:
    data = _align_btc_context(_prepare_indicators(raw_frame), btc_regime)
    trades: list[dict[str, Any]] = []
    index = 201
    while index < len(data) - 2:
        row = data.iloc[index]
        previous = data.iloc[index - 1] if index > 0 else None
        signal, checks = _entry_signal(row, previous)
        if not signal or pd.isna(row.atr14) or row.atr14 <= 0:
            index += 1
            continue

        entry_index = index + 1
        entry_row = data.iloc[entry_index]
        base_entry = float(entry_row.open)
        entry_price = base_entry * (1 + config.slippage_rate)
        risk_per_unit = float(row.atr14) * config.atr_multiplier
        if risk_per_unit <= 0 or entry_price <= risk_per_unit:
            index += 1
            continue
        stop_price = entry_price - risk_per_unit
        target_price = entry_price + risk_per_unit * config.reward_risk
        exit_index = min(entry_index + config.max_hold_bars, len(data) - 1)
        exit_reason = "time_stop"
        exit_base_price = float(data.iloc[exit_index].close)

        for cursor in range(entry_index, min(entry_index + config.max_hold_bars + 1, len(data))):
            candle = data.iloc[cursor]
            # Conservative same-candle path: if both stop and target are touched,
            # the stop is recorded first.
            if float(candle.low) <= stop_price:
                exit_index = cursor
                exit_reason = "stop_loss"
                exit_base_price = stop_price
                break
            if float(candle.high) >= target_price:
                exit_index = cursor
                exit_reason = "target_2r"
                exit_base_price = target_price
                break

        exit_price = exit_base_price * (1 - config.slippage_rate)
        gross_r = (exit_price - entry_price) / risk_per_unit
        fee_r = config.fee_rate * (entry_price + exit_price) / risk_per_unit
        net_r = gross_r - fee_r
        trades.append(
            {
                "pair": pair,
                "entryTimestamp": _iso(entry_row.date),
                "exitTimestamp": _iso(data.iloc[exit_index].date),
                "entryPrice": _round(entry_price, 8),
                "exitPrice": _round(exit_price, 8),
                "stopPrice": _round(stop_price, 8),
                "targetPrice": _round(target_price, 8),
                "grossR": _round(gross_r, 6),
                "feeR": _round(fee_r, 6),
                "netR": _round(net_r, 6),
                "exitReason": exit_reason,
                "holdBars": int(exit_index - entry_index + 1),
                "btcPrimaryRegime": row.btcPrimaryRegime,
                "btcLabels": row.btcLabels,
                "rsi14": _round(row.rsi14),
                "macdHist": _round(row.macdHist, 8),
                "volumeRatio": _round(row.volumeRatio),
                "atrPct": _round(row.atrPct),
                "bbWidthPct": _round(row.bbWidthPct),
                "entryChecks": checks,
            }
        )
        index = exit_index + 1
    return trades


def _max_consecutive_losses(trades: list[dict[str, Any]]) -> int:
    best = 0
    current = 0
    for trade in sorted(trades, key=lambda item: item["exitTimestamp"]):
        if float(trade.get("netR") or 0) < 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _metrics(trades: list[dict[str, Any]], config: FactorConfluenceBacktestConfig) -> dict[str, Any]:
    ordered = sorted(trades, key=lambda item: item["exitTimestamp"])
    if not ordered:
        return {
            "tradeCount": 0,
            "winRatePct": None,
            "profitFactor": None,
            "totalNetR": 0.0,
            "totalReturnPct": 0.0,
            "maxDrawdownPct": 0.0,
            "averageWinR": None,
            "averageLossR": None,
            "realizedRewardRiskRatio": None,
            "targetRewardRiskRatio": config.reward_risk,
            "maxConsecutiveLosses": 0,
        }
    wins = [float(trade["netR"]) for trade in ordered if float(trade["netR"]) > 0]
    losses = [float(trade["netR"]) for trade in ordered if float(trade["netR"]) < 0]
    equity = []
    cumulative_r = 0.0
    for trade in ordered:
        cumulative_r += float(trade["netR"])
        equity.append(1 + cumulative_r * config.risk_per_trade_pct / 100)
    equity_series = pd.Series(equity)
    drawdown = (equity_series.cummax() - equity_series) / equity_series.cummax() * 100
    avg_win = sum(wins) / len(wins) if wins else None
    avg_loss = abs(sum(losses) / len(losses)) if losses else None
    return {
        "tradeCount": len(ordered),
        "winRatePct": _round(len(wins) / len(ordered) * 100),
        "profitFactor": _round(sum(wins) / abs(sum(losses)) if losses else None),
        "totalNetR": _round(cumulative_r),
        "totalReturnPct": _round(cumulative_r * config.risk_per_trade_pct),
        "maxDrawdownPct": _round(drawdown.max()),
        "averageWinR": _round(avg_win),
        "averageLossR": _round(avg_loss),
        "realizedRewardRiskRatio": _round(avg_win / avg_loss if avg_win is not None and avg_loss else None),
        "targetRewardRiskRatio": config.reward_risk,
        "maxConsecutiveLosses": _max_consecutive_losses(ordered),
    }


def _group_metrics(trades: list[dict[str, Any]], key: str, config: FactorConfluenceBacktestConfig) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for value, group in pd.DataFrame(trades).groupby(key) if trades else []:
        subset = group.to_dict("records")
        row = {key: value}
        row.update(_metrics(subset, config))
        rows.append(row)
    return sorted(rows, key=lambda item: str(item.get(key)))


def _walk_forward_metrics(trades: list[dict[str, Any]], config: FactorConfluenceBacktestConfig) -> list[dict[str, Any]]:
    if not trades:
        return []
    frame = pd.DataFrame(trades)
    frame["exitTimestamp"] = pd.to_datetime(frame["exitTimestamp"], utc=True, errors="coerce")
    splits = [
        ("train_2020_2022", "2020-01-01", "2023-01-01"),
        ("validation_2023_2024", "2023-01-01", "2025-01-01"),
        ("test_2025_2026", "2025-01-01", "2027-01-01"),
    ]
    rows = []
    for split_id, start, end in splits:
        subset = frame[(frame["exitTimestamp"] >= pd.Timestamp(start, tz="UTC")) & (frame["exitTimestamp"] < pd.Timestamp(end, tz="UTC"))]
        metrics = _metrics(subset.to_dict("records"), config)
        metrics["splitId"] = split_id
        metrics["start"] = start
        metrics["endExclusive"] = end
        rows.append(metrics)
    return rows


def _baseline_comparison(metrics: dict[str, Any], baseline_path: Path) -> dict[str, Any]:
    if not baseline_path.exists():
        return {"available": False, "warnings": [f"Baseline report missing: {baseline_path.as_posix()}"]}
    import json

    payload = json.loads(baseline_path.read_text(encoding="utf-8"))
    equal_weight = None
    for row in payload.get("comparisonTable", []):
        if isinstance(row, dict) and str(row.get("name", "")).startswith("EqualWeight") and row.get("timeframe") == "4h":
            equal_weight = row
            break
    strategy_return = metrics.get("totalReturnPct")
    equal_return = equal_weight.get("totalReturnPct") if equal_weight else None
    equal_drawdown = equal_weight.get("maxDrawdownPct") if equal_weight else None
    return {
        "available": True,
        "source": baseline_path.as_posix(),
        "strategyReturnPct": strategy_return,
        "strategyMaxDrawdownPct": metrics.get("maxDrawdownPct"),
        "noTradeReturnPct": 0.0,
        "equalWeightReturnPct": equal_return,
        "equalWeightMaxDrawdownPct": equal_drawdown,
        "beatsNoTrade": strategy_return is not None and strategy_return > 0,
        "beatsEqualWeight": strategy_return is not None and equal_return is not None and strategy_return > equal_return,
        "drawdownLowerThanEqualWeight": (
            metrics.get("maxDrawdownPct") is not None
            and equal_drawdown is not None
            and metrics["maxDrawdownPct"] < equal_drawdown
        ),
        "warnings": [] if equal_weight else ["No 4h equal-weight baseline row was found."],
    }


def _pass_gate(
    metrics: dict[str, Any],
    baseline: dict[str, Any],
    pass_gate: dict[str, Any],
    walk_forward: list[dict[str, Any]],
) -> dict[str, Any]:
    validation = next((row for row in walk_forward if row.get("splitId") == "validation_2023_2024"), {})
    test = next((row for row in walk_forward if row.get("splitId") == "test_2025_2026"), {})
    checks = {
        "minTradeCount": metrics.get("tradeCount", 0) >= pass_gate["minTradeCount"],
        "minRewardRiskRatio": metrics.get("targetRewardRiskRatio") == pass_gate["minRewardRiskRatio"],
        "minProfitFactor": metrics.get("profitFactor") is not None and metrics["profitFactor"] >= pass_gate["minProfitFactor"],
        "maxDrawdownPct": metrics.get("maxDrawdownPct") is not None and metrics["maxDrawdownPct"] <= pass_gate["maxDrawdownPct"],
        "mustBeatNoTrade": bool(baseline.get("beatsNoTrade")),
        "mustBeatEqualWeight": bool(baseline.get("beatsEqualWeight")),
        "walkForwardValidationPositive": (
            validation.get("tradeCount", 0) >= 20
            and validation.get("totalReturnPct") is not None
            and validation["totalReturnPct"] > 0
            and validation.get("profitFactor") is not None
            and validation["profitFactor"] >= 1.0
        ),
        "walkForwardTestPositive": (
            test.get("tradeCount", 0) >= 20
            and test.get("totalReturnPct") is not None
            and test["totalReturnPct"] > 0
            and test.get("profitFactor") is not None
            and test["profitFactor"] >= 1.0
        ),
    }
    return {
        "gateId": "v13_7_19_research_backtest_gate",
        "inputPassGate": pass_gate,
        "checks": checks,
        "passed": all(checks.values()),
        "paperObservationApproved": all(checks.values()),
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
    }


def run_factor_confluence_backtest(
    config: FactorConfluenceBacktestConfig | None = None,
    *,
    baseline_report_path: Path = Path("reports/v13_4_32_low_frequency_baseline_report.json"),
) -> dict[str, Any]:
    active_config = config or FactorConfluenceBacktestConfig()
    frames, warnings = _load_frames(active_config)
    btc = frames.get("BTC/USDT:USDT")
    if btc is None:
        return {
            "status": "blocked",
            "reason": "BTC/USDT:USDT 4h OHLCV is required for the regime gate.",
            "warnings": warnings,
            "trades": [],
        }
    btc_regime = _build_btc_regime_proxy(btc)
    all_trades: list[dict[str, Any]] = []
    for pair, frame in frames.items():
        if pair == "BTC/USDT:USDT":
            # BTC is used as a regime gate first. Other assets carry the
            # confluence candidate replay.
            continue
        all_trades.extend(_simulate_pair(pair, frame, btc_regime, active_config))

    metrics = _metrics(all_trades, active_config)
    baseline = _baseline_comparison(metrics, baseline_report_path)
    pass_gate = {
        "minTradeCount": 80,
        "minRewardRiskRatio": 2.0,
        "minProfitFactor": 1.15,
        "maxDrawdownPct": 25,
        "mustBeatNoTrade": True,
        "mustBeatEqualWeight": True,
    }
    walk_forward = _walk_forward_metrics(all_trades, active_config)
    gate = _pass_gate(metrics, baseline, pass_gate, walk_forward)
    return {
        "status": "completed",
        "experimentId": "lf_factor_confluence_regime_filter_4h_v0_1",
        "strategyName": "LF Factor Confluence Regime Filter 4H V0.1",
        "sourceCandidateId": "factor_confluence_low_frequency_filter_v0_1",
        "timerange": active_config.timerange,
        "timeframe": active_config.timeframe,
        "dataPath": active_config.data_path.as_posix(),
        "pairCount": len(frames),
        "testedPairs": sorted(pair for pair in frames if pair != "BTC/USDT:USDT"),
        "config": {
            "startingEquity": active_config.starting_equity,
            "riskPerTradePct": active_config.risk_per_trade_pct,
            "feeRateOneWay": active_config.fee_rate,
            "slippageRateOneWay": active_config.slippage_rate,
            "atrMultiplier": active_config.atr_multiplier,
            "targetRewardRiskRatio": active_config.reward_risk,
            "maxHoldBars": active_config.max_hold_bars,
            "entryExecution": "next_bar_open_plus_slippage",
            "sameCandlePath": "conservative_stop_first",
        },
        "btcRegimeSource": {
            "source": "local_public_btc_4h_ohlcv_inline_proxy_v13_7_19",
            "labelCount": int(len(btc_regime)),
            "firstTimestamp": _iso(btc_regime["date"].iloc[0]) if not btc_regime.empty else None,
            "lastTimestamp": _iso(btc_regime["date"].iloc[-1]) if not btc_regime.empty else None,
            "blockedRegimes": sorted(BLOCKED_BTC_REGIMES),
            "note": "Regime labels are computed deterministically from local BTC public OHLCV for full timerange coverage; no missing labels are fabricated.",
        },
        "metrics": metrics,
        "passGate": gate,
        "baselineComparison": baseline,
        "walkForward": walk_forward,
        "byPair": _group_metrics(all_trades, "pair", active_config),
        "byRegime": _group_metrics(all_trades, "btcPrimaryRegime", active_config),
        "exitReasonBreakdown": _group_metrics(all_trades, "exitReason", active_config),
        "tradeSample": sorted(all_trades, key=lambda item: item["exitTimestamp"])[:80],
        "warnings": warnings,
        "safetyBoundary": {
            "realTradingEnabled": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "tradeApiEnabled": False,
            "withdrawApiEnabled": False,
            "apiKeyStorage": False,
            "realAccountReads": False,
            "realPositionReads": False,
            "orderCreation": False,
            "autoTrading": False,
        },
    }
