"""Generate V13.4.10 Trend Pullback redesign review artifacts.

This module reads local V13.4.8 and V13.4.9 report files only. It does not
modify strategy code, download data, run backtests, enter Dry-run, call exchange
APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.reports.trend_pullback_redesign_schema import TrendPullbackRedesignReviewReport

DEFAULT_SMOKE_REPORT = Path("reports/v13_4_8_trend_pullback_1h_smoke_report.json")
DEFAULT_EXPANDED_REPORT = Path("reports/v13_4_9_trend_pullback_expanded_validation_report.json")
DEFAULT_EXPANDED_SUMMARY = Path("reports/v13_4_9_trend_pullback_expanded_validation_summary.md")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_10_trend_pullback_redesign_review.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_10_trend_pullback_redesign_summary.md")

REPORT_ID = "v13_4_10_trend_pullback_redesign_review"
REPORT_VERSION = "V13.4.10"
STRATEGY_ID = "alpha_trend_pullback_1h_v01"
MAIN_COINS = {"BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"Missing input JSON report: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"Unable to parse JSON report {path}: {exc}")
        return {}


def _read_text(path: Path, warnings: list[str]) -> str:
    if not path.exists():
        warnings.append(f"Missing input text report: {path}")
        return "unavailable"
    return path.read_text(encoding="utf-8")


def _safe(value: Any) -> Any:
    return "unavailable" if value is None else value


def _number(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _round(value: Any, digits: int = 4) -> float | None:
    number = _number(value)
    if number is None:
        return None
    return round(number, digits)


def _source_reports(smoke_path: Path, expanded_path: Path, expanded_summary_path: Path, smoke: dict[str, Any], expanded: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "key": "v13_4_8_smoke",
            "path": str(smoke_path),
            "exists": smoke_path.exists(),
            "reportId": smoke.get("reportId", "v13_4_8_trend_pullback_1h_smoke_report"),
            "isMock": smoke.get("isMock", "unavailable"),
            "dryRunApproved": smoke.get("dryRunApproved", "unavailable"),
        },
        {
            "key": "v13_4_9_expanded",
            "path": str(expanded_path),
            "exists": expanded_path.exists(),
            "reportId": expanded.get("reportId", "unavailable"),
            "isMock": expanded.get("isMock", "unavailable"),
            "dryRunApproved": expanded.get("dryRunApproved", "unavailable"),
        },
        {
            "key": "v13_4_9_expanded_summary",
            "path": str(expanded_summary_path),
            "exists": expanded_summary_path.exists(),
            "reportId": "markdown_summary" if expanded_summary_path.exists() else "unavailable",
        },
    ]


def _smoke_pair_rows(smoke: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in smoke.get("pairPerformance", []) or []:
        pair = row.get("key") or row.get("pair")
        if not pair or pair == "TOTAL":
            continue
        rows.append(
            {
                "pair": pair,
                "tradeCount": row.get("trades"),
                "totalReturnPct": _round(row.get("profit_total_pct")),
                "totalProfitAbs": _round(row.get("profit_total_abs"), 8),
                "profitFactor": _round(row.get("profit_factor")),
                "winRate": _round((_number(row.get("winrate")) or 0) * 100) if row.get("winrate") is not None else "unavailable",
                "maxDrawdownPct": _round((_number(row.get("max_drawdown_account")) or 0) * 100) if row.get("max_drawdown_account") is not None else "unavailable",
            }
        )
    return rows


def _expanded_pair_rows(expanded: dict[str, Any], adjusted: bool = False) -> list[dict[str, Any]]:
    rows = []
    for item in expanded.get("pairPerformance", []) or []:
        pair = item.get("pair")
        payload = item.get("slippageAdjusted") if adjusted else item.get("raw")
        if not pair or not isinstance(payload, dict):
            continue
        if adjusted:
            rows.append(
                {
                    "pair": pair,
                    "tradeCount": payload.get("tradeCount"),
                    "totalReturnPct": _round(payload.get("slippageAdjustedReturnPct")),
                    "totalProfitAbs": _round(payload.get("slippageAdjustedProfitAbs"), 8),
                    "profitFactor": _round(payload.get("slippageAdjustedProfitFactor")),
                    "winRate": _round(payload.get("slippageAdjustedWinRate")),
                    "slippageCost": _round(payload.get("slippageCost"), 8),
                }
            )
        else:
            rows.append(
                {
                    "pair": pair,
                    "tradeCount": payload.get("tradeCount"),
                    "totalReturnPct": _round(payload.get("totalReturnPct")),
                    "totalProfitAbs": _round(payload.get("totalProfit"), 8),
                    "profitFactor": _round(payload.get("profitFactor")),
                    "winRate": _round(payload.get("winRate")),
                    "maxDrawdownPct": _round(payload.get("maxDrawdownPct")),
                }
            )
    return rows


def _sort_by_profit(rows: list[dict[str, Any]], reverse: bool = False) -> list[dict[str, Any]]:
    return sorted(rows, key=lambda row: _number(row.get("totalProfitAbs")) or 0.0, reverse=reverse)


def _sum_profit(rows: list[dict[str, Any]], pairs: set[str] | None = None, invert: bool = False) -> float | None:
    selected = []
    for row in rows:
        pair = str(row.get("pair"))
        in_set = pairs is None or pair in pairs
        if invert:
            in_set = not in_set
        if in_set and _number(row.get("totalProfitAbs")) is not None:
            selected.append(float(row["totalProfitAbs"]))
    if not selected:
        return None
    return round(sum(selected), 8)


def _month_label_from_raw(row: dict[str, Any]) -> str:
    raw = row.get("raw", {})
    date = str(raw.get("date") or "unknown")
    if date.count("/") == 2:
        day, month, year = date.split("/")
        return f"{year}-{month}"
    return date


def _monthly_breakdown(expanded: dict[str, Any]) -> dict[str, Any]:
    raw_rows: list[dict[str, Any]] = []
    adjusted_rows: list[dict[str, Any]] = []
    for item in expanded.get("monthlyPerformance", []) or []:
        if "raw" in item and isinstance(item["raw"], dict):
            raw = item["raw"]
            if raw.get("trades", 0) == 0 and _number(raw.get("profit_abs")) == 0:
                continue
            raw_rows.append(
                {
                    "month": _month_label_from_raw(item),
                    "profitAbs": _round(raw.get("profit_abs"), 8),
                    "tradeCount": raw.get("trades"),
                    "wins": raw.get("wins"),
                    "losses": raw.get("losses"),
                    "profitFactor": _round(raw.get("profit_factor")),
                }
            )
        if "slippageAdjusted" in item and isinstance(item["slippageAdjusted"], dict):
            adjusted = item["slippageAdjusted"]
            adjusted_rows.append(
                {
                    "month": adjusted.get("month"),
                    "profitAbs": _round(adjusted.get("slippageAdjustedProfitAbs"), 8),
                    "returnPct": _round(adjusted.get("slippageAdjustedReturnPct")),
                    "tradeCount": adjusted.get("tradeCount"),
                    "winRate": _round(adjusted.get("slippageAdjustedWinRate")),
                    "slippageCost": _round(adjusted.get("slippageCost"), 8),
                }
            )
    raw_losses = [row for row in raw_rows if (_number(row.get("profitAbs")) or 0) < 0]
    raw_wins = [row for row in raw_rows if (_number(row.get("profitAbs")) or 0) > 0]
    adjusted_losses = [row for row in adjusted_rows if (_number(row.get("profitAbs")) or 0) < 0]
    return {
        "monthlyBreakdownAvailable": bool(raw_rows or adjusted_rows),
        "rawRows": raw_rows,
        "slippageAdjustedRows": adjusted_rows,
        "worstRawMonths": sorted(raw_losses, key=lambda row: _number(row.get("profitAbs")) or 0)[:3],
        "bestRawMonths": sorted(raw_wins, key=lambda row: _number(row.get("profitAbs")) or 0, reverse=True)[:3],
        "worstSlippageAdjustedMonths": sorted(adjusted_losses, key=lambda row: _number(row.get("profitAbs")) or 0)[:3],
        "analysis": [
            "The expanded sample lost across multiple months rather than one isolated period.",
            "January, April, and May were the largest raw loss months.",
            "Slippage-adjusted losses worsened every active month.",
            "The pattern suggests broad regime fragility, not a single bad event.",
        ],
    }


def _build_smoke_vs_expanded(smoke: dict[str, Any], expanded: dict[str, Any]) -> dict[str, Any]:
    smoke_metrics = smoke.get("metrics", {})
    raw = expanded.get("rawMetrics", {})
    adjusted = expanded.get("slippageAdjustedMetrics", {})
    return {
        "smoke": {
            "scope": "BTC/ETH/SOL, 20260401-, 1h",
            "tradeCount": _safe(smoke_metrics.get("tradeCount")),
            "totalReturnPct": _safe(smoke_metrics.get("totalReturnPct")),
            "profitFactor": _safe(smoke_metrics.get("profitFactor")),
            "winRate": _safe(smoke_metrics.get("winRate")),
            "maxDrawdownPct": _safe(smoke_metrics.get("maxDrawdownPct")),
            "maxConsecutiveLosses": _safe(smoke_metrics.get("maxConsecutiveLosses")),
        },
        "expandedRaw": {
            "scope": "fixed Top30, supported 28 pairs, 20260101-, 1h",
            "tradeCount": _safe(raw.get("tradeCount")),
            "totalReturnPct": _safe(raw.get("totalReturnPct")),
            "profitFactor": _safe(raw.get("profitFactor")),
            "winRate": _safe(raw.get("winRate")),
            "maxDrawdownPct": _safe(raw.get("maxDrawdownPct")),
            "maxConsecutiveLosses": _safe(raw.get("maxConsecutiveLosses")),
        },
        "expandedSlippageAdjusted": {
            "tradeCount": _safe(adjusted.get("tradeCount")),
            "totalReturnPct": _safe(adjusted.get("slippageAdjustedTotalReturnPct")),
            "profitFactor": _safe(adjusted.get("slippageAdjustedProfitFactor")),
            "winRate": _safe(adjusted.get("slippageAdjustedWinRate")),
            "maxDrawdownPct": _safe(adjusted.get("maxDrawdownPct")),
            "maxConsecutiveLosses": _safe(adjusted.get("maxConsecutiveLosses")),
        },
        "divergence": {
            "returnDeltaRaw": _round((_number(raw.get("totalReturnPct")) or 0) - (_number(smoke_metrics.get("totalReturnPct")) or 0)),
            "profitFactorDeltaRaw": _round((_number(raw.get("profitFactor")) or 0) - (_number(smoke_metrics.get("profitFactor")) or 0)),
            "tradeCountMultiplier": _round((_number(raw.get("tradeCount")) or 0) / (_number(smoke_metrics.get("tradeCount")) or 1)),
            "interpretation": [
                "The smoke result verified implementation, but it was too narrow to prove strategy robustness.",
                "The expanded result added more pairs, more months, and more trades, exposing weak generalization.",
                "The loss is not explained by one pair alone; the wider universe and longer period revealed structural fragility.",
            ],
        },
    }


def _build_pair_concentration(smoke: dict[str, Any], expanded: dict[str, Any]) -> dict[str, Any]:
    smoke_rows = _smoke_pair_rows(smoke)
    raw_rows = _expanded_pair_rows(expanded, adjusted=False)
    adjusted_rows = _expanded_pair_rows(expanded, adjusted=True)
    btc_eth_sol_raw = [row for row in raw_rows if row.get("pair") in MAIN_COINS]
    btc_eth_sol_adjusted = [row for row in adjusted_rows if row.get("pair") in MAIN_COINS]
    alt_raw_total = _sum_profit(raw_rows, MAIN_COINS, invert=True)
    alt_adjusted_total = _sum_profit(adjusted_rows, MAIN_COINS, invert=True)
    gate = expanded.get("qualityGate", {})
    return {
        "pairConcentrationAvailable": bool(raw_rows),
        "supportedPairs": expanded.get("supportedPairs", []),
        "excludedPairs": expanded.get("excludedPairs", []),
        "smokePairs": smoke_rows,
        "topRawProfitPairs": _sort_by_profit(raw_rows, reverse=True)[:5],
        "topRawLossPairs": _sort_by_profit(raw_rows)[:5],
        "topSlippageAdjustedProfitPairs": _sort_by_profit(adjusted_rows, reverse=True)[:5],
        "topSlippageAdjustedLossPairs": _sort_by_profit(adjusted_rows)[:5],
        "btcEthSolExpandedRaw": btc_eth_sol_raw,
        "btcEthSolExpandedSlippageAdjusted": btc_eth_sol_adjusted,
        "btcEthSolRawTotalProfitAbs": _sum_profit(raw_rows, MAIN_COINS),
        "btcEthSolSlippageAdjustedTotalProfitAbs": _sum_profit(adjusted_rows, MAIN_COINS),
        "altRawTotalProfitAbs": alt_raw_total,
        "altSlippageAdjustedTotalProfitAbs": alt_adjusted_total,
        "largestPairAbsContributionPct": gate.get("largestPairAbsContributionPct", "unavailable"),
        "analysis": [
            "ETH and SOL remained positive in the expanded report, while BTC stayed negative.",
            "Top30 expansion introduced broad altcoin drag, especially after slippage post-processing.",
            "The largest pair contribution was not dominant, so the failure is portfolio-wide rather than one-pair-only.",
            "Pair universe narrowing is a plausible next validation path, but it carries overfitting risk.",
        ],
    }


def _build_cost_sensitivity(expanded: dict[str, Any]) -> dict[str, Any]:
    raw = expanded.get("rawMetrics", {})
    adjusted = expanded.get("slippageAdjustedMetrics", {})
    raw_return = _number(raw.get("totalReturnPct"))
    adjusted_return = _number(adjusted.get("slippageAdjustedTotalReturnPct"))
    raw_pf = _number(raw.get("profitFactor"))
    adjusted_pf = _number(adjusted.get("slippageAdjustedProfitFactor"))
    return {
        "tradeCount": _safe(raw.get("tradeCount")),
        "averageHoldingMinutes": _safe(raw.get("averageHoldingMinutes")),
        "rawTotalReturnPct": _safe(raw.get("totalReturnPct")),
        "slippageAdjustedTotalReturnPct": _safe(adjusted.get("slippageAdjustedTotalReturnPct")),
        "returnDegradationPctPoints": _round(adjusted_return - raw_return) if raw_return is not None and adjusted_return is not None else "unavailable",
        "rawProfitFactor": _safe(raw.get("profitFactor")),
        "slippageAdjustedProfitFactor": _safe(adjusted.get("slippageAdjustedProfitFactor")),
        "profitFactorDegradation": _round(adjusted_pf - raw_pf) if raw_pf is not None and adjusted_pf is not None else "unavailable",
        "slippageCost": _safe(adjusted.get("slippageCost")),
        "slippageRateOneWay": _safe(adjusted.get("slippageRateOneWay")),
        "slippageAppliedByFreqtrade": _safe(adjusted.get("slippageAppliedByFreqtrade")),
        "slippageAppliedByPostProcessing": _safe(adjusted.get("slippageAppliedByPostProcessing")),
        "analysis": [
            "A 472-trade six-month sample is still cost-sensitive for a 1h strategy.",
            "Slippage turned an already failed raw result into a much deeper rejection.",
            "Execution reality must be modeled before any future Dry-run discussion.",
            "Lower frequency, stronger liquidity filters, or higher expected payoff are required.",
        ],
    }


def _build_payoff_review(smoke: dict[str, Any], expanded: dict[str, Any]) -> dict[str, Any]:
    smoke_metrics = smoke.get("metrics", {})
    raw = expanded.get("rawMetrics", {})
    adjusted = expanded.get("slippageAdjustedMetrics", {})
    return {
        "payoffDetailsAvailable": False,
        "configuredStopLoss": "-2.5%",
        "configuredTakeProfit": "+5%",
        "averageWin": "unavailable",
        "averageLoss": "unavailable",
        "smokeWinRate": _safe(smoke_metrics.get("winRate")),
        "expandedRawWinRate": _safe(raw.get("winRate")),
        "expandedAdjustedWinRate": _safe(adjusted.get("slippageAdjustedWinRate")),
        "analysis": [
            "The apparent 2:1 configured payoff did not survive expanded validation.",
            "The expanded win rate fell to roughly 31.6% raw and 30.7% after slippage adjustment.",
            "Average win/loss details are unavailable in the V13.4.9 report, so this review does not invent them.",
            "The likely issue is entry quality and path behavior: too many trades reach stop-loss or weak exits before +5%.",
        ],
    }


def _build_filter_review() -> dict[str, Any]:
    return {
        "filtersReviewed": [
            "4h trend filter",
            "BTC safety",
            "1h pullback location",
            "reclaim confirmation",
            "volumeRatio >= 1.2",
            "no-chase",
            "ATR risk quality",
        ],
        "likelyTooLoose": [
            "volumeRatio >= 1.2 may still admit noisy rebounds in weaker altcoins.",
            "BTC safety alone does not represent full market regime strength.",
            "Pullback and reclaim checks are binary and do not score trend quality.",
            "No-chase and ATR filters reduce obvious bad entries but do not ensure positive expectancy.",
        ],
        "missingFilters": [
            "pair-level liquidity filter",
            "execution reality filter",
            "market regime filter beyond BTC only",
            "signal score / quality gate",
            "pair-specific trade cap or exposure cap",
        ],
        "analysis": [
            "The current filters are useful guards but not sufficient quality gates.",
            "Top30 altcoin behavior likely needs liquidity and pair quality control.",
            "A score-based gate is preferable to another round of simple threshold tweaks.",
        ],
    }


def _redesign_options(pair_concentration: dict[str, Any], cost_sensitivity: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "id": "option_a_pair_universe_narrowing",
            "name": "Pair Universe Narrowing",
            "direction": "Trade only high-liquidity majors or a high-quality subset instead of all Top30 pairs.",
            "candidateScope": ["BTC/ETH/SOL", "Top10 liquidity", "supportedPairs with stable expanded behavior"],
            "evidence": [
                "V13.4.8 BTC/ETH/SOL smoke was positive.",
                "V13.4.9 Top30 expansion failed deeply.",
                f"BTC/ETH/SOL expanded adjusted total profit abs: {pair_concentration.get('btcEthSolSlippageAdjustedTotalProfitAbs')}",
            ],
            "risks": ["smaller sample", "overfitting to BTC/ETH/SOL", "may miss broader market opportunities"],
        },
        {
            "id": "option_b_market_regime_filter",
            "name": "Market Regime Filter",
            "direction": "Enable Trend Pullback only during trend-friendly market regimes.",
            "candidateRules": [
                "BTC 4h trend positive",
                "ETH/SOL confirmation not weak",
                "future total-market or dominance proxy",
            ],
            "evidence": [
                "Expanded losses occurred across multiple months.",
                "Single BTC safety was not enough to protect Top30 exposure.",
            ],
            "risks": ["more data needed", "fewer signals", "more complex validation"],
        },
        {
            "id": "option_c_signal_score_quality_gate",
            "name": "Signal Score / Quality Gate",
            "direction": "Replace binary pass/fail entry with low-frequency high-quality signal scoring.",
            "candidateFactors": [
                "4h trend strength",
                "1h pullback quality",
                "volume quality",
                "risk distance",
                "no-chase distance",
                "pair liquidity",
                "BTC safety",
            ],
            "candidateRule": "score >= 80 before entry",
            "evidence": ["Current filters still generated 472 expanded trades with negative expectancy."],
            "risks": ["subjective weights", "possible overfitting", "may create too few trades"],
        },
        {
            "id": "option_d_liquidity_execution_reality_filter",
            "name": "Liquidity / Execution Reality Filter",
            "direction": "Add pre-trade liquidity and execution feasibility checks.",
            "candidateRules": [
                "minimum 24h volume",
                "minimum recent 1h volume",
                "maximum position notional / volume ratio",
                "future orderbook depth filter",
            ],
            "evidence": [
                f"Slippage-adjusted return degraded to {cost_sensitivity.get('slippageAdjustedTotalReturnPct')}%.",
                f"Slippage cost estimate: {cost_sensitivity.get('slippageCost')}.",
            ],
            "risks": ["requires more market data", "first version may only approximate execution quality"],
        },
        {
            "id": "option_e_alternate_strategy_direction",
            "name": "Alternate Strategy Direction",
            "direction": "Pause Trend Pullback and return to Breakout Retest or another V03/V04 direction.",
            "candidateDirections": ["Breakout Retest Confirmation", "High Score Signal Only", "new V04 strategy family"],
            "evidence": ["Trend Pullback failed expanded validation severely."],
            "risks": ["longer development cycle", "new strategy also requires full validation"],
        },
    ]


def _recommended_next_step(pair_concentration: dict[str, Any], cost_sensitivity: dict[str, Any]) -> str:
    adjusted_return = _number(cost_sensitivity.get("slippageAdjustedTotalReturnPct"))
    btc_eth_sol_adjusted = _number(pair_concentration.get("btcEthSolSlippageAdjustedTotalProfitAbs"))
    alt_adjusted = _number(pair_concentration.get("altSlippageAdjustedTotalProfitAbs"))
    if adjusted_return is not None and adjusted_return < -50:
        return "V13.4.11 - Execution Reality and Liquidity Gate Design"
    if btc_eth_sol_adjusted is not None and btc_eth_sol_adjusted > 0 and alt_adjusted is not None and alt_adjusted < 0:
        return "V13.4.11 - Pair Universe Narrowing Validation"
    return "V13.4.11 - Signal Score Gate Specification"


def build_report(smoke_path: Path, expanded_path: Path, expanded_summary_path: Path) -> TrendPullbackRedesignReviewReport:
    warnings: list[str] = []
    smoke = _read_json(smoke_path, warnings)
    expanded = _read_json(expanded_path, warnings)
    expanded_summary = _read_text(expanded_summary_path, warnings)

    if smoke.get("strategyId") != STRATEGY_ID:
        warnings.append("Smoke report strategyId does not match alpha_trend_pullback_1h_v01.")
    if expanded.get("strategyId") != STRATEGY_ID:
        warnings.append("Expanded report strategyId does not match alpha_trend_pullback_1h_v01.")
    if smoke.get("isMock") is not False:
        warnings.append("Smoke report isMock is not false.")
    if expanded.get("isMock") is not False:
        warnings.append("Expanded report isMock is not false.")
    if expanded_summary == "unavailable":
        warnings.append("Expanded summary unavailable; markdown cross-check skipped.")

    smoke_vs_expanded = _build_smoke_vs_expanded(smoke, expanded)
    pair_concentration = _build_pair_concentration(smoke, expanded)
    monthly = _monthly_breakdown(expanded)
    cost_sensitivity = _build_cost_sensitivity(expanded)
    payoff = _build_payoff_review(smoke, expanded)
    filter_review = _build_filter_review()
    redesign_options = _redesign_options(pair_concentration, cost_sensitivity)
    recommended = _recommended_next_step(pair_concentration, cost_sensitivity)
    failure_findings = [
        "V13.4.8 small BTC/ETH/SOL smoke profit did not generalize to Top30 six-month validation.",
        "V13.4.9 expanded raw result is deeply negative.",
        "Slippage-adjusted post-processing worsened the already failed result.",
        "The current strategy cannot enter Dry-run.",
        "Continuing to micro-tune the current rules has high overfitting risk.",
        "The next design must address pair selection, market regime, signal quality, and execution cost.",
    ]
    return TrendPullbackRedesignReviewReport(
        reportId=REPORT_ID,
        version=REPORT_VERSION,
        strategyId=STRATEGY_ID,
        sourceReports=_source_reports(smoke_path, expanded_path, expanded_summary_path, smoke, expanded),
        currentStatus="needs_redesign",
        dryRunApproved=False,
        smokeVsExpanded=smoke_vs_expanded,
        pairConcentration=pair_concentration,
        monthlyBreakdown=monthly,
        costSensitivity=cost_sensitivity,
        payoffReview=payoff,
        filterReview=filter_review,
        strategyFamilyDecision={
            "status": "needs_redesign",
            "notApprovedForDryRun": True,
            "archiveCurrentImplementationForReference": True,
            "doNotScaleCurrentTop30Strategy": True,
            "reason": "Expanded validation and slippage-adjusted checks failed too severely for parameter tuning.",
        },
        failureFindings=failure_findings,
        redesignOptions=redesign_options,
        recommendedNextStep=recommended,
        doNotProceed=[
            "Do not enter Dry-run.",
            "Do not connect live trading.",
            "Do not add or store API keys.",
            "Do not auto trade.",
            "Do not continue scaling the current Top30 Trend Pullback rule set.",
            "Do not treat the V13.4.8 small-sample positive result as strategy approval.",
        ],
        warnings=warnings,
        generatedAt=_utc_now(),
    )


def _format(value: Any) -> str:
    if value is None:
        return "unavailable"
    return str(value)


def _write_summary(report: dict[str, Any], path: Path) -> None:
    smoke = report["smokeVsExpanded"]["smoke"]
    raw = report["smokeVsExpanded"]["expandedRaw"]
    adjusted = report["smokeVsExpanded"]["expandedSlippageAdjusted"]
    pair = report["pairConcentration"]
    monthly = report["monthlyBreakdown"]
    cost = report["costSensitivity"]
    payoff = report["payoffReview"]
    filter_review = report["filterReview"]
    lines = [
        "# V13.4.10 Trend Pullback Redesign Review Summary",
        "",
        "## Decision",
        "",
        f"- currentStatus: {report['currentStatus']}",
        f"- dryRunApproved: {report['dryRunApproved']}",
        f"- recommendedNextStep: {report['recommendedNextStep']}",
        "- The current Trend Pullback 1H V0.1 implementation is kept as research reference only.",
        "",
        "## Smoke vs Expanded",
        "",
        "| Scope | Trades | Return % | PF | Win Rate % | Max DD % | Max Loss Streak |",
        "|---|---:|---:|---:|---:|---:|---:|",
        f"| V13.4.8 BTC/ETH/SOL smoke | {smoke['tradeCount']} | {smoke['totalReturnPct']} | {smoke['profitFactor']} | {smoke['winRate']} | {smoke['maxDrawdownPct']} | {smoke['maxConsecutiveLosses']} |",
        f"| V13.4.9 Top30 raw | {raw['tradeCount']} | {raw['totalReturnPct']} | {raw['profitFactor']} | {raw['winRate']} | {raw['maxDrawdownPct']} | {raw['maxConsecutiveLosses']} |",
        f"| V13.4.9 slippage-adjusted | {adjusted['tradeCount']} | {adjusted['totalReturnPct']} | {adjusted['profitFactor']} | {adjusted['winRate']} | {adjusted['maxDrawdownPct']} | {adjusted['maxConsecutiveLosses']} |",
        "",
        "The small positive smoke sample did not generalize to the wider Top30 six-month sample.",
        "",
        "## Pair Concentration",
        "",
        f"- pairConcentrationAvailable: {pair['pairConcentrationAvailable']}",
        f"- supportedPairs: {len(pair['supportedPairs'])}",
        f"- excludedPairs: {', '.join(item.get('pair', 'unknown') for item in pair['excludedPairs']) if pair['excludedPairs'] else 'none'}",
        f"- largestPairAbsContributionPct: {pair['largestPairAbsContributionPct']}",
        f"- BTC/ETH/SOL adjusted total profit abs: {pair['btcEthSolSlippageAdjustedTotalProfitAbs']}",
        f"- Other pairs adjusted total profit abs: {pair['altSlippageAdjustedTotalProfitAbs']}",
        "",
        "### Top Raw Profit Pairs",
        "",
    ]
    lines.extend(f"- {row['pair']}: {row['totalReturnPct']}%, trades={row['tradeCount']}, PF={row['profitFactor']}" for row in pair["topRawProfitPairs"])
    lines.extend(["", "### Top Raw Loss Pairs", ""])
    lines.extend(f"- {row['pair']}: {row['totalReturnPct']}%, trades={row['tradeCount']}, PF={row['profitFactor']}" for row in pair["topRawLossPairs"])
    lines.extend(["", "## Monthly / Regime Breakdown", ""])
    lines.append(f"- monthlyBreakdownAvailable: {monthly['monthlyBreakdownAvailable']}")
    lines.append("- Worst raw months:")
    lines.extend(f"  - {row['month']}: {row['profitAbs']} USDT, trades={row['tradeCount']}" for row in monthly["worstRawMonths"])
    lines.append("- Worst slippage-adjusted months:")
    lines.extend(f"  - {row['month']}: {row['profitAbs']} USDT, trades={row['tradeCount']}" for row in monthly["worstSlippageAdjustedMonths"])
    lines.extend(["", "## Cost Sensitivity", ""])
    lines.extend(
        [
            f"- tradeCount: {cost['tradeCount']}",
            f"- rawTotalReturnPct: {cost['rawTotalReturnPct']}",
            f"- slippageAdjustedTotalReturnPct: {cost['slippageAdjustedTotalReturnPct']}",
            f"- returnDegradationPctPoints: {cost['returnDegradationPctPoints']}",
            f"- rawProfitFactor: {cost['rawProfitFactor']}",
            f"- slippageAdjustedProfitFactor: {cost['slippageAdjustedProfitFactor']}",
            f"- profitFactorDegradation: {cost['profitFactorDegradation']}",
            f"- slippageCost: {cost['slippageCost']}",
        ]
    )
    lines.extend(["", "## Payoff Review", ""])
    lines.extend(
        [
            f"- payoffDetailsAvailable: {payoff['payoffDetailsAvailable']}",
            f"- configuredStopLoss: {payoff['configuredStopLoss']}",
            f"- configuredTakeProfit: {payoff['configuredTakeProfit']}",
            f"- expandedRawWinRate: {payoff['expandedRawWinRate']}",
            f"- expandedAdjustedWinRate: {payoff['expandedAdjustedWinRate']}",
        ]
    )
    lines.extend(f"- {item}" for item in payoff["analysis"])
    lines.extend(["", "## Filter Review", ""])
    lines.append("Likely weak or incomplete areas:")
    lines.extend(f"- {item}" for item in filter_review["likelyTooLoose"])
    lines.append("Missing filter categories:")
    lines.extend(f"- {item}" for item in filter_review["missingFilters"])
    lines.extend(["", "## Failure Findings", ""])
    lines.extend(f"- {item}" for item in report["failureFindings"])
    lines.extend(["", "## Redesign Options", ""])
    for option in report["redesignOptions"]:
        lines.extend(
            [
                f"### {option['name']}",
                "",
                f"- id: {option['id']}",
                f"- direction: {option['direction']}",
                "- evidence:",
            ]
        )
        lines.extend(f"  - {item}" for item in option.get("evidence", []))
        lines.append("- risks:")
        lines.extend(f"  - {item}" for item in option.get("risks", []))
        lines.append("")
    lines.extend(
        [
            "## Do Not Proceed",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["doNotProceed"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "V13.4.10 reads local reports and writes research artifacts only. It does not modify strategy code, run backtests, download data, enter Dry-run, use API keys, call Trade API or Withdraw API, read accounts, create orders, or auto trade.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_report(smoke_path: Path, expanded_path: Path, expanded_summary_path: Path, output_json: Path, output_summary: Path) -> tuple[Path, Path]:
    report = build_report(smoke_path, expanded_path, expanded_summary_path).to_dict()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(report, output_summary)
    return output_json, output_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.10 Trend Pullback redesign review.")
    parser.add_argument("--smoke-report", type=Path, default=DEFAULT_SMOKE_REPORT)
    parser.add_argument("--expanded-report", type=Path, default=DEFAULT_EXPANDED_REPORT)
    parser.add_argument("--expanded-summary", type=Path, default=DEFAULT_EXPANDED_SUMMARY)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    args = parser.parse_args()

    output_json, output_summary = export_report(
        args.smoke_report,
        args.expanded_report,
        args.expanded_summary,
        args.output_json,
        args.output_summary,
    )
    print(f"Exported Trend Pullback redesign review: {output_json}")
    print(f"Exported Trend Pullback redesign summary: {output_summary}")


if __name__ == "__main__":
    main()
