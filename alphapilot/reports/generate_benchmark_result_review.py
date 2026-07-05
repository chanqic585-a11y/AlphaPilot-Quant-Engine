"""Generate V13.4.24 benchmark result review.

This module reads existing local benchmark reports only. It does not run a new
backtest, modify benchmark strategies, enter Dry-run, call private exchange
APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.reports.benchmark_result_review_schema import BenchmarkResultReviewReport

DEFAULT_BENCHMARK_REPORT = Path("reports/v13_4_23_benchmark_suite_report.json")
DEFAULT_BENCHMARK_SUMMARY = Path("reports/v13_4_23_benchmark_suite_summary.md")
DEFAULT_BENCHMARK_MANIFEST = Path("reports/v13_4_23_benchmark_manifest.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_24_benchmark_result_review.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_24_benchmark_result_summary.md")
DEFAULT_STATUS_ARCHIVE = Path("reports/v13_4_24_benchmark_status_archive.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 4) -> float | None:
    number = _num(value)
    return round(number, digits) if number is not None else None


def _fmt(value: Any) -> str:
    number = _num(value)
    if number is None:
        return "unavailable"
    return str(round(number, 4))


def _benchmark_label(row: dict[str, Any]) -> str:
    return str(row.get("className") or row.get("benchmarkId") or row.get("name") or "unknown")


def _active_benchmarks(report: dict[str, Any]) -> list[dict[str, Any]]:
    return [row for row in report.get("benchmarks", []) if row.get("type") == "freqtrade_backtest_baseline"]


def _find_by_id(report: dict[str, Any], benchmark_id: str) -> dict[str, Any]:
    for row in report.get("benchmarks", []):
        if row.get("benchmarkId") == benchmark_id:
            return row
    return {}


def _best_active(report: dict[str, Any]) -> dict[str, Any]:
    target = report.get("bestBenchmarkSlippageAdjusted") or report.get("bestBenchmarkRaw")
    for row in _active_benchmarks(report):
        if row.get("className") == target or row.get("benchmarkId") == target:
            return row
    active = _active_benchmarks(report)
    return sorted(
        active,
        key=lambda item: _num(item.get("slippageAdjustedTotalReturnPct")) if _num(item.get("slippageAdjustedTotalReturnPct")) is not None else -999999,
        reverse=True,
    )[0] if active else {}


def _stability_rows(container: Any, key: str) -> list[dict[str, Any]]:
    if isinstance(container, dict) and isinstance(container.get(key), list):
        return [row for row in container[key] if isinstance(row, dict)]
    return []


def _worst_best(rows: list[dict[str, Any]], label_key: str) -> dict[str, Any]:
    usable = [row for row in rows if _num(row.get("profitAbs")) is not None]
    if not usable:
        return {"available": False, "worst": None, "best": None}
    ordered = sorted(usable, key=lambda row: _num(row.get("profitAbs")) or 0)
    return {
        "available": True,
        "worst": ordered[0],
        "best": ordered[-1],
        "negativeCount": sum(1 for row in usable if (_num(row.get("profitAbs")) or 0) < 0),
        "positiveCount": sum(1 for row in usable if (_num(row.get("profitAbs")) or 0) > 0),
        "totalCount": len(usable),
        "labelKey": label_key,
    }


def _concentration_summary(row: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    warnings: list[str] = []
    pair_rows = _stability_rows(row.get("pairStability"), "pairs")
    month_rows = _stability_rows(row.get("monthlyStability"), "months")
    pair_summary = _worst_best(pair_rows, "pair")
    month_summary = _worst_best(month_rows, "month")
    if not pair_summary["available"]:
        warnings.append(f"{_benchmark_label(row)} pair stability unavailable.")
    if not month_summary["available"]:
        warnings.append(f"{_benchmark_label(row)} monthly stability unavailable.")
    return pair_summary, month_summary, warnings


def _cost_sensitivity(row: dict[str, Any]) -> dict[str, Any]:
    raw_return = _num(row.get("totalReturnPct"))
    adjusted_return = _num(row.get("slippageAdjustedTotalReturnPct"))
    slippage_gap = None if raw_return is None or adjusted_return is None else round(raw_return - adjusted_return, 4)
    trade_count = _num(row.get("tradeCount")) or 0
    slippage_cost = _num(row.get("slippageCost"))
    fees_paid = _num(row.get("feesPaid"))
    if slippage_gap is None:
        level = "unavailable"
    elif slippage_gap >= 100 or trade_count >= 2000:
        level = "very_high"
    elif slippage_gap >= 60 or trade_count >= 1000:
        level = "high"
    elif slippage_gap >= 25:
        level = "medium"
    else:
        level = "low"
    return {
        "level": level,
        "tradeCount": int(trade_count),
        "feesPaid": _round(fees_paid),
        "slippageCost": _round(slippage_cost),
        "rawReturnPct": _round(raw_return),
        "slippageAdjustedReturnPct": _round(adjusted_return),
        "slippagePenaltyPct": slippage_gap,
    }


def _benchmark_status(row: dict[str, Any]) -> str:
    label = _benchmark_label(row)
    total_return = _num(row.get("totalReturnPct"))
    adjusted_return = _num(row.get("slippageAdjustedTotalReturnPct"))
    profit_factor = _num(row.get("profitFactor"))
    if label == "BenchmarkBollingerRebound":
        return "research_reference"
    if total_return is not None and adjusted_return is not None and total_return < 0 and adjusted_return < 0:
        return "failed_benchmark"
    if profit_factor is not None and profit_factor < 1:
        return "failed_benchmark"
    return "research_reference"


def _main_weakness(row: dict[str, Any]) -> str:
    label = _benchmark_label(row)
    pf = _num(row.get("profitFactor"))
    adjusted = _num(row.get("slippageAdjustedTotalReturnPct"))
    drawdown = _num(row.get("maxDrawdownPct"))
    trades = _num(row.get("tradeCount")) or 0
    if label == "BenchmarkBollingerRebound":
        return "Relative best, but still negative with high drawdown and profit factor below 1."
    if trades >= 2000:
        return "Excessive trade frequency and repeated losses overwhelm any simple rule edge."
    if adjusted is not None and adjusted < -200:
        return "Very high cost sensitivity after slippage stress."
    if drawdown is not None and drawdown > 80:
        return "Drawdown is too high for research promotion."
    if pf is not None and pf < 1:
        return "Profit factor below 1."
    return "Insufficient evidence of robust edge."


def _future_use(row: dict[str, Any]) -> str:
    label = _benchmark_label(row)
    if label == "BenchmarkBollingerRebound":
        return "Useful as a mean-reversion hypothesis seed and future baseline, not as a strategy."
    if label == "BenchmarkRSIMeanReversion":
        return "Useful only for studying why simple oversold rebounds failed."
    if label == "BenchmarkEMATrend":
        return "Useful as a negative reference for simple EMA trend logic."
    if label == "BenchmarkMACDVolume":
        return "Useful as a negative reference for simple momentum plus volume logic."
    if label == "BenchmarkTD9Exhaustion":
        return "Useful as a negative reference for standalone exhaustion counts."
    return "Research reference only."


def _review_benchmark(row: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    pair_summary, month_summary, warnings = _concentration_summary(row)
    exit_available = bool(row.get("exitAttribution"))
    if not exit_available:
        warnings.append(f"{_benchmark_label(row)} exit attribution unavailable in V13.4.23 report.")
    cost = _cost_sensitivity(row)
    status = _benchmark_status(row)
    return {
        "benchmarkId": row.get("benchmarkId"),
        "className": row.get("className"),
        "name": row.get("name"),
        "status": status,
        "mainWeakness": _main_weakness(row),
        "costSensitivity": cost,
        "profitFactor": _round(row.get("profitFactor")),
        "pairConcentration": pair_summary,
        "monthlyConcentration": month_summary,
        "exitAttributionAvailable": exit_available,
        "exitAttribution": row.get("exitAttribution") if exit_available else "unavailable",
        "whetherUsefulForFutureHypothesis": _future_use(row),
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "canBeUsedAsBaseline": True,
        "canBeUsedAsStrategy": False,
        "relativeToNoTradePct": _round((_num(row.get("totalReturnPct")) or 0) - 0),
        "relativeToBuyHoldBtcPct": None,
    }, warnings


def _build_no_trade_comparison(report: dict[str, Any]) -> dict[str, Any]:
    no_trade = report.get("noTradeBaseline") or _find_by_id(report, "benchmark_no_trade")
    rows = []
    for row in _active_benchmarks(report):
        rows.append({
            "benchmarkId": row.get("benchmarkId"),
            "className": row.get("className"),
            "returnVsNoTradePct": _round((_num(row.get("totalReturnPct")) or 0) - (_num(no_trade.get("totalReturnPct")) or 0)),
            "slippageAdjustedVsNoTradePct": _round((_num(row.get("slippageAdjustedTotalReturnPct")) or 0) - (_num(no_trade.get("slippageAdjustedTotalReturnPct")) or 0)),
            "outperformedNoTrade": (_num(row.get("slippageAdjustedTotalReturnPct")) or -999999) > (_num(no_trade.get("slippageAdjustedTotalReturnPct")) or 0),
        })
    return {
        "baselineReturnPct": _round(no_trade.get("totalReturnPct")),
        "baselineSlippageAdjustedReturnPct": _round(no_trade.get("slippageAdjustedTotalReturnPct")),
        "activeBenchmarksOutperformed": sum(1 for row in rows if row["outperformedNoTrade"]),
        "activeBenchmarkCount": len(rows),
        "rows": rows,
        "summary": "All active benchmarks underperformed NoTrade on the selected sample, before and after slippage stress.",
    }


def _build_buy_hold_comparison(report: dict[str, Any]) -> dict[str, Any]:
    buy_hold = report.get("buyHoldBtcBaseline") or _find_by_id(report, "benchmark_buy_hold_btc")
    baseline_return = _num(buy_hold.get("totalReturnPct"))
    baseline_adj = _num(buy_hold.get("slippageAdjustedTotalReturnPct"))
    rows = []
    for row in _active_benchmarks(report):
        outperformed = baseline_adj is not None and (_num(row.get("slippageAdjustedTotalReturnPct")) or -999999) > baseline_adj
        rows.append({
            "benchmarkId": row.get("benchmarkId"),
            "className": row.get("className"),
            "returnVsBuyHoldBtcPct": _round((_num(row.get("totalReturnPct")) or 0) - (baseline_return or 0)),
            "slippageAdjustedVsBuyHoldBtcPct": _round((_num(row.get("slippageAdjustedTotalReturnPct")) or 0) - (baseline_adj or 0)),
            "outperformedBuyHoldBtc": outperformed,
        })
    return {
        "buyHoldReturnPct": _round(baseline_return),
        "buyHoldSlippageAdjustedReturnPct": _round(baseline_adj),
        "buyHoldMaxDrawdownPct": _round(buy_hold.get("maxDrawdownPct")),
        "activeBenchmarksOutperformed": sum(1 for row in rows if row["outperformedBuyHoldBtc"]),
        "activeBenchmarkCount": len(rows),
        "rows": rows,
        "summary": "All active benchmarks underperformed BuyHoldBTC; simple passive BTC exposure lost less than frequent benchmark trading in this sample.",
    }


def _best_review(best: dict[str, Any], no_trade: dict[str, Any], buy_hold: dict[str, Any]) -> dict[str, Any]:
    pair_summary, month_summary, warnings = _concentration_summary(best)
    return {
        "benchmarkId": best.get("benchmarkId"),
        "className": _benchmark_label(best),
        "rawReturnPct": _round(best.get("totalReturnPct")),
        "slippageAdjustedReturnPct": _round(best.get("slippageAdjustedTotalReturnPct")),
        "maxDrawdownPct": _round(best.get("maxDrawdownPct")),
        "profitFactor": _round(best.get("profitFactor")),
        "tradeCount": best.get("tradeCount"),
        "relativeBestReason": "It lost less than the other active benchmark strategies and traded less frequently than the very high-turnover references.",
        "stillUnusableReasons": [
            "Return is still deeply negative.",
            "Slippage-adjusted return remains far below NoTrade and BuyHoldBTC.",
            "Profit factor is below 1.",
            "Max drawdown is high.",
            "No month in the available monthly stability table is positive.",
        ],
        "relativeBestNotTradable": True,
        "pairConcentration": pair_summary,
        "monthlyConcentration": month_summary,
        "warnings": warnings,
        "summary": "relative best != tradable",
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }


def _hypothesis_seeds() -> list[dict[str, Any]]:
    return [
        {
            "seedId": "bollinger_mean_reversion_research",
            "status": "hypothesis_seed",
            "source": "BenchmarkBollingerRebound was the least bad active benchmark.",
            "researchUse": "Study mean-reversion / deviation recovery with stricter filters, lower frequency, and stronger regime context.",
            "tradeReady": False,
        },
        {
            "seedId": "avoid_simple_ema_trend_baseline",
            "status": "hypothesis_seed",
            "source": "BenchmarkEMATrend had excessive turnover and severe drawdown.",
            "researchUse": "Simple EMA trend is a negative reference; future trend logic needs richer regime and volatility context.",
            "tradeReady": False,
        },
        {
            "seedId": "momentum_volume_needs_quality_filter",
            "status": "hypothesis_seed",
            "source": "BenchmarkMACDVolume was highly cost sensitive.",
            "researchUse": "Momentum plus volume alone is insufficient; study quality filters and fewer trades.",
            "tradeReady": False,
        },
        {
            "seedId": "td9_not_standalone",
            "status": "hypothesis_seed",
            "source": "BenchmarkTD9Exhaustion remained negative.",
            "researchUse": "TD-style exhaustion counts should not stand alone; only consider as one contextual feature.",
            "tradeReady": False,
        },
        {
            "seedId": "baseline_discipline_required",
            "status": "hypothesis_seed",
            "source": "NoTrade and BuyHoldBTC both beat active benchmarks.",
            "researchUse": "Every future strategy candidate must clear NoTrade, BuyHoldBTC, and BenchmarkBollingerRebound after costs.",
            "tradeReady": False,
        },
    ]


def _rejected_ideas(report: dict[str, Any]) -> list[dict[str, Any]]:
    ideas = []
    for item in report.get("rejectedBenchmarkIdeas", []) or []:
        ideas.append({
            "benchmarkId": item.get("benchmarkId") or item.get("className") or item.get("name"),
            "name": item.get("name"),
            "status": "rejected",
            "reason": item.get("reason") or "Rejected benchmark idea.",
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "canBeUsedAsStrategy": False,
        })
    if not ideas:
        ideas.append({
            "benchmarkId": "RejectedBenchmarkMartingale",
            "status": "rejected",
            "reason": "Unbounded risk / not compatible with AlphaPilot controlled live principles.",
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "canBeUsedAsStrategy": False,
        })
    return ideas


def _failure_findings(report: dict[str, Any], reviews: list[dict[str, Any]]) -> list[str]:
    active_count = len(reviews)
    no_trade_losers = sum(1 for row in reviews if (_num(row.get("costSensitivity", {}).get("slippageAdjustedReturnPct")) or -999999) < 0)
    high_cost = [row.get("className") for row in reviews if row.get("costSensitivity", {}).get("level") in {"high", "very_high"}]
    return [
        f"{no_trade_losers}/{active_count} active benchmarks failed to beat NoTrade after slippage stress.",
        "All active benchmarks failed to beat BuyHoldBTC on the selected Top10 / 1h / 20260101- sample.",
        "BenchmarkBollingerRebound is the relative best active benchmark, but it remains negative and has profit factor below 1.",
        f"High or very high cost sensitivity appears in: {', '.join(high_cost) if high_cost else 'unavailable'}.",
        "Pair and month stability do not show a robust positive pattern; losses are broad rather than isolated to one small pocket.",
        "Exit attribution is not available in the V13.4.23 benchmark report and should be added to future benchmark reporting.",
        "Current evidence does not support Dry-run, live trading, or direct benchmark parameter tuning.",
    ]


def build_report(benchmark_report_path: Path, summary_path: Path, manifest_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    warnings: list[str] = []
    benchmark_report = _read_json(benchmark_report_path)
    manifest = _read_json(manifest_path)
    if not summary_path.exists():
        warnings.append(f"{summary_path} unavailable.")
    no_trade = _build_no_trade_comparison(benchmark_report)
    buy_hold = _build_buy_hold_comparison(benchmark_report)
    reviews = []
    for row in _active_benchmarks(benchmark_report):
        review, row_warnings = _review_benchmark(row)
        matching = next((item for item in buy_hold["rows"] if item["benchmarkId"] == review["benchmarkId"]), None)
        if matching:
            review["relativeToBuyHoldBtcPct"] = matching["slippageAdjustedVsBuyHoldBtcPct"]
        reviews.append(review)
        warnings.extend(row_warnings)
    best = _best_active(benchmark_report)
    best_review = _best_review(best, no_trade, buy_hold) if best else {"available": False}
    warnings.extend(best_review.get("warnings", []))
    rejected = _rejected_ideas(benchmark_report)
    strategy_reset = {
        "resetRequired": True,
        "reason": "Simple benchmark families did not produce tradable evidence; continuing to tune benchmark parameters would overfit a weak base.",
        "nextVersion": "V13.4.25 - Strategy Research Factory: Factor Hypothesis Mining",
        "nextObjectives": [
            "Mine hypotheses from V13.4.22 factor evaluation, V13.4.23 benchmark results, and V13.4.24 failure attribution.",
            "Prioritize Bollinger / mean-reversion and low-frequency quality filters as research hypotheses.",
            "Compare any future candidate against NoTrade, BuyHoldBTC, and BenchmarkBollingerRebound after costs.",
            "Do not write a trading strategy until a hypothesis has stronger evidence.",
        ],
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }
    report = BenchmarkResultReviewReport(
        reportId="v13_4_24_benchmark_result_review",
        sourceBenchmarkReport=str(benchmark_report_path),
        sourceBenchmarkSummary=str(summary_path),
        sourceBenchmarkManifest=str(manifest_path),
        currentStatus="benchmark_review_completed",
        dryRunApproved=False,
        liveTradingApproved=False,
        noTradeComparison=no_trade,
        buyHoldBtcComparison=buy_hold,
        benchmarkReviews=reviews,
        bestBenchmarkReview=best_review,
        failureFindings=_failure_findings(benchmark_report, reviews),
        usefulHypothesisSeeds=_hypothesis_seeds(),
        rejectedIdeas=rejected,
        strategyResearchReset=strategy_reset,
        recommendedNextStep="V13.4.25 - Strategy Research Factory: Factor Hypothesis Mining",
        warnings=sorted(set(warnings)),
        generatedAt=_utc_now(),
        inputReports=[str(benchmark_report_path), str(summary_path), str(manifest_path)],
    ).to_dict()
    status_archive = {
        "reportId": "v13_4_24_benchmark_status_archive",
        "sourceBenchmarkReport": str(benchmark_report_path),
        "benchmarks": [
            {
                "benchmarkId": row.get("className") or row.get("benchmarkId"),
                "status": "research_reference" if row.get("benchmarkId") in {"benchmark_no_trade", "benchmark_buy_hold_btc"} else review.get("status"),
                "dryRunApproved": False,
                "liveTradingApproved": False,
                "reason": "Baseline comparison reference." if row.get("type") == "report_only_baseline" else review.get("mainWeakness"),
                "canBeUsedAsBaseline": True,
                "canBeUsedAsStrategy": False,
            }
            for row in benchmark_report.get("benchmarks", [])
            for review in ([next((item for item in reviews if item.get("benchmarkId") == row.get("benchmarkId")), {})])
        ] + rejected,
        "manifestStrategiesSucceeded": sum(1 for item in manifest.get("strategies", []) if item.get("succeeded")),
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "generatedAt": _utc_now(),
    }
    return report, status_archive


def write_summary(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# AlphaPilot V13.4.24 Benchmark Result Review Summary",
        "",
        "This review reads V13.4.23 benchmark reports only. It does not run a new backtest, approve Dry-run, or approve live trading.",
        "",
        "## Core Conclusion",
        "",
        "- Active benchmarks did not prove a tradable advantage.",
        "- BenchmarkBollingerRebound was the relative best active benchmark, but relative best does not mean usable.",
        "- NoTrade and BuyHoldBTC remain mandatory baselines for future strategy research.",
        "- The recommended next step is Strategy Research Factory / Factor Hypothesis Mining, not benchmark parameter tuning.",
        "",
        "## NoTrade Comparison",
        "",
        f"- baselineReturnPct: {report['noTradeComparison'].get('baselineReturnPct')}",
        f"- activeBenchmarksOutperformed: {report['noTradeComparison'].get('activeBenchmarksOutperformed')}/{report['noTradeComparison'].get('activeBenchmarkCount')}",
        f"- summary: {report['noTradeComparison'].get('summary')}",
        "",
        "## BuyHoldBTC Comparison",
        "",
        f"- buyHoldReturnPct: {report['buyHoldBtcComparison'].get('buyHoldReturnPct')}",
        f"- buyHoldMaxDrawdownPct: {report['buyHoldBtcComparison'].get('buyHoldMaxDrawdownPct')}",
        f"- activeBenchmarksOutperformed: {report['buyHoldBtcComparison'].get('activeBenchmarksOutperformed')}/{report['buyHoldBtcComparison'].get('activeBenchmarkCount')}",
        f"- summary: {report['buyHoldBtcComparison'].get('summary')}",
        "",
        "## Best Benchmark Review",
        "",
        f"- className: {report['bestBenchmarkReview'].get('className')}",
        f"- rawReturnPct: {report['bestBenchmarkReview'].get('rawReturnPct')}",
        f"- slippageAdjustedReturnPct: {report['bestBenchmarkReview'].get('slippageAdjustedReturnPct')}",
        f"- maxDrawdownPct: {report['bestBenchmarkReview'].get('maxDrawdownPct')}",
        f"- profitFactor: {report['bestBenchmarkReview'].get('profitFactor')}",
        f"- tradeCount: {report['bestBenchmarkReview'].get('tradeCount')}",
        f"- conclusion: {report['bestBenchmarkReview'].get('summary')}",
        "",
        "## Benchmark Family Review",
        "",
        "| Benchmark | Status | Raw Return % | Adj Return % | PF | Trades | Cost Sensitivity | Main Weakness |",
        "|---|---|---:|---:|---:|---:|---|---|",
    ]
    for row in report["benchmarkReviews"]:
        cost = row.get("costSensitivity", {})
        lines.append(
            f"| {row.get('className')} | {row.get('status')} | "
            f"{cost.get('rawReturnPct')} | {cost.get('slippageAdjustedReturnPct')} | "
            f"{_fmt(row.get('profitFactor')) if row.get('profitFactor') is not None else 'unavailable'} | "
            f"{cost.get('tradeCount')} | {cost.get('level')} | {row.get('mainWeakness')} |"
        )
    lines.extend(["", "## Failure Findings", ""])
    lines.extend(f"- {item}" for item in report["failureFindings"])
    lines.extend(["", "## Useful Hypothesis Seeds", ""])
    lines.extend(f"- {item['seedId']}: {item['researchUse']}" for item in report["usefulHypothesisSeeds"])
    lines.extend(["", "## Rejected Ideas", ""])
    lines.extend(f"- {item.get('benchmarkId')}: {item.get('reason')}" for item in report["rejectedIdeas"])
    lines.extend(["", "## Recommended Next Step", "", f"- {report['recommendedNextStep']}"])
    lines.extend(["", "## Safety Boundary", ""])
    lines.extend([
        "- dryRunApproved: false",
        "- liveTradingApproved: false",
        "- no new backtest run",
        "- no benchmark strategy code changes",
        "- no real API key",
        "- no Trade API / Withdraw API",
        "- no account or position reads",
        "- no real orders",
        "- no auto trading",
    ])
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in report["warnings"]) if report["warnings"] else lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.24 benchmark result review.")
    parser.add_argument("--benchmark-report", default=str(DEFAULT_BENCHMARK_REPORT))
    parser.add_argument("--benchmark-summary", default=str(DEFAULT_BENCHMARK_SUMMARY))
    parser.add_argument("--benchmark-manifest", default=str(DEFAULT_BENCHMARK_MANIFEST))
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--status-archive", default=str(DEFAULT_STATUS_ARCHIVE))
    args = parser.parse_args()

    report_path = Path(args.benchmark_report)
    summary_path = Path(args.benchmark_summary)
    manifest_path = Path(args.benchmark_manifest)
    for required in (report_path, summary_path, manifest_path):
        if not required.exists():
            raise FileNotFoundError(f"Required V13.4.23 input missing: {required}")

    report, status_archive = build_report(report_path, summary_path, manifest_path)
    output_json = Path(args.output_json)
    output_summary = Path(args.output_summary)
    status_path = Path(args.status_archive)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    status_path.write_text(json.dumps(status_archive, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_summary(report, output_summary)
    print(f"Exported benchmark result review: {output_json}")
    print(f"Exported benchmark result summary: {output_summary}")
    print(f"Exported benchmark status archive: {status_path}")


if __name__ == "__main__":
    main()
