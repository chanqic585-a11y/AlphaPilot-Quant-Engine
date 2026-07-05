"""Generate V13.4.34 Low-Frequency Directional 4H research report.

The generator reads local Freqtrade backtest result files only. It does not run
backtests, enter Dry-run, call private exchange APIs, read accounts, create
orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
import math
from bisect import bisect_right
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from alphapilot.reports.low_frequency_directional_report_schema import LowFrequencyDirectionalReport


REPORT_ID = "v13_4_34_low_frequency_directional_4h_report"
VERSION = "V13.4.34"
STRATEGY_CLASS = "AlphaPilotLowFrequencyDirectional4HV01"
STRATEGY_ID = "alpha_low_frequency_directional_4h_v01"
STRATEGY_NAME = "AlphaPilot Low Frequency Directional 4H V0.1"
STRATEGY_VERSION = "0.1-v13.4.34"
DEFAULT_RESULT_DIR = Path("user_data/backtest_results")
DEFAULT_RESULT_FILE = DEFAULT_RESULT_DIR / "v13_4_34_low_frequency_directional_4h.zip"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_4_34_low_frequency_directional_4h_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_34_low_frequency_directional_4h_summary.md")
DEFAULT_BASELINE_REPORT = Path("reports/v13_4_32_low_frequency_baseline_report.json")
DEFAULT_REGIME_LABELS = Path("reports/v13_4_27_btc_regime_labels.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | list[Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_freqtrade_payload(path: Path) -> dict[str, Any] | list[Any]:
    if path.suffix.lower() != ".zip":
        return _read_json(path)
    with ZipFile(path) as archive:
        result_members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".json")
            and not name.lower().endswith("_config.json")
            and not name.lower().endswith(".meta.json")
        ]
        if not result_members:
            return {}
        return json.loads(archive.read(result_members[0]).decode("utf-8"))


def _iter_result_files(result_dir: Path) -> list[Path]:
    if not result_dir.exists():
        return []
    candidates = [
        path
        for pattern in ("*.zip", "*.json")
        for path in result_dir.glob(pattern)
        if path.is_file()
        and not path.name.lower().endswith(".meta.json")
        and path.name != ".last_result.json"
    ]
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def _select_strategy_payload(payload: dict[str, Any] | list[Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict):
        return None
    if STRATEGY_CLASS in strategy and isinstance(strategy[STRATEGY_CLASS], dict):
        return strategy[STRATEGY_CLASS]
    for value in strategy.values():
        if isinstance(value, dict) and value.get("strategy_name") == STRATEGY_CLASS:
            return value
    return None


def _find_result(result_file: Path, result_dir: Path) -> tuple[Path | None, dict[str, Any] | None]:
    candidates = [result_file] if result_file.exists() else []
    candidates.extend(path for path in _iter_result_files(result_dir) if path not in candidates)
    for path in candidates:
        payload = _read_freqtrade_payload(path)
        strategy_payload = _select_strategy_payload(payload)
        if strategy_payload is not None:
            return path, strategy_payload
    return None, None


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _pct_from_source(source: dict[str, Any], pct_key: str, ratio_key: str) -> float | None:
    pct = _safe_float(source.get(pct_key), None)
    if pct is not None:
        return round(pct, 4)
    ratio = _safe_float(source.get(ratio_key), None)
    if ratio is None:
        return None
    return round(ratio * 100 if -1 <= ratio <= 1 else ratio, 4)


def _drawdown_pct(source: dict[str, Any]) -> float | None:
    for pct_key in ("max_drawdown_account_pct", "max_drawdown_pct"):
        value = _safe_float(source.get(pct_key), None)
        if value is not None:
            return round(abs(value), 4)
    for ratio_key in ("max_drawdown_account", "max_drawdown"):
        value = _safe_float(source.get(ratio_key), None)
        if value is not None:
            return round(abs(value * 100 if -1 <= value <= 1 else value), 4)
    return None


def _trades(source: dict[str, Any]) -> list[dict[str, Any]]:
    trades = source.get("trades") or []
    return trades if isinstance(trades, list) else []


def _trade_profit_abs(trade: dict[str, Any]) -> float:
    return _safe_float(trade.get("profit_abs"), 0.0) or 0.0


def _trade_is_win(trade: dict[str, Any]) -> bool:
    return _trade_profit_abs(trade) > 0


def _profit_factor_for_trades(trades: list[dict[str, Any]]) -> float | None:
    positive = sum(_trade_profit_abs(trade) for trade in trades if _trade_profit_abs(trade) > 0)
    negative = sum(_trade_profit_abs(trade) for trade in trades if _trade_profit_abs(trade) < 0)
    if negative < 0:
        return round(positive / abs(negative), 4)
    return None


def _win_rate_for_trades(trades: list[dict[str, Any]]) -> float | None:
    if not trades:
        return None
    return round(sum(1 for trade in trades if _trade_is_win(trade)) / len(trades) * 100, 4)


def _avg_duration_minutes(trades: list[dict[str, Any]]) -> float | None:
    values = [
        _safe_float(trade.get("trade_duration"), None)
        for trade in trades
        if _safe_float(trade.get("trade_duration"), None) is not None
    ]
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def _max_consecutive_losses(source: dict[str, Any], trades: list[dict[str, Any]] | None = None) -> int | None:
    direct = _safe_int(source.get("max_consecutive_losses"), None)
    if direct is not None and trades is None:
        return direct
    rows = trades if trades is not None else _trades(source)
    ordered = sorted(rows, key=lambda item: item.get("close_timestamp") or item.get("open_timestamp") or 0)
    best = 0
    current = 0
    for trade in ordered:
        if _trade_profit_abs(trade) < 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _starting_balance(source: dict[str, Any]) -> float:
    return _safe_float(source.get("starting_balance"), 0.0) or 0.0


def _slippage_adjustment_for_trades(
    trades: list[dict[str, Any]],
    starting_balance: float,
    rate: float,
) -> dict[str, Any]:
    positive = 0.0
    negative = 0.0
    total = 0.0
    total_cost = 0.0
    for trade in trades:
        stake = _safe_float(trade.get("max_stake_amount"), _safe_float(trade.get("stake_amount"), 0.0)) or 0.0
        leverage = _safe_float(trade.get("leverage"), 1.0) or 1.0
        notional = stake * leverage
        cost = notional * rate * 2
        adjusted = _trade_profit_abs(trade) - cost
        total += adjusted
        total_cost += cost
        if adjusted > 0:
            positive += adjusted
        elif adjusted < 0:
            negative += adjusted
    return {
        "slippageRateOneWay": rate,
        "totalSlippageCost": round(total_cost, 8),
        "totalReturnPct": round(total / starting_balance * 100, 4) if starting_balance else None,
        "profitFactor": round(positive / abs(negative), 4) if negative < 0 else None,
    }


def _direction_metrics(source: dict[str, Any], is_short: bool) -> dict[str, Any]:
    trades = [trade for trade in _trades(source) if bool(trade.get("is_short")) is is_short]
    starting_balance = _starting_balance(source)
    profit_abs = sum(_trade_profit_abs(trade) for trade in trades)
    return {
        "direction": "short" if is_short else "long",
        "tradeCount": len(trades),
        "totalProfitAbs": round(profit_abs, 8),
        "totalReturnPct": round(profit_abs / starting_balance * 100, 4) if starting_balance else None,
        "winRate": _win_rate_for_trades(trades),
        "profitFactor": _profit_factor_for_trades(trades),
        "averageDurationMinutes": _avg_duration_minutes(trades),
        "maxConsecutiveLosses": _max_consecutive_losses(source, trades),
        "slippageStress": [
            _slippage_adjustment_for_trades(trades, starting_balance, rate)
            for rate in (0.0005, 0.001)
        ],
    }


def _compact_rows(rows: Any, max_rows: int = 80) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    return [row for row in rows[:max_rows] if isinstance(row, dict)]


def _pair_performance(source: dict[str, Any]) -> list[dict[str, Any]]:
    results = source.get("results_per_pair")
    if isinstance(results, list):
        return _compact_rows(results, max_rows=60)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in _trades(source):
        pair = str(trade.get("pair") or "unknown")
        grouped[pair].append(trade)
    rows = []
    starting_balance = _starting_balance(source)
    for pair, trades in sorted(grouped.items()):
        profit_abs = sum(_trade_profit_abs(trade) for trade in trades)
        rows.append(
            {
                "pair": pair,
                "tradeCount": len(trades),
                "totalProfitAbs": round(profit_abs, 8),
                "totalReturnPct": round(profit_abs / starting_balance * 100, 4) if starting_balance else None,
                "winRate": _win_rate_for_trades(trades),
                "profitFactor": _profit_factor_for_trades(trades),
                "longTradeCount": sum(1 for trade in trades if not bool(trade.get("is_short"))),
                "shortTradeCount": sum(1 for trade in trades if bool(trade.get("is_short"))),
            }
        )
    return rows


def _monthly_performance(source: dict[str, Any]) -> list[dict[str, Any]]:
    periodic = source.get("periodic_breakdown", {})
    if isinstance(periodic, dict):
        rows = _compact_rows(periodic.get("month", []), max_rows=80)
        if rows:
            return rows
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in _trades(source):
        timestamp = trade.get("close_timestamp") or trade.get("open_timestamp")
        if timestamp is None:
            continue
        month = datetime.fromtimestamp(int(timestamp) / 1000, tz=UTC).strftime("%Y-%m")
        grouped[month].append(trade)
    rows = []
    starting_balance = _starting_balance(source)
    for month, trades in sorted(grouped.items()):
        profit_abs = sum(_trade_profit_abs(trade) for trade in trades)
        rows.append(
            {
                "month": month,
                "tradeCount": len(trades),
                "totalProfitAbs": round(profit_abs, 8),
                "totalReturnPct": round(profit_abs / starting_balance * 100, 4) if starting_balance else None,
                "winRate": _win_rate_for_trades(trades),
            }
        )
    return rows


def _exit_reason_breakdown(source: dict[str, Any]) -> list[dict[str, Any]]:
    summary = source.get("exit_reason_summary")
    if isinstance(summary, list) and summary:
        return _compact_rows(summary, max_rows=40)
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in _trades(source):
        grouped[str(trade.get("exit_reason") or "unknown")].append(trade)
    rows = []
    starting_balance = _starting_balance(source)
    for reason, trades in sorted(grouped.items()):
        profit_abs = sum(_trade_profit_abs(trade) for trade in trades)
        rows.append(
            {
                "exitReason": reason,
                "tradeCount": len(trades),
                "totalProfitAbs": round(profit_abs, 8),
                "totalReturnPct": round(profit_abs / starting_balance * 100, 4) if starting_balance else None,
                "winRate": _win_rate_for_trades(trades),
            }
        )
    return rows


def _pairlist(source: dict[str, Any]) -> list[str]:
    pairs = source.get("pairlist")
    if isinstance(pairs, list):
        return [str(pair) for pair in pairs]
    return sorted({str(trade.get("pair")) for trade in _trades(source) if trade.get("pair")})


def _load_baselines(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"available": False, "warnings": [f"Baseline report not found: {path.as_posix()}"]}
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else {"available": False, "warnings": ["Baseline report is not an object."]}


def _baseline_lookup(baseline_report: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = baseline_report.get("comparisonTable")
    lookup = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = f"{row.get('pair') or 'ALL'}:{row.get('timeframe') or 'ALL'}:{row.get('name')}"
            lookup[key] = row
    return lookup


def _build_baseline_comparison(source: dict[str, Any], baseline_report: dict[str, Any]) -> dict[str, Any]:
    strategy_return = _pct_from_source(source, "profit_total_pct", "profit_total")
    strategy_drawdown = _drawdown_pct(source)
    lookup = _baseline_lookup(baseline_report)
    equal_weight = None
    buy_hold_rows = []
    for row in lookup.values():
        name = str(row.get("name") or "")
        if name.startswith("EqualWeight") and row.get("timeframe") == "4h":
            equal_weight = row
        if name.startswith("BuyHold") and row.get("timeframe") == "4h":
            buy_hold_rows.append(row)
    equal_weight_return = _safe_float(equal_weight.get("totalReturnPct"), None) if equal_weight else None
    equal_weight_drawdown = _safe_float(equal_weight.get("maxDrawdownPct"), None) if equal_weight else None
    buy_hold_comparisons = []
    for row in buy_hold_rows:
        row_return = _safe_float(row.get("totalReturnPct"), None)
        row_drawdown = _safe_float(row.get("maxDrawdownPct"), None)
        buy_hold_comparisons.append(
            {
                "pair": row.get("pair"),
                "baselineReturnPct": row_return,
                "baselineMaxDrawdownPct": row_drawdown,
                "strategyExcessReturnPct": round(strategy_return - row_return, 4)
                if strategy_return is not None and row_return is not None
                else None,
                "drawdownDifferencePct": round(strategy_drawdown - row_drawdown, 4)
                if strategy_drawdown is not None and row_drawdown is not None
                else None,
            }
        )
    return {
        "sourceBaselineReport": DEFAULT_BASELINE_REPORT.as_posix(),
        "noTradeReturnPct": 0.0,
        "strategyReturnPct": strategy_return,
        "strategyMaxDrawdownPct": strategy_drawdown,
        "equalWeightReturnPct": equal_weight_return,
        "equalWeightMaxDrawdownPct": equal_weight_drawdown,
        "excessReturnVsNoTradePct": round(strategy_return, 4) if strategy_return is not None else None,
        "excessReturnVsEqualWeightPct": round(strategy_return - equal_weight_return, 4)
        if strategy_return is not None and equal_weight_return is not None
        else None,
        "drawdownDifferenceVsEqualWeightPct": round(strategy_drawdown - equal_weight_drawdown, 4)
        if strategy_drawdown is not None and equal_weight_drawdown is not None
        else None,
        "buyHoldComparisons": buy_hold_comparisons,
        "whetherBeatsBaseline": {
            "beatsNoTradeReturn": strategy_return is not None and strategy_return > 0,
            "beatsEqualWeightReturn": strategy_return is not None
            and equal_weight_return is not None
            and strategy_return > equal_weight_return,
            "hasLowerDrawdownThanEqualWeight": strategy_drawdown is not None
            and equal_weight_drawdown is not None
            and strategy_drawdown < equal_weight_drawdown,
        },
    }


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value) / 1000, tz=UTC)
    text = str(value)
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _load_regime_labels(path: Path) -> tuple[list[datetime], list[str], list[str]]:
    if not path.exists():
        return [], [], [f"Regime labels not found: {path.as_posix()}"]
    payload = _read_json(path)
    labels = payload.get("labels") if isinstance(payload, dict) else None
    if not isinstance(labels, list):
        return [], [], ["Regime label report does not contain a labels list."]
    points: list[tuple[datetime, str]] = []
    for row in labels:
        if not isinstance(row, dict):
            continue
        timestamp = _parse_datetime(row.get("timestamp"))
        if timestamp is None:
            continue
        points.append((timestamp, str(row.get("primaryLabel") or "unknown")))
    points.sort(key=lambda item: item[0])
    return [item[0] for item in points], [item[1] for item in points], []


def _regime_breakdown(source: dict[str, Any], path: Path) -> dict[str, Any]:
    times, labels, warnings = _load_regime_labels(path)
    if not times:
        return {
            "source": path.as_posix(),
            "available": False,
            "rows": [],
            "warnings": warnings,
        }
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    unknown_count = 0
    for trade in _trades(source):
        timestamp = trade.get("close_timestamp") or trade.get("open_timestamp")
        trade_time = _parse_datetime(timestamp)
        if trade_time is None:
            unknown_count += 1
            grouped["unknown"].append(trade)
            continue
        index = bisect_right(times, trade_time) - 1
        label = labels[index] if index >= 0 else "unknown"
        grouped[label].append(trade)
    rows = []
    starting_balance = _starting_balance(source)
    for label, trades in sorted(grouped.items()):
        profit_abs = sum(_trade_profit_abs(trade) for trade in trades)
        rows.append(
            {
                "regime": label,
                "tradeCount": len(trades),
                "longTradeCount": sum(1 for trade in trades if not bool(trade.get("is_short"))),
                "shortTradeCount": sum(1 for trade in trades if bool(trade.get("is_short"))),
                "totalProfitAbs": round(profit_abs, 8),
                "totalReturnPct": round(profit_abs / starting_balance * 100, 4) if starting_balance else None,
                "winRate": _win_rate_for_trades(trades),
                "profitFactor": _profit_factor_for_trades(trades),
            }
        )
    if unknown_count:
        warnings.append(f"{unknown_count} trades could not be aligned to a regime timestamp.")
    return {
        "source": path.as_posix(),
        "available": True,
        "rows": rows,
        "warnings": warnings,
    }


def _win_rate(source: dict[str, Any], trade_count: int) -> float | None:
    wins = _safe_int(source.get("wins"), None)
    if trade_count and wins is not None:
        return round(wins / trade_count * 100, 4)
    value = _safe_float(source.get("winrate"), None)
    if value is None:
        return _win_rate_for_trades(_trades(source))
    return round(value * 100 if 0 <= value <= 1 else value, 4)


def _research_decision(
    *,
    trade_count: int,
    total_return: float | None,
    drawdown: float | None,
    slippage_return: float | None,
    slippage_pf: float | None,
    baseline_comparison: dict[str, Any],
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if trade_count < 10:
        reasons.append("Trade count is below 10, so the sample is too small for continuation confidence.")
    else:
        reasons.append("Trade count is large enough for a first research read.")
    if slippage_return is None or slippage_return <= 0:
        reasons.append("0.05% one-way slippage-adjusted return is not positive.")
    else:
        reasons.append("0.05% one-way slippage-adjusted return is positive.")
    if slippage_pf is None or slippage_pf <= 1.05:
        reasons.append("0.05% one-way slippage-adjusted profit factor is not above 1.05.")
    else:
        reasons.append("0.05% one-way slippage-adjusted profit factor is above 1.05.")
    if drawdown is None:
        reasons.append("Max drawdown is unavailable.")
    elif drawdown > 45:
        reasons.append("Max drawdown is high for a low-frequency research candidate.")
    else:
        reasons.append("Max drawdown is within the first-pass research ceiling.")
    beats = baseline_comparison.get("whetherBeatsBaseline", {})
    if not beats.get("beatsNoTradeReturn"):
        reasons.append("Raw return does not beat NoTrade.")
    if not beats.get("beatsEqualWeightReturn"):
        reasons.append("Raw return does not beat EqualWeight BTC/ETH/SOL baseline.")
    if total_return is None:
        reasons.append("Raw return is unavailable.")
    worth = (
        trade_count >= 10
        and slippage_return is not None
        and slippage_return > 0
        and slippage_pf is not None
        and slippage_pf > 1.05
        and drawdown is not None
        and drawdown <= 45
        and bool(beats.get("beatsNoTradeReturn"))
    )
    return worth, reasons


def _build_report(
    *,
    result_file: Path,
    result_dir: Path,
    baseline_report_path: Path,
    regime_labels_path: Path,
) -> LowFrequencyDirectionalReport:
    warnings: list[str] = []
    path, source = _find_result(result_file, result_dir)
    if source is None or path is None:
        warnings.append("No real Freqtrade result found for AlphaPilotLowFrequencyDirectional4HV01.")
        report = LowFrequencyDirectionalReport(
            reportId=REPORT_ID,
            version=VERSION,
            isMock=True,
            dryRunApproved=False,
            liveTradingApproved=False,
            strategyId=STRATEGY_ID,
            strategyName=STRATEGY_NAME,
            strategyVersion=STRATEGY_VERSION,
            strategyClass=STRATEGY_CLASS,
            pairs=[],
            timeframe="4h",
            timerange="unknown",
            resultFile=result_file.as_posix(),
            tradeCount=0,
            longTradeCount=0,
            shortTradeCount=0,
            totalReturnPct=None,
            slippageAdjustedTotalReturnPct=None,
            maxDrawdownPct=None,
            profitFactor=None,
            slippageAdjustedProfitFactor=None,
            winRate=None,
            maxConsecutiveLosses=None,
            longMetrics={},
            shortMetrics={},
            pairPerformance=[],
            monthlyPerformance=[],
            regimeBreakdown={"available": False, "rows": [], "warnings": ["No real backtest result available."]},
            exitReasonBreakdown=[],
            baselineComparison={"available": False},
            slippageModel={
                "freqtradeFeeRateOneWay": 0.0005,
                "slippageAppliedByFreqtrade": False,
                "slippageAppliedByPostProcessing": True,
                "stressRatesOneWay": [0.0005, 0.001],
            },
            researchWorthContinuing=False,
            researchDecisionReasons=["No real backtest result was available."],
            safetyBoundary=_safety_boundary(freqtrade_backtest_executed=False),
            generatedAt=utc_now(),
            warnings=warnings,
        )
        return report

    trades = _trades(source)
    trade_count = _safe_int(source.get("total_trades", source.get("trade_count")), len(trades)) or 0
    long_trade_count = _safe_int(source.get("trade_count_long"), None)
    short_trade_count = _safe_int(source.get("trade_count_short"), None)
    if long_trade_count is None:
        long_trade_count = sum(1 for trade in trades if not bool(trade.get("is_short")))
    if short_trade_count is None:
        short_trade_count = sum(1 for trade in trades if bool(trade.get("is_short")))
    starting_balance = _starting_balance(source)
    slippage_stress = [_slippage_adjustment_for_trades(trades, starting_balance, rate) for rate in (0.0005, 0.001)]
    baseline_report = _load_baselines(baseline_report_path)
    baseline_comparison = _build_baseline_comparison(source, baseline_report)
    regime_breakdown = _regime_breakdown(source, regime_labels_path)
    total_return = _pct_from_source(source, "profit_total_pct", "profit_total")
    drawdown = _drawdown_pct(source)
    profit_factor = _safe_float(source.get("profit_factor"), None)
    slippage_return = slippage_stress[0].get("totalReturnPct")
    slippage_pf = slippage_stress[0].get("profitFactor")
    research_worth, decision_reasons = _research_decision(
        trade_count=trade_count,
        total_return=total_return,
        drawdown=drawdown,
        slippage_return=slippage_return,
        slippage_pf=slippage_pf,
        baseline_comparison=baseline_comparison,
    )
    if trade_count == 0:
        warnings.append("The real backtest completed but produced zero trades.")
    warnings.extend(regime_breakdown.get("warnings") or [])
    report = LowFrequencyDirectionalReport(
        reportId=REPORT_ID,
        version=VERSION,
        isMock=False,
        dryRunApproved=False,
        liveTradingApproved=False,
        strategyId=STRATEGY_ID,
        strategyName=STRATEGY_NAME,
        strategyVersion=STRATEGY_VERSION,
        strategyClass=STRATEGY_CLASS,
        pairs=_pairlist(source),
        timeframe=str(source.get("timeframe") or "4h"),
        timerange=str(source.get("timerange") or "unknown"),
        resultFile=path.as_posix(),
        tradeCount=trade_count,
        longTradeCount=long_trade_count or 0,
        shortTradeCount=short_trade_count or 0,
        totalReturnPct=total_return,
        slippageAdjustedTotalReturnPct=slippage_return,
        maxDrawdownPct=drawdown,
        profitFactor=profit_factor,
        slippageAdjustedProfitFactor=slippage_pf,
        winRate=_win_rate(source, trade_count),
        maxConsecutiveLosses=_max_consecutive_losses(source),
        longMetrics=_direction_metrics(source, is_short=False),
        shortMetrics=_direction_metrics(source, is_short=True),
        pairPerformance=_pair_performance(source),
        monthlyPerformance=_monthly_performance(source),
        regimeBreakdown=regime_breakdown,
        exitReasonBreakdown=_exit_reason_breakdown(source),
        baselineComparison=baseline_comparison,
        slippageModel={
            "freqtradeFeeRateOneWay": 0.0005,
            "slippageAppliedByFreqtrade": False,
            "slippageAppliedByPostProcessing": True,
            "stressRatesOneWay": [0.0005, 0.001],
            "stressResults": slippage_stress,
        },
        researchWorthContinuing=research_worth,
        researchDecisionReasons=decision_reasons,
        safetyBoundary=_safety_boundary(freqtrade_backtest_executed=True),
        generatedAt=utc_now(),
        warnings=warnings,
    )
    return report


def _safety_boundary(*, freqtrade_backtest_executed: bool) -> dict[str, bool]:
    return {
        "strategyImplemented": True,
        "freqtradeBacktestExecuted": freqtrade_backtest_executed,
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "tradeApiUsed": False,
        "withdrawApiUsed": False,
        "apiKeyStored": False,
        "accountRead": False,
        "positionRead": False,
        "orderCreated": False,
        "autoTradingUsed": False,
    }


def render_summary(report: LowFrequencyDirectionalReport) -> str:
    payload = report.to_dict()
    lines = [
        "# AlphaPilot V13.4.34 Low-Frequency Directional 4H Research Report",
        "",
        "This report summarizes a real local Freqtrade research backtest when available. It is not Dry-run, not live trading, and not a trading command.",
        "",
        "## Run Summary",
        "",
        f"- isMock: {payload['isMock']}",
        f"- strategy: {payload['strategyClass']}",
        f"- result file: {payload['resultFile']}",
        f"- pairs: {', '.join(payload['pairs']) if payload['pairs'] else '--'}",
        f"- timeframe: {payload['timeframe']}",
        f"- timerange: {payload['timerange']}",
        f"- tradeCount: {payload['tradeCount']}",
        f"- longTradeCount: {payload['longTradeCount']}",
        f"- shortTradeCount: {payload['shortTradeCount']}",
        f"- totalReturnPct: {payload['totalReturnPct']}",
        f"- slippageAdjustedTotalReturnPct: {payload['slippageAdjustedTotalReturnPct']}",
        f"- maxDrawdownPct: {payload['maxDrawdownPct']}",
        f"- profitFactor: {payload['profitFactor']}",
        f"- slippageAdjustedProfitFactor: {payload['slippageAdjustedProfitFactor']}",
        f"- winRate: {payload['winRate']}",
        f"- researchWorthContinuing: {payload['researchWorthContinuing']}",
        "",
        "## Direction Metrics",
        "",
        "| Direction | Trades | Return % | Win Rate % | Profit Factor | Avg Duration Min | Max Consecutive Losses |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in ("longMetrics", "shortMetrics"):
        row = payload.get(key) or {}
        lines.append(
            "| {direction} | {trades} | {ret} | {win} | {pf} | {duration} | {losses} |".format(
                direction=row.get("direction") or key,
                trades=row.get("tradeCount"),
                ret=row.get("totalReturnPct"),
                win=row.get("winRate"),
                pf=row.get("profitFactor"),
                duration=row.get("averageDurationMinutes"),
                losses=row.get("maxConsecutiveLosses"),
            )
        )
    lines.extend(["", "## Pair Performance", ""])
    lines.append("| Pair | Trades | Profit % | Profit Abs | Wins | Drawdown % |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: |")
    for row in payload["pairPerformance"][:20]:
        lines.append(
            "| {pair} | {trades} | {ret} | {abs} | {wins} | {dd} |".format(
                pair=row.get("key") or row.get("pair") or "--",
                trades=row.get("trades") or row.get("tradeCount"),
                ret=row.get("profit_total_pct") or row.get("totalReturnPct"),
                abs=row.get("profit_total_abs") or row.get("totalProfitAbs"),
                wins=row.get("wins") or row.get("winRate"),
                dd=row.get("max_drawdown_account_pct") or row.get("maxDrawdownPct"),
            )
        )
    lines.extend(["", "## Baseline Comparison", ""])
    baseline = payload["baselineComparison"]
    for key in (
        "excessReturnVsNoTradePct",
        "excessReturnVsEqualWeightPct",
        "drawdownDifferenceVsEqualWeightPct",
    ):
        lines.append(f"- {key}: {baseline.get(key)}")
    lines.extend(["", "## Regime Breakdown", ""])
    regime = payload["regimeBreakdown"]
    if regime.get("available"):
        lines.append("| Regime | Trades | Long | Short | Return % | Win Rate % | Profit Factor |")
        lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
        for row in regime.get("rows", []):
            lines.append(
                "| {regime} | {trades} | {longs} | {shorts} | {ret} | {win} | {pf} |".format(
                    regime=row.get("regime"),
                    trades=row.get("tradeCount"),
                    longs=row.get("longTradeCount"),
                    shorts=row.get("shortTradeCount"),
                    ret=row.get("totalReturnPct"),
                    win=row.get("winRate"),
                    pf=row.get("profitFactor"),
                )
            )
    else:
        lines.append("- Regime breakdown unavailable.")
    lines.extend(["", "## Research Decision Reasons", ""])
    for reason in payload["researchDecisionReasons"]:
        lines.append(f"- {reason}")
    lines.extend(["", "## Safety Boundary", ""])
    for key, value in payload["safetyBoundary"].items():
        lines.append(f"- {key}: {value}")
    if payload["warnings"]:
        lines.extend(["", "## Warnings", ""])
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.34 low-frequency directional 4H report.")
    parser.add_argument("--result-file", default=DEFAULT_RESULT_FILE.as_posix())
    parser.add_argument("--result-dir", default=DEFAULT_RESULT_DIR.as_posix())
    parser.add_argument("--baseline-report", default=DEFAULT_BASELINE_REPORT.as_posix())
    parser.add_argument("--regime-labels", default=DEFAULT_REGIME_LABELS.as_posix())
    parser.add_argument("--output-report", default=DEFAULT_OUTPUT_REPORT.as_posix())
    parser.add_argument("--output-summary", default=DEFAULT_OUTPUT_SUMMARY.as_posix())
    args = parser.parse_args()

    report = _build_report(
        result_file=Path(args.result_file),
        result_dir=Path(args.result_dir),
        baseline_report_path=Path(args.baseline_report),
        regime_labels_path=Path(args.regime_labels),
    )
    _write_json(Path(args.output_report), report.to_dict())
    _write_text(Path(args.output_summary), render_summary(report))
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_summary}")
    print(f"isMock={report.isMock}")
    print(f"researchWorthContinuing={report.researchWorthContinuing}")


if __name__ == "__main__":
    main()
