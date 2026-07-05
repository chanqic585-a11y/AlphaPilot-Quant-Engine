"""Generate V13.4.35 multi-strategy batch research report.

This generator reads local Freqtrade backtest artifacts and a local manifest.
It does not run backtests, enter Dry-run, call private exchange APIs, read
accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.reports.generate_low_frequency_directional_report import (
    _drawdown_pct,
    _exit_reason_breakdown,
    _max_consecutive_losses,
    _monthly_performance,
    _pair_performance,
    _pct_from_source,
    _profit_factor_for_trades,
    _read_freqtrade_payload,
    _safe_float,
    _safe_int,
    _slippage_adjustment_for_trades,
    _trades,
    _win_rate,
    _win_rate_for_trades,
)
from alphapilot.reports.multi_strategy_batch_report_schema import (
    MultiStrategyBatchReport,
    MultiStrategyResult,
)


REPORT_ID = "v13_4_35_multi_strategy_batch_report"
VERSION = "V13.4.35"
DEFAULT_MANIFEST = Path("reports/v13_4_35_multi_strategy_batch_manifest.json")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_4_35_multi_strategy_batch_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_35_multi_strategy_batch_summary.md")
DEFAULT_BASELINE_REPORT = Path("reports/v13_4_32_low_frequency_baseline_report.json")
DEFAULT_V13_4_34_REPORT = Path("reports/v13_4_34_low_frequency_directional_4h_report.json")

STRATEGY_DIRECTIONS = {
    "AlphaPilotBatchA_EMATrendLong4H": "long_only",
    "AlphaPilotBatchB_EMATrendShort4H": "short_only",
    "AlphaPilotBatchC_BreakoutRetestLong4H": "long_only",
    "AlphaPilotBatchD_BreakdownRetestShort4H": "short_only",
    "AlphaPilotBatchE_BollingerReversionLong4H": "long_only",
    "AlphaPilotBatchF_BollingerReversionShort4H": "short_only",
    "AlphaPilotBatchG_RelativeStrengthLong4H": "long_only",
    "AlphaPilotBatchH_VolatilityCompressionBreakout4H": "long_only",
}

STRATEGY_IDS = {
    "AlphaPilotBatchA_EMATrendLong4H": "alpha_batch_a_ema_trend_long_4h",
    "AlphaPilotBatchB_EMATrendShort4H": "alpha_batch_b_ema_trend_short_4h",
    "AlphaPilotBatchC_BreakoutRetestLong4H": "alpha_batch_c_breakout_retest_long_4h",
    "AlphaPilotBatchD_BreakdownRetestShort4H": "alpha_batch_d_breakdown_retest_short_4h",
    "AlphaPilotBatchE_BollingerReversionLong4H": "alpha_batch_e_bollinger_reversion_long_4h",
    "AlphaPilotBatchF_BollingerReversionShort4H": "alpha_batch_f_bollinger_reversion_short_4h",
    "AlphaPilotBatchG_RelativeStrengthLong4H": "alpha_batch_g_relative_strength_long_4h",
    "AlphaPilotBatchH_VolatilityCompressionBreakout4H": "alpha_batch_h_volatility_compression_breakout_4h",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _select_strategy_payload(payload: dict[str, Any] | list[Any], strategy_class: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict):
        return None
    if strategy_class in strategy and isinstance(strategy[strategy_class], dict):
        return strategy[strategy_class]
    for value in strategy.values():
        if isinstance(value, dict) and value.get("strategy_name") == strategy_class:
            return value
    return None


def _load_baseline_report(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = _read_json(path)
    return payload if isinstance(payload, dict) else {}


def _equal_weight_baseline(baseline_report: dict[str, Any]) -> dict[str, Any] | None:
    for row in baseline_report.get("comparisonTable", []) or []:
        if not isinstance(row, dict):
            continue
        if str(row.get("name") or "").startswith("EqualWeight") and row.get("timeframe") == "4h":
            return row
    return None


def _baseline_comparison(source: dict[str, Any], baseline_report: dict[str, Any]) -> dict[str, Any]:
    total_return = _pct_from_source(source, "profit_total_pct", "profit_total")
    drawdown = _drawdown_pct(source)
    equal_weight = _equal_weight_baseline(baseline_report)
    equal_weight_return = _safe_float(equal_weight.get("totalReturnPct"), None) if equal_weight else None
    equal_weight_drawdown = _safe_float(equal_weight.get("maxDrawdownPct"), None) if equal_weight else None
    return {
        "beatsNoTrade": total_return is not None and total_return > 0,
        "beatsEqualWeight": total_return is not None
        and equal_weight_return is not None
        and total_return > equal_weight_return,
        "strategyReturnPct": total_return,
        "strategyMaxDrawdownPct": drawdown,
        "equalWeightReturnPct": equal_weight_return,
        "equalWeightMaxDrawdownPct": equal_weight_drawdown,
        "excessReturnVsEqualWeight": round(total_return - equal_weight_return, 4)
        if total_return is not None and equal_weight_return is not None
        else None,
        "drawdownVsEqualWeight": round(drawdown - equal_weight_drawdown, 4)
        if drawdown is not None and equal_weight_drawdown is not None
        else None,
    }


def _starting_balance(source: dict[str, Any]) -> float:
    return _safe_float(source.get("starting_balance"), 0.0) or 0.0


def _fees_paid(source: dict[str, Any]) -> float | None:
    trades = _trades(source)
    if not trades:
        return 0.0
    total = 0.0
    for trade in trades:
        stake = _safe_float(trade.get("max_stake_amount"), _safe_float(trade.get("stake_amount"), 0.0)) or 0.0
        leverage = _safe_float(trade.get("leverage"), 1.0) or 1.0
        notional = stake * leverage
        fee_open = _safe_float(trade.get("fee_open"), 0.0) or 0.0
        fee_close = _safe_float(trade.get("fee_close"), 0.0) or 0.0
        total += notional * (fee_open + fee_close)
    return round(total, 8)


def _pair_dominance(trades: list[dict[str, Any]]) -> float:
    if not trades:
        return 0.0
    counts: dict[str, int] = defaultdict(int)
    for trade in trades:
        counts[str(trade.get("pair") or "unknown")] += 1
    return max(counts.values()) / len(trades)


def _month_dominance(trades: list[dict[str, Any]]) -> float:
    if not trades:
        return 0.0
    counts: dict[str, int] = defaultdict(int)
    for trade in trades:
        timestamp = trade.get("close_timestamp") or trade.get("open_timestamp")
        if timestamp is None:
            counts["unknown"] += 1
            continue
        month = datetime.fromtimestamp(int(timestamp) / 1000, tz=UTC).strftime("%Y-%m")
        counts[month] += 1
    return max(counts.values()) / len(trades)


def _research_decision(
    *,
    source: dict[str, Any],
    baseline_comparison: dict[str, Any],
    slippage_profit_factor: float | None,
    slippage_return: float | None,
    v13_4_34_drawdown: float | None,
) -> tuple[bool, list[str]]:
    trades = _trades(source)
    trade_count = _safe_int(source.get("total_trades", source.get("trade_count")), len(trades)) or 0
    total_return = _pct_from_source(source, "profit_total_pct", "profit_total")
    drawdown = _drawdown_pct(source)
    pair_dom = _pair_dominance(trades)
    month_dom = _month_dominance(trades)
    reasons: list[str] = []
    if trade_count < 5:
        reasons.append("Trade count is below 5.")
    elif trade_count > 500:
        reasons.append("Trade count is excessive for the low-frequency research scope.")
    else:
        reasons.append("Trade count is within the first-pass low-frequency range.")
    if slippage_profit_factor is None or slippage_profit_factor <= 1.05:
        reasons.append("0.05% one-way slippage-adjusted profit factor is not above 1.05.")
    else:
        reasons.append("0.05% one-way slippage-adjusted profit factor is above 1.05.")
    if slippage_return is None or slippage_return <= 0:
        reasons.append("0.05% one-way slippage-adjusted return is not positive.")
    else:
        reasons.append("0.05% one-way slippage-adjusted return is positive.")
    if total_return is None or total_return <= 0:
        reasons.append("Raw return does not beat NoTrade.")
    else:
        reasons.append("Raw return beats NoTrade.")
    if drawdown is None:
        reasons.append("Max drawdown is unavailable.")
    elif v13_4_34_drawdown is not None and drawdown < v13_4_34_drawdown - 10:
        reasons.append("Max drawdown is noticeably below V13.4.34.")
    else:
        reasons.append("Max drawdown is not noticeably below V13.4.34.")
    if pair_dom > 0.75:
        reasons.append("Trades are dominated by one pair.")
    if month_dom > 0.5:
        reasons.append("Trades are dominated by one month.")
    worth = (
        5 <= trade_count <= 500
        and slippage_profit_factor is not None
        and slippage_profit_factor > 1.05
        and slippage_return is not None
        and slippage_return > 0
        and total_return is not None
        and total_return > 0
        and drawdown is not None
        and v13_4_34_drawdown is not None
        and drawdown < v13_4_34_drawdown - 10
        and pair_dom <= 0.75
        and month_dom <= 0.5
    )
    if baseline_comparison.get("beatsEqualWeight"):
        reasons.append("Raw return beats EqualWeight BTC/ETH/SOL baseline.")
    else:
        reasons.append("Raw return does not beat EqualWeight BTC/ETH/SOL baseline.")
    return worth, reasons


def _build_strategy_result(
    *,
    manifest_entry: dict[str, Any],
    baseline_report: dict[str, Any],
    v13_4_34_drawdown: float | None,
) -> MultiStrategyResult:
    strategy_class = str(manifest_entry.get("strategyClass") or "unknown")
    result_path = manifest_entry.get("resultZipPath")
    warnings: list[str] = []
    if manifest_entry.get("status") != "success" or not result_path:
        return MultiStrategyResult(
            strategyId=STRATEGY_IDS.get(strategy_class, strategy_class),
            strategyClass=strategy_class,
            direction=STRATEGY_DIRECTIONS.get(strategy_class, "unknown"),
            resultPath=result_path,
            status=str(manifest_entry.get("status") or "failed"),
            isRealBacktest=False,
            tradeCount=0,
            totalReturnPct=None,
            slippageAdjustedReturnPct=None,
            maxDrawdownPct=None,
            profitFactor=None,
            slippageAdjustedProfitFactor=None,
            winRate=None,
            maxConsecutiveLosses=None,
            feesPaid=None,
            slippageCost=None,
            pairPerformance=[],
            monthlyPerformance=[],
            exitReasonBreakdown=[],
            baselineComparison={},
            researchWorthContinuing=False,
            decisionReasons=[str(manifest_entry.get("error") or "Strategy did not produce a successful result.")],
            warnings=warnings,
        )
    path = Path(str(result_path))
    if not path.exists():
        return MultiStrategyResult(
            strategyId=STRATEGY_IDS.get(strategy_class, strategy_class),
            strategyClass=strategy_class,
            direction=STRATEGY_DIRECTIONS.get(strategy_class, "unknown"),
            resultPath=str(path),
            status="result_missing",
            isRealBacktest=False,
            tradeCount=0,
            totalReturnPct=None,
            slippageAdjustedReturnPct=None,
            maxDrawdownPct=None,
            profitFactor=None,
            slippageAdjustedProfitFactor=None,
            winRate=None,
            maxConsecutiveLosses=None,
            feesPaid=None,
            slippageCost=None,
            pairPerformance=[],
            monthlyPerformance=[],
            exitReasonBreakdown=[],
            baselineComparison={},
            researchWorthContinuing=False,
            decisionReasons=[f"Result path not found: {path.as_posix()}"],
            warnings=warnings,
        )
    payload = _read_freqtrade_payload(path)
    source = _select_strategy_payload(payload, strategy_class)
    if source is None:
        return MultiStrategyResult(
            strategyId=STRATEGY_IDS.get(strategy_class, strategy_class),
            strategyClass=strategy_class,
            direction=STRATEGY_DIRECTIONS.get(strategy_class, "unknown"),
            resultPath=str(path),
            status="parse_failed",
            isRealBacktest=False,
            tradeCount=0,
            totalReturnPct=None,
            slippageAdjustedReturnPct=None,
            maxDrawdownPct=None,
            profitFactor=None,
            slippageAdjustedProfitFactor=None,
            winRate=None,
            maxConsecutiveLosses=None,
            feesPaid=None,
            slippageCost=None,
            pairPerformance=[],
            monthlyPerformance=[],
            exitReasonBreakdown=[],
            baselineComparison={},
            researchWorthContinuing=False,
            decisionReasons=["Could not find strategy payload in Freqtrade result."],
            warnings=warnings,
        )
    trades = _trades(source)
    starting_balance = _starting_balance(source)
    slip_005 = _slippage_adjustment_for_trades(trades, starting_balance, 0.0005)
    baseline = _baseline_comparison(source, baseline_report)
    worth, reasons = _research_decision(
        source=source,
        baseline_comparison=baseline,
        slippage_profit_factor=slip_005.get("profitFactor"),
        slippage_return=slip_005.get("totalReturnPct"),
        v13_4_34_drawdown=v13_4_34_drawdown,
    )
    trade_count = _safe_int(source.get("total_trades", source.get("trade_count")), len(trades)) or 0
    if trade_count == 0:
        warnings.append("Backtest completed but produced zero trades.")
    return MultiStrategyResult(
        strategyId=STRATEGY_IDS.get(strategy_class, strategy_class),
        strategyClass=strategy_class,
        direction=STRATEGY_DIRECTIONS.get(strategy_class, "unknown"),
        resultPath=str(path),
        status="success",
        isRealBacktest=True,
        tradeCount=trade_count,
        totalReturnPct=_pct_from_source(source, "profit_total_pct", "profit_total"),
        slippageAdjustedReturnPct=slip_005.get("totalReturnPct"),
        maxDrawdownPct=_drawdown_pct(source),
        profitFactor=_safe_float(source.get("profit_factor"), None),
        slippageAdjustedProfitFactor=slip_005.get("profitFactor"),
        winRate=_win_rate(source, trade_count),
        maxConsecutiveLosses=_max_consecutive_losses(source),
        feesPaid=_fees_paid(source),
        slippageCost=slip_005.get("totalSlippageCost"),
        pairPerformance=_pair_performance(source),
        monthlyPerformance=_monthly_performance(source),
        exitReasonBreakdown=_exit_reason_breakdown(source),
        baselineComparison=baseline,
        researchWorthContinuing=worth,
        decisionReasons=reasons,
        warnings=warnings,
    )


def _leaderboard(results: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    rows = [
        {
            "rank": 0,
            "strategyClass": item["strategyClass"],
            "direction": item["direction"],
            "tradeCount": item["tradeCount"],
            "totalReturnPct": item["totalReturnPct"],
            "slippageAdjustedReturnPct": item["slippageAdjustedReturnPct"],
            "maxDrawdownPct": item["maxDrawdownPct"],
            "profitFactor": item["profitFactor"],
            "slippageAdjustedProfitFactor": item["slippageAdjustedProfitFactor"],
            "winRate": item["winRate"],
            "researchWorthContinuing": item["researchWorthContinuing"],
        }
        for item in results
        if item.get("isRealBacktest") and item.get(key) is not None
    ]
    rows.sort(key=lambda item: item.get(key) or -999999, reverse=True)
    for index, row in enumerate(rows, start=1):
        row["rank"] = index
    return rows


def _batch_baseline_summary(strategy_results: list[dict[str, Any]]) -> dict[str, Any]:
    real = [item for item in strategy_results if item.get("isRealBacktest")]
    return {
        "strategyCount": len(strategy_results),
        "realBacktestCount": len(real),
        "beatsNoTradeCount": sum(1 for item in real if item.get("baselineComparison", {}).get("beatsNoTrade")),
        "beatsEqualWeightCount": sum(1 for item in real if item.get("baselineComparison", {}).get("beatsEqualWeight")),
        "researchWorthContinuingCount": sum(1 for item in real if item.get("researchWorthContinuing")),
    }


def _recommendations(strategy_results: list[dict[str, Any]]) -> list[str]:
    continuing = [item for item in strategy_results if item.get("researchWorthContinuing")]
    if not continuing:
        return [
            "No strategy passed the first research continuation gate.",
            "Archive weak OHLCV-only batch candidates as research references.",
            "Consider V13.4.36 as OHLCV batch failure review and funding/OI route start.",
        ]
    names = ", ".join(item["strategyClass"] for item in continuing)
    return [
        f"Focus the next review on: {names}.",
        "Do not approve Dry-run from this batch report alone.",
        "Run focused expanded validation and inspect pair/month/regime concentration before any next gate.",
    ]


def _safety_boundary() -> dict[str, bool]:
    return {
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


def build_report(
    *,
    manifest_path: Path,
    baseline_report_path: Path,
    v13_4_34_report_path: Path,
) -> MultiStrategyBatchReport:
    warnings: list[str] = []
    if not manifest_path.exists():
        warnings.append(f"Manifest not found: {manifest_path.as_posix()}")
        manifest = {}
    else:
        manifest = _read_json(manifest_path)
    baseline_report = _load_baseline_report(baseline_report_path)
    v13_4_34 = _read_json(v13_4_34_report_path) if v13_4_34_report_path.exists() else {}
    v13_4_34_drawdown = _safe_float(v13_4_34.get("maxDrawdownPct"), None) if isinstance(v13_4_34, dict) else None
    strategy_results = [
        _build_strategy_result(
            manifest_entry=item,
            baseline_report=baseline_report,
            v13_4_34_drawdown=v13_4_34_drawdown,
        ).to_dict()
        for item in manifest.get("results", []) or []
        if isinstance(item, dict)
    ]
    failed = [
        {
            "strategyClass": item["strategyClass"],
            "status": item["status"],
            "resultPath": item["resultPath"],
            "reasons": item["decisionReasons"],
        }
        for item in strategy_results
        if not item.get("isRealBacktest")
    ]
    leaderboard_raw = _leaderboard(strategy_results, "totalReturnPct")
    leaderboard_slip = _leaderboard(strategy_results, "slippageAdjustedReturnPct")
    is_mock = not any(item.get("isRealBacktest") for item in strategy_results)
    if is_mock:
        warnings.append("No real strategy result was parsed; report is mock/blocked.")
    return MultiStrategyBatchReport(
        reportId=REPORT_ID,
        version=VERSION,
        isMock=is_mock,
        dryRunApproved=False,
        liveTradingApproved=False,
        timerange=str(manifest.get("timerange") or "unknown"),
        timeframe=str(manifest.get("timeframe") or "4h"),
        pairs=list(manifest.get("pairs") or []),
        manifestPath=manifest_path.as_posix(),
        expandedTop10Executed=bool(manifest.get("expandedTop10Executed", False)),
        expandedTop10Reason=manifest.get("expandedTop10Reason")
        or (
            "Skipped in V13.4.35 because the required BTC/ETH/SOL batch already produced a clear all-strategy failure result."
            if not bool(manifest.get("expandedTop10Executed", False))
            else None
        ),
        strategyResults=strategy_results,
        leaderboardRaw=leaderboard_raw,
        leaderboardSlippageAdjusted=leaderboard_slip,
        longOnlyResults=[item for item in strategy_results if item.get("direction") == "long_only"],
        shortOnlyResults=[item for item in strategy_results if item.get("direction") == "short_only"],
        mixedDirectionResults=[item for item in strategy_results if item.get("direction") == "mixed_direction"],
        bestRawStrategy=leaderboard_raw[0] if leaderboard_raw else None,
        bestSlippageAdjustedStrategy=leaderboard_slip[0] if leaderboard_slip else None,
        failedStrategies=failed,
        baselineComparison=_batch_baseline_summary(strategy_results),
        recommendations=_recommendations(strategy_results),
        slippageModel={
            "freqtradeFeeRateOneWay": 0.0005,
            "slippageStressRatesOneWay": [0.0005, 0.001],
            "slippageAppliedByFreqtrade": False,
            "slippageAppliedByPostProcessing": True,
        },
        safetyBoundary=_safety_boundary(),
        generatedAt=utc_now(),
        warnings=warnings,
    )


def render_summary(report: MultiStrategyBatchReport) -> str:
    payload = report.to_dict()
    lines = [
        "# AlphaPilot V13.4.35 Multi-Strategy Batch Research Backtest",
        "",
        "This report ranks research-only Freqtrade backtests. It is not Dry-run, not live trading, and not a trading command.",
        "",
        "## Batch Summary",
        "",
        f"- isMock: {payload['isMock']}",
        f"- timerange: {payload['timerange']}",
        f"- timeframe: {payload['timeframe']}",
        f"- pairs: {', '.join(payload['pairs'])}",
        f"- expandedTop10Executed: {payload['expandedTop10Executed']}",
        f"- expandedTop10Reason: {payload['expandedTop10Reason']}",
        f"- strategyCount: {len(payload['strategyResults'])}",
        f"- failedStrategies: {len(payload['failedStrategies'])}",
        f"- bestRawStrategy: {(payload['bestRawStrategy'] or {}).get('strategyClass')}",
        f"- bestSlippageAdjustedStrategy: {(payload['bestSlippageAdjustedStrategy'] or {}).get('strategyClass')}",
        "",
        "## Leaderboard Raw",
        "",
        "| Rank | Strategy | Direction | Trades | Return % | Max DD % | PF | Worth Continuing |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in payload["leaderboardRaw"]:
        lines.append(
            "| {rank} | {strategy} | {direction} | {trades} | {ret} | {dd} | {pf} | {worth} |".format(
                rank=row.get("rank"),
                strategy=row.get("strategyClass"),
                direction=row.get("direction"),
                trades=row.get("tradeCount"),
                ret=row.get("totalReturnPct"),
                dd=row.get("maxDrawdownPct"),
                pf=row.get("profitFactor"),
                worth=row.get("researchWorthContinuing"),
            )
        )
    lines.extend(
        [
            "",
            "## Leaderboard Slippage Adjusted",
            "",
            "| Rank | Strategy | Direction | Trades | Slippage Return % | Slippage PF | Worth Continuing |",
            "| ---: | --- | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in payload["leaderboardSlippageAdjusted"]:
        lines.append(
            "| {rank} | {strategy} | {direction} | {trades} | {ret} | {pf} | {worth} |".format(
                rank=row.get("rank"),
                strategy=row.get("strategyClass"),
                direction=row.get("direction"),
                trades=row.get("tradeCount"),
                ret=row.get("slippageAdjustedReturnPct"),
                pf=row.get("slippageAdjustedProfitFactor"),
                worth=row.get("researchWorthContinuing"),
            )
        )
    lines.extend(["", "## Baseline Comparison Summary", ""])
    for key, value in payload["baselineComparison"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Failed Strategies", ""])
    if payload["failedStrategies"]:
        for item in payload["failedStrategies"]:
            lines.append(f"- {item.get('strategyClass')}: {item.get('status')}")
    else:
        lines.append("- none")
    lines.extend(["", "## Recommendations", ""])
    for item in payload["recommendations"]:
        lines.append(f"- {item}")
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
    parser = argparse.ArgumentParser(description="Generate V13.4.35 multi-strategy batch report.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST.as_posix())
    parser.add_argument("--baseline-report", default=DEFAULT_BASELINE_REPORT.as_posix())
    parser.add_argument("--v13-4-34-report", default=DEFAULT_V13_4_34_REPORT.as_posix())
    parser.add_argument("--output-report", default=DEFAULT_OUTPUT_REPORT.as_posix())
    parser.add_argument("--output-summary", default=DEFAULT_OUTPUT_SUMMARY.as_posix())
    args = parser.parse_args()
    report = build_report(
        manifest_path=Path(args.manifest),
        baseline_report_path=Path(args.baseline_report),
        v13_4_34_report_path=Path(args.v13_4_34_report),
    )
    _write_json(Path(args.output_report), report.to_dict())
    _write_text(Path(args.output_summary), render_summary(report))
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_summary}")
    print(f"isMock={report.isMock}")
    print(f"realBacktestCount={report.baselineComparison.get('realBacktestCount')}")


if __name__ == "__main__":
    main()
