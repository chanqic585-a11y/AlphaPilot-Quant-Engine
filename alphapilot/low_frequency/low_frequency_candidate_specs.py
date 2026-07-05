"""V13.4.33 low-frequency strategy candidate specifications.

The specs are research-only. They do not implement Freqtrade strategies, run
backtests, create orders, or approve Dry-run/live trading.
"""

from __future__ import annotations

from typing import Any

from alphapilot.low_frequency.directional_score_spec import build_directional_score_framework
from alphapilot.low_frequency.low_frequency_candidate_schema import LowFrequencyCandidateSpec


DEFAULT_PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]


def _buy_hold_rows(baseline_report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(baseline_report.get("baselines", {}).get("buyHold") or [])


def _equal_weight_rows(baseline_report: dict[str, Any]) -> list[dict[str, Any]]:
    return list(baseline_report.get("baselines", {}).get("equalWeight") or [])


def _row_key(row: dict[str, Any]) -> str:
    pair = row.get("pair") or "portfolio"
    timeframe = row.get("timeframe") or "unknown"
    return f"{pair}:{timeframe}"


def build_baseline_hurdles(baseline_report: dict[str, Any]) -> dict[str, Any]:
    no_trade = baseline_report.get("baselines", {}).get("noTrade") or {}
    buy_hold = {_row_key(row): row for row in _buy_hold_rows(baseline_report)}
    equal_weight = {_row_key(row): row for row in _equal_weight_rows(baseline_report)}
    return {
        "universalHurdles": {
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "mustBeatNoTrade": True,
            "mustReportVsBuyHold": True,
            "mustReportVsEqualWeight": True,
            "mustReportRegimeBreakdown": True,
            "mustReportLongShortBreakdown": True,
            "mustReportSlippageAdjustedMetrics": True,
        },
        "noTradeHurdle": {
            "baselineId": no_trade.get("baselineId"),
            "requiredFutureFields": [
                "slippageAdjustedReturnPct",
                "maxDrawdownPct",
                "tradeCount",
                "exposureTimePct",
            ],
            "minimumExpectation": {
                "slippageAdjustedReturnPct": "> 0",
                "tradeCount": "not zero and not excessive",
                "maxDrawdownPct": "must be explicitly judged against baseline and strategy risk concept",
            },
            "reference": {
                "totalReturnPct": no_trade.get("totalReturnPct"),
                "maxDrawdownPct": no_trade.get("maxDrawdownPct"),
                "exposureTimePct": no_trade.get("exposureTimePct"),
            },
        },
        "pairSpecificBuyHoldHurdles": {
            key: {
                "baselineId": row.get("baselineId"),
                "pair": row.get("pair"),
                "timeframe": row.get("timeframe"),
                "totalReturnPct": row.get("totalReturnPct"),
                "maxDrawdownPct": row.get("maxDrawdownPct"),
                "volatilityPct": row.get("volatilityPct"),
                "requiredFutureComparison": [
                    "excessReturnVsPairBuyHold",
                    "drawdownReductionVsPairBuyHold",
                    "riskAdjustedComparison",
                ],
            }
            for key, row in buy_hold.items()
        },
        "equalWeightHurdles": {
            key: {
                "baselineId": row.get("baselineId"),
                "timeframe": row.get("timeframe"),
                "totalReturnPct": row.get("totalReturnPct"),
                "maxDrawdownPct": row.get("maxDrawdownPct"),
                "volatilityPct": row.get("volatilityPct"),
                "requiredFutureComparison": [
                    "excessReturnVsEqualWeight",
                    "drawdownReductionVsEqualWeight",
                    "monthlyStabilityVsEqualWeight",
                ],
            }
            for key, row in equal_weight.items()
        },
        "regimeHurdle": {
            "mustReport": [
                "bull performance",
                "bear performance",
                "sideways performance",
                "crash/high-volatility performance",
                "noTradeRatio by regime",
            ],
            "riskRequirement": "If direction is wrong in bear/crash contexts, future implementation must show low exposure or explicit defensive behavior.",
            "source": baseline_report.get("baselines", {}).get("regimeBreakdown", {}).get("source"),
        },
    }


def _candidate_hurdles(candidate_id: str, baseline_hurdles: dict[str, Any], pair_scope: list[str], timeframe: str) -> dict[str, Any]:
    return {
        "candidateId": candidate_id,
        "universalHurdles": baseline_hurdles["universalHurdles"],
        "noTradeHurdle": baseline_hurdles["noTradeHurdle"],
        "pairBuyHoldReferences": {
            pair: baseline_hurdles["pairSpecificBuyHoldHurdles"].get(f"{pair}:{timeframe}")
            for pair in pair_scope
        },
        "equalWeightReference": baseline_hurdles["equalWeightHurdles"].get(f"portfolio:{timeframe}"),
        "regimeHurdle": baseline_hurdles["regimeHurdle"],
    }


def build_candidate_specs(baseline_report: dict[str, Any]) -> list[LowFrequencyCandidateSpec]:
    pairs = list(baseline_report.get("pairs") or DEFAULT_PAIRS)
    baseline_hurdles = build_baseline_hurdles(baseline_report)
    return [
        LowFrequencyCandidateSpec(
            candidateId="LF-CAND-A-4H-EMA-TREND-LONG",
            name="4H EMA Trend Long",
            direction="long",
            timeframe="4h",
            pairs=pairs,
            coreConditions=[
                "4h close > EMA200",
                "4h EMA20 > EMA50",
                "close pullback near EMA20 or EMA50",
                "close reclaims EMA20",
                "volume not collapsing",
            ],
            exitConcept={
                "stoploss": "2.5% - 4%",
                "takeProfit": "1.5R - 2R or trailing",
                "timeStop": "5-10 4h candles",
            },
            riskConcept={
                "regimeUse": "bull / recovery / neutral-positive improves score but is not the only hard switch",
                "maxCoreConditions": 5,
                "firstImplementation": "candidate implementation must report slippage-adjusted metrics and baseline comparison",
            },
            baselineHurdles=_candidate_hurdles("LF-CAND-A-4H-EMA-TREND-LONG", baseline_hurdles, pairs, "4h"),
            expectedStrength=[
                "simple trend-following structure",
                "clear pair-specific BuyHold comparison",
                "compatible with low-frequency 4h data",
            ],
            knownRisk=[
                "late entries after extended moves",
                "whipsaw during sideways regime",
                "may underperform BuyHold during persistent bull trend",
            ],
            validationPlan=[
                "Implement only after V13.4.33 approval.",
                "Backtest BTC/ETH/SOL 4h from 20240101-.",
                "Report long-only results vs NoTrade, pair BuyHold, and EqualWeight.",
                "Report regime and slippage-adjusted breakdown.",
            ],
            invalidationRules=[
                "slippageAdjustedReturnPct <= 0",
                "drawdown not materially controlled vs BuyHold",
                "trade count too low to evaluate or too high for low-frequency intent",
                "bear/crash exposure remains high without defensive behavior",
            ],
        ),
        LowFrequencyCandidateSpec(
            candidateId="LF-CAND-B-4H-BEAR-REJECTION-SHORT",
            name="4H Bear Rejection Short",
            direction="short",
            timeframe="4h",
            pairs=pairs,
            coreConditions=[
                "4h price rejects EMA20 or EMA50 area",
                "close falls back below EMA20",
                "MACD histogram weakens",
                "RSI below 55 or falling",
                "no chase after large drop",
            ],
            exitConcept={
                "stoploss": "2.5% - 4%",
                "takeProfit": "1.5R - 2R",
                "timeStop": "5-10 4h candles",
            },
            riskConcept={
                "regimeUse": "bear / weak recovery / failed bounce improves score but does not forbid shorts outside bear labels",
                "maxCoreConditions": 5,
                "shortSpecificWarning": "must avoid shorting after an already extended drop",
            },
            baselineHurdles=_candidate_hurdles("LF-CAND-B-4H-BEAR-REJECTION-SHORT", baseline_hurdles, pairs, "4h"),
            expectedStrength=[
                "addresses failed V13.4.29 short-rejection lessons with fewer gates",
                "keeps no-chase rule explicit",
                "separates short performance from long performance",
            ],
            knownRisk=[
                "short squeeze after failed bounce",
                "poor performance during high-liquidity relief rallies",
                "can overtrade if EMA rejection is defined too loosely",
            ],
            validationPlan=[
                "Implement after Candidate A or alongside it in V13.4.34 only.",
                "Backtest as short-only on BTC/ETH/SOL 4h from 20240101-.",
                "Report vs NoTrade, pair BuyHold opportunity cost, and EqualWeight.",
                "Report bear/recovery/sideways/crash exposure and no-chase failures.",
            ],
            invalidationRules=[
                "profit factor remains below 1 after slippage",
                "max drawdown is unacceptable for short-only low-frequency research",
                "large-drop chase trades dominate losses",
                "regime breakdown shows high losses outside intended contexts",
            ],
        ),
        LowFrequencyCandidateSpec(
            candidateId="LF-CAND-C-1D-REGIME-4H-ENTRY-ROUTER",
            name="1D Regime + 4H Entry Directional Router",
            direction="long_or_short",
            timeframe="1d regime + 4h entry",
            pairs=pairs,
            coreConditions=[
                "1d regime gives directional bias",
                "4h confirms direction",
                "avoidScore not high",
                "longScore or shortScore exceeds threshold",
                "entry not extended",
            ],
            exitConcept={
                "mode": "router-only first; does not define standalone exit rules",
                "futureUse": "routes Candidate A/B style entries into long/short/no-trade research lanes",
            },
            riskConcept={
                "regimeUse": "directional scoring background, not a single hard switch",
                "maxCoreConditions": 5,
                "firstImplementation": "report-only scoring before executable strategy use",
            },
            baselineHurdles=_candidate_hurdles("LF-CAND-C-1D-REGIME-4H-ENTRY-ROUTER", baseline_hurdles, pairs, "4h"),
            expectedStrength=[
                "unifies longScore, shortScore, and avoidScore explanations",
                "keeps regime as context rather than a brittle hard gate",
                "helps compare long/short decisions under one reporting layer",
            ],
            knownRisk=[
                "router can become overfit if too many score inputs are added",
                "ambiguous thresholds may hide discretionary logic",
                "needs careful no-trade accounting",
            ],
            validationPlan=[
                "Keep V13.4.34 report-only unless Candidate A/B are stable.",
                "Compare routed decisions against non-routed Candidate A/B.",
                "Report noTradeRatio by regime.",
            ],
            invalidationRules=[
                "score thresholds cannot be explained with 5 or fewer inputs",
                "router reduces transparency versus simple candidates",
                "router increases drawdown or overtrading without improving baseline comparisons",
            ],
        ),
        LowFrequencyCandidateSpec(
            candidateId="LF-CAND-D-4H-BREAKOUT-RETEST",
            name="4H Breakout / Breakdown Retest",
            direction="long_or_short",
            timeframe="4h",
            pairs=pairs,
            coreConditions=[
                "break recent N-bar high or low",
                "retest confirms the breakout or breakdown level",
                "volume not collapsing",
                "close resumes in the breakout or breakdown direction",
            ],
            exitConcept={
                "stoploss": "near failed retest level with capped percent risk",
                "takeProfit": "1.5R - 2R or trailing after range expansion",
                "timeStop": "exit if retest does not follow through within 5-10 candles",
            },
            riskConcept={
                "primaryRisk": "false breakout or breakdown",
                "supportResistanceRequirement": "future implementation must define N-bar levels before backtesting",
                "maxCoreConditions": 4,
            },
            baselineHurdles=_candidate_hurdles("LF-CAND-D-4H-BREAKOUT-RETEST", baseline_hurdles, pairs, "4h"),
            expectedStrength=[
                "simple structure for both long and short research",
                "naturally supports no-trade when retest fails",
                "can be compared against passive baselines by pair",
            ],
            knownRisk=[
                "sample size may be sparse on 4h mainstream coins",
                "support/resistance definitions can become subjective",
                "false breakouts can cluster in volatile regimes",
            ],
            validationPlan=[
                "Defer executable implementation until Candidate A/B are evaluated.",
                "First validate N-bar level definitions in a report-only sample.",
                "Then compare long and short branches separately.",
            ],
            invalidationRules=[
                "too few events for statistical review",
                "level definition requires discretionary manual labeling",
                "false breakout losses dominate after slippage",
            ],
        ),
        LowFrequencyCandidateSpec(
            candidateId="LF-CAND-E-NOTRADE-DEFENSIVE-REGIME",
            name="NoTrade as Active Decision",
            direction="no_trade_filter",
            timeframe="1d / 4h",
            pairs=pairs,
            coreConditions=[
                "crash/high-volatility regime",
                "direction scores conflict",
                "liquidity or spread unavailable",
                "extreme candle or data anomaly",
            ],
            exitConcept={
                "output": ["no_trade", "observe_only"],
                "notAProfitModule": True,
            },
            riskConcept={
                "purpose": "reduce avoidable wrong-context trades",
                "futureUse": "defensive layer for all other candidates",
                "maxCoreConditions": 4,
            },
            baselineHurdles={
                "candidateId": "LF-CAND-E-NOTRADE-DEFENSIVE-REGIME",
                "noTradeHurdle": baseline_hurdles["noTradeHurdle"],
                "regimeHurdle": baseline_hurdles["regimeHurdle"],
                "requiredFutureComparison": [
                    "reduction in losing trades",
                    "noTradeRatio by regime",
                    "opportunity cost versus BuyHold and EqualWeight",
                ],
            },
            expectedStrength=[
                "turns no-trade into an explicit research decision",
                "protects Candidate A/B/D from poor-context exposure",
                "keeps defensive behavior measurable",
            ],
            knownRisk=[
                "can over-filter and miss strong trends",
                "may improve drawdown while reducing return too much",
                "depends on quality of regime and data anomaly inputs",
            ],
            validationPlan=[
                "Evaluate as overlay on Candidate A and B in V13.4.34.",
                "Report no-trade opportunity cost versus BuyHold and EqualWeight.",
                "Do not allow it to hide poor candidate definitions.",
            ],
            invalidationRules=[
                "noTradeRatio is high but drawdown does not improve",
                "filter blocks most profitable historical periods",
                "filter depends on unavailable liquidity/spread data without fallback",
            ],
            status="research_only",
        ),
    ]


def build_v13_4_34_plan() -> dict[str, Any]:
    return {
        "version": "V13.4.34",
        "name": "Low-Frequency Candidate Implementation and Research Backtest",
        "status": "planned",
        "scope": {
            "pairs": DEFAULT_PAIRS,
            "timeframe": "4h",
            "timerange": "20240101-",
            "candidatesToImplement": [
                "LF-CAND-A-4H-EMA-TREND-LONG",
                "LF-CAND-B-4H-BEAR-REJECTION-SHORT",
                "LF-CAND-E-NOTRADE-DEFENSIVE-REGIME",
            ],
            "deferredCandidates": [
                "LF-CAND-C-1D-REGIME-4H-ENTRY-ROUTER",
                "LF-CAND-D-4H-BREAKOUT-RETEST",
            ],
        },
        "requiredOutputs": [
            "candidate comparison report",
            "baseline comparison",
            "long/short breakdown",
            "regime breakdown",
            "slippage-adjusted metrics",
            "dryRunApproved=false",
            "liveTradingApproved=false",
        ],
        "nonGoals": [
            "no real API key",
            "no Trade API",
            "no Withdraw API",
            "no account reads",
            "no position reads",
            "no real orders",
            "no auto trading",
        ],
    }


def build_low_frequency_candidate_spec_package(baseline_report: dict[str, Any]) -> dict[str, Any]:
    return {
        "baselineHurdles": build_baseline_hurdles(baseline_report),
        "candidates": build_candidate_specs(baseline_report),
        "directionalScoreFramework": build_directional_score_framework(),
        "v13_4_34Plan": build_v13_4_34_plan(),
    }
