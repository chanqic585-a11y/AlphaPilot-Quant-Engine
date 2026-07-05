"""Generate V13.4.30 Short Rejection failure review.

This module converts the V13.4.29 short-only research failure into a reusable
negative research asset. It only reads local report files. It does not run
backtests, enter Dry-run, call private exchange APIs, read accounts, create
orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.reports.short_rejection_failure_schema import (
    NegativeResearchRulesPayload,
    ShortFailureReviewReport,
    ShortStrategyStatusArchive,
)

SOURCE_SHORT_REPORT = Path("reports/v13_4_29_short_rejection_1h_report.json")
SOURCE_SHORT_SUMMARY = Path("reports/v13_4_29_short_rejection_1h_summary.md")
OUTPUT_REPORT = Path("reports/v13_4_30_short_rejection_failure_review.json")
OUTPUT_SUMMARY = Path("reports/v13_4_30_short_rejection_failure_summary.md")
OUTPUT_ARCHIVE = Path("reports/v13_4_30_short_strategy_status_archive.json")
OUTPUT_RULES = Path("reports/v13_4_30_negative_research_rules.json")

REPORT_ID = "v13_4_30_short_rejection_failure_review"
STRATEGY_ID = "alpha_short_rejection_1h_v01"
STRATEGY_NAME = "AlphaPilot Short Rejection 1H V0.1"
CURRENT_STATUS = "failed_research_current_sample"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _sort_by_number(rows: list[dict[str, Any]], key: str, reverse: bool = False) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: _num(row.get(key)), reverse=reverse)


def _top_rows(rows: list[dict[str, Any]], key: str, limit: int = 5, reverse: bool = False) -> list[dict[str, Any]]:
    return _sort_by_number(rows, key, reverse=reverse)[:limit]


def _compact_pair(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "pair": row.get("key"),
        "trades": row.get("trades"),
        "profitTotalPct": row.get("profit_total_pct"),
        "profitFactor": row.get("profit_factor"),
        "winRatePct": round(_num(row.get("winrate")) * 100, 4),
        "losses": row.get("losses"),
    }


def _compact_month(row: dict[str, Any]) -> dict[str, Any]:
    trades = int(_num(row.get("trades"), 0))
    losses = int(_num(row.get("losses"), 0))
    return {
        "month": row.get("date"),
        "trades": trades,
        "profitAbs": row.get("profit_abs"),
        "profitFactor": row.get("profit_factor"),
        "lossRatePct": round(losses / trades * 100, 4) if trades else None,
    }


def _compact_exit(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "exitReason": row.get("key"),
        "trades": row.get("trades"),
        "profitTotalPct": row.get("profit_total_pct"),
        "wins": row.get("wins"),
        "losses": row.get("losses"),
        "winRatePct": round(_num(row.get("winrate")) * 100, 4),
    }


def build_negative_rules() -> list[dict[str, Any]]:
    return [
        {
            "ruleId": "SHORT_NEG_001",
            "rule": "Do not mistake a small set of loose conditions for a constrained strategy.",
            "evidence": "V13.4.29 produced 5052 expanded short trades and near-total loss.",
        },
        {
            "ruleId": "SHORT_NEG_002",
            "rule": "Do not rely only on EMA rejection plus MACD/RSI weakening for short research.",
            "evidence": "The shortScore design still generated excessive low-quality entries.",
        },
        {
            "ruleId": "SHORT_NEG_003",
            "rule": "A loose shortScore can create overtrading even when each condition looks reasonable alone.",
            "evidence": "The 1h strategy averaged hundreds of trades per month across the expanded sample.",
        },
        {
            "ruleId": "SHORT_NEG_004",
            "rule": "Short research must explicitly monitor rebound and squeeze risk.",
            "evidence": "The report lacks per-trade regime attribution and stop_loss dominated losses.",
        },
        {
            "ruleId": "SHORT_NEG_005",
            "rule": "Short research must reduce trade frequency or use stronger trigger quality before expansion.",
            "evidence": "5052 trades amplified stop-loss frequency and slippage-adjusted losses.",
        },
        {
            "ruleId": "SHORT_NEG_006",
            "rule": "Regime context cannot be ignored, but it should be evaluated before becoming a hard switch.",
            "evidence": "Regime background is available, but V13.4.29 has no per-trade regime attribution.",
        },
        {
            "ruleId": "SHORT_NEG_007",
            "rule": "Do not try to rescue a deeply negative expanded backtest with small parameter tweaks.",
            "evidence": "Expanded totalReturnPct was -99.9966 with maxDrawdownPct 99.9966.",
        },
        {
            "ruleId": "SHORT_NEG_008",
            "rule": "Failed research strategies should be archived as benchmark/reference assets, not deleted.",
            "evidence": "The failure explains what not to repeat in later short research.",
        },
        {
            "ruleId": "SHORT_NEG_009",
            "rule": "Any future short strategy must include per-trade regime attribution before next-stage review.",
            "evidence": "Current report only has background regime distribution, not trade-level attribution.",
        },
        {
            "ruleId": "SHORT_NEG_010",
            "rule": "Any future short strategy must report separated direction metrics, costs, and stop-loss sources.",
            "evidence": "V13.4.29 demonstrates that stop_loss and slippage can dominate headline results.",
        },
    ]


def build_future_recommendations() -> list[str]:
    return [
        "Do not continue tuning AlphaPilotShortRejection1HV01 as the active short mainline.",
        "Wait for public funding and open-interest data before another short-focused research track.",
        "Require much lower trade frequency before any expanded short backtest.",
        "Use stronger triggers such as failed breakout, lower-high confirmation, or relative weakness.",
        "Add per-trade regime attribution before evaluating short strategy continuation.",
        "Start any future short candidate on BTC/ETH/SOL or Top10 only before supported-pair expansion.",
    ]


def build_archive(generated_at: str) -> ShortStrategyStatusArchive:
    return ShortStrategyStatusArchive(
        strategyId=STRATEGY_ID,
        strategyName=STRATEGY_NAME,
        status=CURRENT_STATUS,
        dryRunApproved=False,
        liveTradingApproved=False,
        researchWorthContinuing=False,
        reason="Expanded short-only backtest suffered near-total loss with excessive trade count.",
        evidenceReports=[str(SOURCE_SHORT_REPORT)],
        archiveMode="research_reference",
        canBeUsedAsBenchmark=True,
        canBeRevivedIf=[
            "new short thesis with stronger regime filter",
            "funding/OI data support",
            "much lower trade frequency",
            "per-trade regime attribution improves",
        ],
        generatedAt=generated_at,
    )


def build_review(source: dict[str, Any], generated_at: str) -> ShortFailureReviewReport:
    warnings: list[str] = []
    trade_count = int(_num(source.get("tradeCount"), 0))
    pair_count = len(source.get("pairs") or [])
    monthly = source.get("monthlyPerformance") or []
    pairs = source.get("pairPerformance") or []
    exits = source.get("exitReasonBreakdown") or []
    research_gate = source.get("researchGate") or {}
    regime = source.get("regimeBackground") or {}

    if not pairs:
        warnings.append("pairMonthlyBreakdownAvailable=false: pairPerformance is missing.")
    if not monthly:
        warnings.append("pairMonthlyBreakdownAvailable=false: monthlyPerformance is missing.")
    if not exits:
        warnings.append("exitReasonBreakdownAvailable=false.")

    stop_loss = next((row for row in exits if row.get("key") == "stop_loss"), {})
    roi = next((row for row in exits if row.get("key") == "roi"), {})
    time_stop = next((row for row in exits if row.get("key") == "short_time_stop_8h_not_profitable"), {})
    momentum_exit = next((row for row in exits if row.get("key") == "profitable_short_momentum_exit"), {})

    actual_win_rate = _num(source.get("winRate"))
    required_win_rate = round(2.5 / (5.0 + 2.5) * 100, 4)
    slippage_delta = round(
        _num(source.get("slippageAdjustedTotalReturnPct")) - _num(source.get("totalReturnPct")),
        4,
    )

    overall_failure = {
        "structuralFailure": True,
        "failedResearchStatus": CURRENT_STATUS,
        "rejectedForDryRun": True,
        "stopAsShortMainline": True,
        "tradeCount": trade_count,
        "totalReturnPct": source.get("totalReturnPct"),
        "maxDrawdownPct": source.get("maxDrawdownPct"),
        "profitFactor": source.get("profitFactor"),
        "winRatePct": source.get("winRate"),
        "conclusion": "The expanded short-only sample is a structural failure, not a tuning candidate.",
    }
    frequency_review = {
        "tradeCount": trade_count,
        "pairCount": pair_count,
        "monthCount": len(monthly),
        "averageTradesPerPair": round(trade_count / pair_count, 4) if pair_count else None,
        "averageTradesPerMonth": round(trade_count / len(monthly), 4) if monthly else None,
        "topPairTradeShare": research_gate.get("topPairTradeShare"),
        "overTradingLikely": True,
        "shortScoreObservation": "shortScore >= 4 was still too loose for expanded 1h short research.",
        "conclusion": "The strategy generated too many entries for a fragile short thesis.",
    }
    payoff_review = {
        "configuredRoiPct": 5.0,
        "configuredStoplossPct": 2.5,
        "roughBreakevenWinRatePctBeforeCosts": required_win_rate,
        "actualWinRatePct": actual_win_rate,
        "profitFactor": source.get("profitFactor"),
        "winRateInsufficient": actual_win_rate < required_win_rate,
        "stopLossTrades": stop_loss.get("trades"),
        "roiTrades": roi.get("trades"),
        "conclusion": "The theoretical payoff was undermined by low win rate, frequent stop losses, and costs.",
    }
    squeeze_review = {
        "regimeBackgroundAvailable": bool(regime),
        "perTradeRegimeAttributionAvailable": False,
        "dominantRegimes": regime.get("dominantRegimes", []),
        "regimeDistribution": regime.get("regimeDistribution", {}),
        "notes": [
            "The report has market-regime background but no trade-level regime tags.",
            "Future short reports must show whether losses cluster in bull/recovery/rebound states.",
        ],
        "conclusion": "Wrong-timing and squeeze risk cannot be ruled out and must be instrumented before revival.",
    }
    pair_month_review = {
        "pairMonthlyBreakdownAvailable": bool(pairs and monthly),
        "worstPairsByReturnPct": [_compact_pair(row) for row in _top_rows(pairs, "profit_total_pct", 5)],
        "bestPairsByReturnPct": [_compact_pair(row) for row in _top_rows(pairs, "profit_total_pct", 5, reverse=True)],
        "worstMonthsByProfitAbs": [_compact_month(row) for row in _top_rows(monthly, "profit_abs", 5)],
        "highestTradeMonths": [_compact_month(row) for row in _top_rows(monthly, "trades", 5, reverse=True)],
        "conclusion": "Losses were broad enough that no single pair rescue is a sufficient fix.",
    }
    exit_review = {
        "exitReasonBreakdownAvailable": bool(exits),
        "stopLoss": _compact_exit(stop_loss) if stop_loss else None,
        "roi": _compact_exit(roi) if roi else None,
        "timeStop": _compact_exit(time_stop) if time_stop else None,
        "momentumExit": _compact_exit(momentum_exit) if momentum_exit else None,
        "stopLossSharePct": round(_num(stop_loss.get("trades")) / trade_count * 100, 4) if trade_count and stop_loss else None,
        "conclusion": "stop_loss was the primary loss source; time stop was too small to offset the core failure.",
    }
    cost_review = {
        "slippageReviewAvailable": source.get("slippageAdjustedTotalReturnPct") is not None,
        "slippageAppliedByFreqtrade": source.get("slippageAppliedByFreqtrade"),
        "slippageAppliedByPostProcessing": source.get("slippageAppliedByPostProcessing"),
        "totalReturnPct": source.get("totalReturnPct"),
        "slippageAdjustedTotalReturnPct": source.get("slippageAdjustedTotalReturnPct"),
        "slippageImpactPct": slippage_delta,
        "profitFactor": source.get("profitFactor"),
        "slippageAdjustedProfitFactor": source.get("slippageAdjustedProfitFactor"),
        "tradeCount": trade_count,
        "conclusion": "Costs worsened an already failing strategy; future short research must reduce frequency.",
    }

    if source.get("dryRunApproved") is not False:
        warnings.append("Source report dryRunApproved was not explicitly false.")
    if source.get("liveTradingApproved") is not False:
        warnings.append("Source report liveTradingApproved was not explicitly false.")
    if research_gate.get("researchWorthContinuing") is not False:
        warnings.append("Source report research gate did not explicitly reject continuation.")

    return ShortFailureReviewReport(
        reportId=REPORT_ID,
        sourceShortReport=str(SOURCE_SHORT_REPORT),
        strategyId=source.get("strategyId") or STRATEGY_ID,
        strategyName=source.get("strategyName") or STRATEGY_NAME,
        currentStatus=CURRENT_STATUS,
        dryRunApproved=False,
        liveTradingApproved=False,
        researchWorthContinuing=False,
        overallFailure=overall_failure,
        tradeFrequencyReview=frequency_review,
        payoffReview=payoff_review,
        shortSqueezeRiskReview=squeeze_review,
        pairMonthReview=pair_month_review,
        exitReasonReview=exit_review,
        costReview=cost_review,
        negativeResearchRules=build_negative_rules(),
        futureShortResearchRecommendations=build_future_recommendations(),
        nextStepRecommendation="V13.4.31 - Low-Frequency Mainstream Coin Research Plan",
        warnings=warnings + list(source.get("warnings") or []),
        generatedAt=generated_at,
    )


def build_rules_payload(generated_at: str, warnings: list[str]) -> NegativeResearchRulesPayload:
    return NegativeResearchRulesPayload(
        reportId="v13_4_30_negative_research_rules",
        sourceShortReport=str(SOURCE_SHORT_REPORT),
        strategyId=STRATEGY_ID,
        rules=build_negative_rules(),
        futureRequirements=[
            "per-trade regime attribution",
            "long/short separated metrics",
            "exit reason loss attribution",
            "slippage-adjusted metrics",
            "trade-frequency review before expansion",
            "public funding/OI support before renewed short research",
        ],
        generatedAt=generated_at,
        warnings=warnings,
    )


def render_summary(report: ShortFailureReviewReport) -> str:
    payload = report.to_dict()
    freq = payload["tradeFrequencyReview"]
    payoff = payload["payoffReview"]
    squeeze = payload["shortSqueezeRiskReview"]
    pair_month = payload["pairMonthReview"]
    exit_review = payload["exitReasonReview"]
    cost = payload["costReview"]
    rules = payload["negativeResearchRules"]
    recommendations = payload["futureShortResearchRecommendations"]
    lines = [
        "# AlphaPilot V13.4.30 Short Rejection Failure Review",
        "",
        "V13.4.30 reviews the V13.4.29 short-only 1h research failure and archives it as a negative research asset. It does not modify strategy code, run a new backtest, enter Dry-run, or approve live trading.",
        "",
        "## Status",
        "",
        f"- currentStatus: {payload['currentStatus']}",
        f"- researchWorthContinuing: {payload['researchWorthContinuing']}",
        f"- dryRunApproved: {payload['dryRunApproved']}",
        f"- liveTradingApproved: {payload['liveTradingApproved']}",
        f"- sourceShortReport: {payload['sourceShortReport']}",
        "",
        "## Overall Failure",
        "",
        f"- tradeCount: {payload['overallFailure']['tradeCount']}",
        f"- totalReturnPct: {payload['overallFailure']['totalReturnPct']}",
        f"- maxDrawdownPct: {payload['overallFailure']['maxDrawdownPct']}",
        f"- profitFactor: {payload['overallFailure']['profitFactor']}",
        f"- winRatePct: {payload['overallFailure']['winRatePct']}",
        f"- conclusion: {payload['overallFailure']['conclusion']}",
        "",
        "## Trade Frequency Review",
        "",
        f"- averageTradesPerPair: {freq['averageTradesPerPair']}",
        f"- averageTradesPerMonth: {freq['averageTradesPerMonth']}",
        f"- topPairTradeShare: {freq['topPairTradeShare']}",
        f"- conclusion: {freq['conclusion']}",
        "",
        "## Payoff Review",
        "",
        f"- roughBreakevenWinRatePctBeforeCosts: {payoff['roughBreakevenWinRatePctBeforeCosts']}",
        f"- actualWinRatePct: {payoff['actualWinRatePct']}",
        f"- stopLossTrades: {payoff['stopLossTrades']}",
        f"- roiTrades: {payoff['roiTrades']}",
        f"- conclusion: {payoff['conclusion']}",
        "",
        "## Short Squeeze / Wrong Timing Review",
        "",
        f"- regimeBackgroundAvailable: {squeeze['regimeBackgroundAvailable']}",
        f"- perTradeRegimeAttributionAvailable: {squeeze['perTradeRegimeAttributionAvailable']}",
        f"- dominantRegimes: {', '.join(squeeze['dominantRegimes'])}",
        f"- conclusion: {squeeze['conclusion']}",
        "",
        "## Pair / Month Review",
        "",
        f"- pairMonthlyBreakdownAvailable: {pair_month['pairMonthlyBreakdownAvailable']}",
        "- worstPairsByReturnPct:",
    ]
    for row in pair_month["worstPairsByReturnPct"]:
        lines.append(f"  - {row['pair']}: trades={row['trades']} profitTotalPct={row['profitTotalPct']} profitFactor={row['profitFactor']}")
    lines.extend([
        "- worstMonthsByProfitAbs:",
    ])
    for row in pair_month["worstMonthsByProfitAbs"]:
        lines.append(f"  - {row['month']}: trades={row['trades']} profitAbs={row['profitAbs']} profitFactor={row['profitFactor']}")
    lines.extend([
        f"- conclusion: {pair_month['conclusion']}",
        "",
        "## Exit Reason Review",
        "",
        f"- exitReasonBreakdownAvailable: {exit_review['exitReasonBreakdownAvailable']}",
        f"- stopLossSharePct: {exit_review['stopLossSharePct']}",
        f"- stopLoss: {exit_review['stopLoss']}",
        f"- roi: {exit_review['roi']}",
        f"- conclusion: {exit_review['conclusion']}",
        "",
        "## Cost / Slippage Review",
        "",
        f"- slippageReviewAvailable: {cost['slippageReviewAvailable']}",
        f"- totalReturnPct: {cost['totalReturnPct']}",
        f"- slippageAdjustedTotalReturnPct: {cost['slippageAdjustedTotalReturnPct']}",
        f"- slippageImpactPct: {cost['slippageImpactPct']}",
        f"- profitFactor: {cost['profitFactor']}",
        f"- slippageAdjustedProfitFactor: {cost['slippageAdjustedProfitFactor']}",
        f"- conclusion: {cost['conclusion']}",
        "",
        "## Negative Research Rules",
        "",
    ])
    for rule in rules:
        lines.append(f"- {rule['ruleId']}: {rule['rule']}")
    lines.extend([
        "",
        "## Future Short Research Recommendations",
        "",
    ])
    for item in recommendations:
        lines.append(f"- {item}")
    lines.extend([
        "",
        "## Safety Boundary",
        "",
        "- no strategy modification",
        "- no new backtest",
        "- no Dry-run",
        "- no real API key",
        "- no Trade API / Withdraw API",
        "- no account or position reads",
        "- no real orders",
        "- no auto trading",
        "",
    ])
    if payload["warnings"]:
        lines.append("Warnings:")
        lines.append("")
        for warning in payload["warnings"]:
            lines.append(f"- {warning}")
        lines.append("")
    return "\n".join(lines)


def generate() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    if not SOURCE_SHORT_REPORT.exists():
        raise FileNotFoundError(f"Missing required source report: {SOURCE_SHORT_REPORT}")
    if not SOURCE_SHORT_SUMMARY.exists():
        raise FileNotFoundError(f"Missing required source summary: {SOURCE_SHORT_SUMMARY}")
    generated_at = utc_now()
    source = _read_json(SOURCE_SHORT_REPORT)
    report = build_review(source, generated_at)
    archive = build_archive(generated_at)
    rules = build_rules_payload(generated_at, report.warnings)

    report_payload = report.to_dict()
    archive_payload = archive.to_dict()
    rules_payload = rules.to_dict()
    _write_json(OUTPUT_REPORT, report_payload)
    _write_json(OUTPUT_ARCHIVE, archive_payload)
    _write_json(OUTPUT_RULES, rules_payload)
    _write_text(OUTPUT_SUMMARY, render_summary(report))
    return report_payload, archive_payload, rules_payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.30 short rejection failure review.")
    parser.parse_args()
    report, _, _ = generate()
    print(f"V13.4.30 status: {report['currentStatus']}")
    print(f"researchWorthContinuing: {report['researchWorthContinuing']}")
    print(f"dryRunApproved: {report['dryRunApproved']}")
    print(f"liveTradingApproved: {report['liveTradingApproved']}")
    print(f"Report: {OUTPUT_REPORT}")
    print(f"Summary: {OUTPUT_SUMMARY}")
    print(f"Archive: {OUTPUT_ARCHIVE}")
    print(f"Rules: {OUTPUT_RULES}")


if __name__ == "__main__":
    main()
