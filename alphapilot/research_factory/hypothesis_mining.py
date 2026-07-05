"""Mine V13.4.25 strategy research hypotheses from local reports only.

This module reads existing research outputs and creates research hypotheses.
It does not write strategy code, run Freqtrade, enter Dry-run, call exchange
APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

from alphapilot.research_factory.hypothesis_registry import RESEARCH_ONLY_WARNING, SOURCE_REPORTS
from alphapilot.research_factory.hypothesis_schema import HypothesisMiningResult, ResearchHypothesis

REPORT_ID = "v13_4_25_strategy_research_factory"
VERSION = "V13.4.25"


def _read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"Missing input report: {path.as_posix()}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"Unable to parse {path.as_posix()}: {exc}")
        return {}


def _num(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _find_factor(rows: list[dict[str, Any]], factor_id: str) -> dict[str, Any]:
    for row in rows:
        if row.get("factorId") == factor_id:
            return row
    return {}


def _find_benchmark(rows: list[dict[str, Any]], class_name: str) -> dict[str, Any]:
    for row in rows:
        if row.get("className") == class_name or row.get("benchmarkId") == class_name:
            return row
    return {}


def _format_metric(value: Any) -> str:
    number = _num(value)
    return "unavailable" if number is None else str(round(number, 6))


def _input_summaries(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    factor_report = reports["factorEvaluation"]
    candidate_report = reports["factorCandidates"]
    benchmark_report = reports["benchmarkSuite"]
    review = reports["benchmarkReview"]
    archive = reports["benchmarkArchive"]
    return {
        "factorEvaluation": {
            "reportId": factor_report.get("reportId"),
            "sampleCount": factor_report.get("sampleCount"),
            "validLabelCount": factor_report.get("validLabelCount"),
            "evaluatedFactorCount": factor_report.get("evaluatedFactorCount"),
            "candidateFactorCount": len(factor_report.get("candidateFactors", [])),
            "topFactorsByRankIC": factor_report.get("topFactorsByRankIC", [])[:5],
            "topFactorsBySpread": factor_report.get("topFactorsBySpread", [])[:5],
            "topFactorsByProfitFactor": factor_report.get("topFactorsByProfitFactor", [])[:5],
        },
        "factorCandidates": {
            "reportId": candidate_report.get("reportId"),
            "candidateCount": candidate_report.get("candidateCount"),
            "notTradeReady": candidate_report.get("notTradeReady"),
        },
        "benchmarkSuite": {
            "reportId": benchmark_report.get("reportId"),
            "timerange": benchmark_report.get("timerange"),
            "timeframe": benchmark_report.get("timeframe"),
            "bestBenchmarkRaw": benchmark_report.get("bestBenchmarkRaw"),
            "bestBenchmarkSlippageAdjusted": benchmark_report.get("bestBenchmarkSlippageAdjusted"),
            "activeBenchmarkCount": len([row for row in benchmark_report.get("benchmarks", []) if row.get("type") == "freqtrade_backtest_baseline"]),
        },
        "benchmarkReview": {
            "reportId": review.get("reportId"),
            "noTradeSummary": review.get("noTradeComparison", {}).get("summary"),
            "buyHoldBtcSummary": review.get("buyHoldBtcComparison", {}).get("summary"),
            "recommendedNextStep": review.get("recommendedNextStep"),
            "failureFindingCount": len(review.get("failureFindings", [])),
            "usefulHypothesisSeedCount": len(review.get("usefulHypothesisSeeds", [])),
        },
        "benchmarkArchive": {
            "reportId": archive.get("reportId"),
            "manifestStrategiesSucceeded": archive.get("manifestStrategiesSucceeded"),
            "benchmarkCount": len(archive.get("benchmarks", [])),
        },
    }


def _common_risk_notes(extra: list[str] | None = None) -> list[str]:
    notes = [
        "Research-only hypothesis.",
        "Not a Freqtrade strategy.",
        "Not Dry-run approval.",
        "Not live trading approval.",
        "No Trade API, Withdraw API, API key, account read, position read, order, or auto trading is involved.",
        "Future validation must compare against NoTrade, BuyHoldBTC, and BenchmarkBollingerRebound after costs.",
    ]
    if extra:
        notes.extend(extra)
    return notes


def _evidence(source: str, observation: str, metrics: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"source": source, "observation": observation}
    if metrics:
        payload["metrics"] = metrics
    return payload


def mine_strategy_research_hypotheses(
    factor_report_path: Path = Path(SOURCE_REPORTS["factorEvaluation"]),
    factor_candidates_path: Path = Path(SOURCE_REPORTS["factorCandidates"]),
    benchmark_report_path: Path = Path(SOURCE_REPORTS["benchmarkSuite"]),
    benchmark_review_path: Path = Path(SOURCE_REPORTS["benchmarkReview"]),
    benchmark_archive_path: Path = Path(SOURCE_REPORTS["benchmarkArchive"]),
) -> HypothesisMiningResult:
    warnings = [RESEARCH_ONLY_WARNING]
    reports = {
        "factorEvaluation": _read_json(factor_report_path, warnings),
        "factorCandidates": _read_json(factor_candidates_path, warnings),
        "benchmarkSuite": _read_json(benchmark_report_path, warnings),
        "benchmarkReview": _read_json(benchmark_review_path, warnings),
        "benchmarkArchive": _read_json(benchmark_archive_path, warnings),
    }

    factor_report = reports["factorEvaluation"]
    benchmark_report = reports["benchmarkSuite"]
    review = reports["benchmarkReview"]
    top_rank_ic = factor_report.get("topFactorsByRankIC", [])
    top_spread = factor_report.get("topFactorsBySpread", [])
    top_pf = factor_report.get("topFactorsByProfitFactor", [])
    review_benchmarks = review.get("benchmarkReviews", [])
    best_benchmark = review.get("bestBenchmarkReview", {})

    volatility_3d = _find_factor(top_rank_ic, "volatility_3d")
    atr_pct = _find_factor(top_rank_ic, "atr_pct") or _find_factor(top_pf, "atr_pct")
    trend_strength_spread = _find_factor(top_spread, "trend_strength")
    trend_strength_pf = _find_factor(top_pf, "trend_strength")
    ema50_spread = _find_factor(top_spread, "distance_to_ema50")
    ema50_pf = _find_factor(top_pf, "distance_to_ema50")
    volume_spread = _find_factor(top_spread, "volume_expansion_3d")
    volume_pf = _find_factor(top_pf, "volume_expansion_3d")
    bollinger_spread = _find_factor(top_spread, "bollinger_position")
    rsi_review = _find_benchmark(review_benchmarks, "BenchmarkRSIMeanReversion")
    ema_review = _find_benchmark(review_benchmarks, "BenchmarkEMATrend")
    macd_review = _find_benchmark(review_benchmarks, "BenchmarkMACDVolume")

    source_factor = [SOURCE_REPORTS["factorEvaluation"], SOURCE_REPORTS["factorCandidates"]]
    source_benchmark = [SOURCE_REPORTS["benchmarkSuite"], SOURCE_REPORTS["benchmarkReview"], SOURCE_REPORTS["benchmarkArchive"]]
    source_all = source_factor + source_benchmark

    hypotheses = [
        ResearchHypothesis(
            hypothesisId="HYP-001",
            name="Volatility as Risk Filter",
            category="factor_based",
            status="research_only",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["factorEvaluation"],
                    "Volatility and ATR ranked near the top by rank IC, but with negative directionality, suggesting risk-filter use before entry use.",
                    {
                        "volatility_3d_meanRankIC": volatility_3d.get("meanRankIC"),
                        "atr_pct_meanRankIC": atr_pct.get("meanRankIC"),
                    },
                ),
                _evidence(
                    SOURCE_REPORTS["factorEvaluation"],
                    "V13.4.22 produced zero trade-ready candidate factors; volatility should remain a filter hypothesis only.",
                    {"candidateFactors": len(factor_report.get("candidateFactors", []))},
                ),
            ],
            sourceReports=source_factor,
            proposedMechanism="Use volatility and ATR context to avoid unstable samples or separate high-risk regimes before considering any entry rule.",
            expectedBehavior="Future candidates should trade less in extreme volatility buckets and show lower drawdown after costs.",
            riskNotes=_common_risk_notes(["Negative rank IC does not imply direct edge; it only supports regime segmentation research."]),
            requiredData=["FactorDataPanel volatility_3d", "FactorDataPanel volatility_24h", "FactorDataPanel atr_pct", "forward labels"],
            validationPlan=[
                "Build validation dataset by volatility and ATR buckets.",
                "Measure NoTrade, BuyHoldBTC, and benchmark-relative outcomes per bucket.",
                "Check stability by pair, month, and regime before any strategy design.",
            ],
            invalidationRules=[
                "Reject if volatility buckets do not reduce drawdown or improve loss avoidance after costs.",
                "Reject if bucket behavior is concentrated in one pair or one month.",
            ],
            priority="high",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-002",
            name="Trend Strength as Regime Filter",
            category="regime_based",
            status="research_only",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["factorEvaluation"],
                    "trend_strength ranked first by top-bottom spread and first by profit factor, though the profit factor is only near breakeven.",
                    {
                        "topBottomSpread": trend_strength_spread.get("topBottomSpread"),
                        "profitFactor": trend_strength_pf.get("profitFactor"),
                    },
                ),
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "Simple EMA trend benchmarks failed badly, so trend evidence should gate regimes rather than become a simple crossover rule.",
                    {"emaTrendStatus": ema_review.get("status"), "emaTrendWeakness": ema_review.get("mainWeakness")},
                ),
            ],
            sourceReports=[SOURCE_REPORTS["factorEvaluation"], SOURCE_REPORTS["benchmarkReview"]],
            proposedMechanism="Use trend strength as a regime label that decides whether mean-reversion, pullback, or no-trade hypotheses are eligible.",
            expectedBehavior="Future validation should show that some rule families perform less poorly or more selectively inside trend-compatible regimes.",
            riskNotes=_common_risk_notes(["Simple trend entries already failed; this hypothesis must not become EMA-cross tuning."]),
            requiredData=["trend_strength", "ema20", "ema50", "ema200", "regime labels", "benchmark outcomes"],
            validationPlan=[
                "Segment factor and benchmark results by trend_strength buckets.",
                "Compare benchmark family behavior inside high, medium, and low trend regimes.",
                "Require cost-adjusted improvement before any entry rule work.",
            ],
            invalidationRules=[
                "Reject if high trend_strength does not improve benchmark-relative outcomes after costs.",
                "Reject if the effect reverses across pair or month slices.",
            ],
            priority="high",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-003",
            name="EMA50 Distance as Pullback Context",
            category="factor_based",
            status="research_only",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["factorEvaluation"],
                    "distance_to_ema50 ranked second by spread and near the top by profit factor, but did not become a trade-ready candidate.",
                    {
                        "topBottomSpread": ema50_spread.get("topBottomSpread"),
                        "profitFactor": ema50_pf.get("profitFactor"),
                    },
                ),
            ],
            sourceReports=source_factor,
            proposedMechanism="Treat distance from EMA50 as context for pullback quality, not as a standalone trigger.",
            expectedBehavior="Pullback candidates should require favorable distance buckets and avoid overextended entries.",
            riskNotes=_common_risk_notes(["EMA distance can encourage overfitting if optimized directly against failed benchmark results."]),
            requiredData=["distance_to_ema50", "distance_to_ema20", "trend_strength", "forward labels"],
            validationPlan=[
                "Evaluate forward labels by EMA50 distance buckets.",
                "Cross the buckets with trend_strength and volatility buckets.",
                "Check whether pullback contexts beat benchmark references after fees and slippage.",
            ],
            invalidationRules=[
                "Reject if EMA50 distance buckets have weak coverage or no monotonic separation.",
                "Reject if useful buckets disappear after slippage stress.",
            ],
            priority="medium",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-004",
            name="Bollinger Rebound Requires Regime Filter",
            category="benchmark_informed",
            status="research_only",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "BenchmarkBollingerRebound was the relative best active benchmark, but still negative and not tradable.",
                    {
                        "rawReturnPct": best_benchmark.get("rawReturnPct"),
                        "slippageAdjustedReturnPct": best_benchmark.get("slippageAdjustedReturnPct"),
                        "profitFactor": best_benchmark.get("profitFactor"),
                        "tradeCount": best_benchmark.get("tradeCount"),
                    },
                ),
                _evidence(
                    SOURCE_REPORTS["factorEvaluation"],
                    "bollinger_position appeared in spread ranking, supporting research use as context rather than standalone entry logic.",
                    {"topBottomSpread": bollinger_spread.get("topBottomSpread")},
                ),
            ],
            sourceReports=[SOURCE_REPORTS["factorEvaluation"], SOURCE_REPORTS["benchmarkReview"]],
            proposedMechanism="Study Bollinger rebound only when regime, volatility, and liquidity filters agree; standalone rebound logic is insufficient.",
            expectedBehavior="Filtered rebound samples should be lower frequency and less broadly negative than the unfiltered benchmark.",
            riskNotes=_common_risk_notes(["Relative best does not mean usable; V13.4.24 explicitly says relative best != tradable."]),
            requiredData=["bollinger_position", "trend_strength", "volatility_3d", "liquidity metrics", "benchmark stability slices"],
            validationPlan=[
                "Create a validation table for Bollinger position crossed with trend and volatility regimes.",
                "Measure trade frequency reduction and cost-adjusted outcomes.",
                "Keep BenchmarkBollingerRebound as the reference benchmark to beat.",
            ],
            invalidationRules=[
                "Reject if filtered samples remain below NoTrade or BuyHoldBTC after costs.",
                "Reject if pair/month stability remains broadly negative.",
            ],
            priority="high",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-005",
            name="Activity / Volume Expansion as Universe Filter",
            category="factor_based",
            status="research_only",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["factorEvaluation"],
                    "volume_expansion_3d ranked third by spread and appeared in the profit factor list, but below a trade-ready threshold.",
                    {
                        "topBottomSpread": volume_spread.get("topBottomSpread"),
                        "profitFactor": volume_pf.get("profitFactor"),
                    },
                ),
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "Momentum plus volume alone was cost sensitive, so volume should first filter universe/activity quality.",
                    {"macdVolumeStatus": macd_review.get("status"), "macdVolumeWeakness": macd_review.get("mainWeakness")},
                ),
            ],
            sourceReports=[SOURCE_REPORTS["factorEvaluation"], SOURCE_REPORTS["benchmarkReview"]],
            proposedMechanism="Use activity and volume expansion to filter tradable universe quality before strategy-rule evaluation.",
            expectedBehavior="Filtered universes should reduce dead samples and support more stable benchmark comparisons.",
            riskNotes=_common_risk_notes(["Volume expansion alone failed as a benchmark component; it must remain a universe-quality filter hypothesis."]),
            requiredData=["volume_expansion_3d", "volume_expansion_24h", "quote volume", "trade count", "dynamic universe snapshots"],
            validationPlan=[
                "Compare factor outcomes inside active-volume buckets versus low-activity buckets.",
                "Measure coverage, liquidity, and slippage sensitivity by bucket.",
                "Validate with dynamic historical universe membership to avoid lookahead bias.",
            ],
            invalidationRules=[
                "Reject if activity filters only select high-cost churn.",
                "Reject if effects disappear outside the Top10 sample.",
            ],
            priority="medium",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-006",
            name="Low Frequency Requirement",
            category="execution_reality",
            status="research_only",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "V13.4.24 found high or very high cost sensitivity across all active benchmarks.",
                    {"failureFindings": [item for item in review.get("failureFindings", []) if "cost sensitivity" in item.lower()]},
                ),
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "Relative best BenchmarkBollingerRebound traded less than the very high-turnover references but still failed after costs.",
                    {"tradeCount": best_benchmark.get("tradeCount"), "slippageAdjustedReturnPct": best_benchmark.get("slippageAdjustedReturnPct")},
                ),
            ],
            sourceReports=source_benchmark,
            proposedMechanism="Require future strategy hypotheses to prove lower turnover before implementation, because frequent simple rules were overwhelmed by costs.",
            expectedBehavior="Future candidates should show fewer trades, lower fee/slippage drag, and stronger per-trade expectancy before any code strategy work.",
            riskNotes=_common_risk_notes(["Frequency reduction is a research constraint, not a guarantee of edge."]),
            requiredData=["trade count", "fee impact", "slippage impact", "holding duration", "exit attribution"],
            validationPlan=[
                "Add turnover bands to future hypothesis validation datasets.",
                "Rank candidate contexts by cost-adjusted expectancy, not raw hit rate.",
                "Require low-frequency viability before Freqtrade implementation.",
            ],
            invalidationRules=[
                "Reject candidates that need high turnover to produce weak raw results.",
                "Reject if cost-adjusted return remains worse than NoTrade.",
            ],
            priority="high",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-007",
            name="Liquidity Gate First",
            category="execution_reality",
            status="research_only",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "All active benchmarks underperformed after slippage stress; execution reality must precede entry logic.",
                    {"activeBenchmarksOutperformedNoTrade": review.get("noTradeComparison", {}).get("activeBenchmarksOutperformed")},
                ),
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "Losses were broad by pair and month rather than isolated to a small pocket.",
                    {"finding": "Pair and month stability do not show a robust positive pattern."},
                ),
            ],
            sourceReports=source_benchmark,
            proposedMechanism="Apply liquidity and execution feasibility gates before any hypothesis is eligible for rule validation.",
            expectedBehavior="The research factory should reject contexts with insufficient volume, wide slippage sensitivity, or poor execution feasibility before strategy coding.",
            riskNotes=_common_risk_notes(["Liquidity gates protect research quality only; they do not approve live execution."]),
            requiredData=["quote volume", "spread proxy", "slippage stress", "pair stability", "month stability", "dynamic universe snapshots"],
            validationPlan=[
                "Define minimum liquidity and slippage-stress thresholds for validation datasets.",
                "Measure whether candidate contexts survive execution-reality filters.",
                "Keep all failed liquidity contexts in the rejected hypothesis log.",
            ],
            invalidationRules=[
                "Reject if liquidity filtering does not materially change cost-adjusted outcomes.",
                "Reject if data coverage is too narrow for robust execution-reality assessment.",
            ],
            priority="high",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-008",
            name="BuyHoldBTC Benchmark Requirement",
            category="benchmark_informed",
            status="research_only",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "All active benchmarks underperformed BuyHoldBTC; passive BTC exposure lost less than frequent benchmark trading in this sample.",
                    {
                        "activeBenchmarksOutperformedBuyHoldBTC": review.get("buyHoldBtcComparison", {}).get("activeBenchmarksOutperformed"),
                        "buyHoldReturnPct": review.get("buyHoldBtcComparison", {}).get("buyHoldReturnPct"),
                    },
                ),
            ],
            sourceReports=source_benchmark,
            proposedMechanism="Every future hypothesis must include a mandatory BuyHoldBTC comparison before promotion.",
            expectedBehavior="Research promotion only happens when a candidate has a plausible path to beat NoTrade and BuyHoldBTC after costs.",
            riskNotes=_common_risk_notes(["Benchmark comparison is necessary but not sufficient for Dry-run approval."]),
            requiredData=["NoTrade baseline", "BuyHoldBTC baseline", "relative active benchmark returns", "slippage-adjusted outcomes"],
            validationPlan=[
                "Embed NoTrade, BuyHoldBTC, and BenchmarkBollingerRebound baselines into future validation reports.",
                "Require benchmark-relative tables before any implementation proposal.",
            ],
            invalidationRules=[
                "Reject or defer any hypothesis without benchmark-relative measurement.",
                "Reject any hypothesis that only beats one weak active benchmark but fails NoTrade or BuyHoldBTC.",
            ],
            priority="high",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-009",
            name="Regime Router Before Rule Family",
            category="regime_based",
            status="research_only",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "Simple rule families failed broadly, implying rule family selection may need regime routing before entry evaluation.",
                    {"failureFindingCount": len(review.get("failureFindings", []))},
                ),
                _evidence(
                    SOURCE_REPORTS["factorEvaluation"],
                    "Several factors were unstable across pairs or regimes, so validation must explicitly separate regimes.",
                    {"unstableFactorCount": len(factor_report.get("unstableFactors", []))},
                ),
            ],
            sourceReports=source_all,
            proposedMechanism="Route future hypotheses by regime first, then evaluate whether trend, rebound, or avoid logic is even eligible.",
            expectedBehavior="Regime-routed validation should reveal smaller, testable pockets or reject rule families earlier.",
            riskNotes=_common_risk_notes(["Regime routers can overfit if built after seeing benchmark losses; validation must be predeclared."]),
            requiredData=["regime labels", "trend_strength", "volatility buckets", "benchmark family outcomes"],
            validationPlan=[
                "Define fixed regime buckets before running candidate validation.",
                "Measure each benchmark family by regime bucket and pair/month stability.",
                "Defer any rule family with insufficient regime coverage.",
            ],
            invalidationRules=[
                "Reject if regime routing produces no stable bucket or relies on tiny samples.",
                "Reject if improvements are not visible after costs.",
            ],
            priority="medium",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-010",
            name="Dynamic Universe Quality Narrowing",
            category="execution_reality",
            status="deferred",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "Pair stability showed no positive pair pocket for the relative-best benchmark, so future tests need cleaner universe definitions.",
                    {"pairConcentration": best_benchmark.get("pairConcentration")},
                ),
            ],
            sourceReports=source_benchmark,
            proposedMechanism="Use dynamic historical universe and liquidity/activity filters to narrow research samples before rule-family testing.",
            expectedBehavior="A narrower, historically valid universe should reduce unsupported pair churn and make validation conclusions clearer.",
            riskNotes=_common_risk_notes(["Deferred until a validation dataset can preserve no-lookahead universe membership."]),
            requiredData=["historical dynamic universe snapshots", "volume buckets", "liquidity scores", "pair stability"],
            validationPlan=[
                "Build a no-lookahead dynamic universe validation dataset.",
                "Compare benchmark behavior inside and outside the universe filter.",
            ],
            invalidationRules=[
                "Reject if universe narrowing lowers coverage without improving cost-adjusted evidence.",
                "Reject if universe membership uses future information.",
            ],
            priority="medium",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-R01",
            name="Martingale Rejected",
            category="rejected",
            status="rejected",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "V13.4.24 explicitly rejected martingale due to unacceptable tail risk.",
                    {"rejectedIdeas": review.get("rejectedIdeas", [])},
                ),
            ],
            sourceReports=[SOURCE_REPORTS["benchmarkReview"]],
            proposedMechanism="No martingale, inverse averaging, or recovery-size escalation mechanism is allowed in AlphaPilot research.",
            expectedBehavior="Always rejected; never promoted to strategy, Dry-run, or live execution.",
            riskNotes=_common_risk_notes(["Tail-risk escalation conflicts with AlphaPilot risk-first principles."]),
            requiredData=[],
            validationPlan=["Keep in rejected registry and block from future candidate templates."],
            invalidationRules=["None. This remains rejected by safety policy."],
            priority="low",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-R02",
            name="RSI Only Rejected",
            category="rejected",
            status="rejected",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "BenchmarkRSIMeanReversion failed as a simple standalone benchmark and was highly cost sensitive.",
                    {"status": rsi_review.get("status"), "mainWeakness": rsi_review.get("mainWeakness"), "profitFactor": rsi_review.get("profitFactor")},
                ),
            ],
            sourceReports=[SOURCE_REPORTS["benchmarkReview"]],
            proposedMechanism="RSI-only oversold or overbought logic is rejected as a standalone strategy hypothesis.",
            expectedBehavior="RSI may be used as context in future validation but not as a standalone entry rule.",
            riskNotes=_common_risk_notes(["Standalone RSI logic was already disproven by the benchmark suite."]),
            requiredData=["RSI only as contextual feature in future studies"],
            validationPlan=["Use RSI only inside multi-factor validation datasets."],
            invalidationRules=["Reject any future plan that promotes RSI alone as a strategy."],
            priority="low",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-R03",
            name="Simple EMA Cross Rejected",
            category="rejected",
            status="rejected",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "BenchmarkEMATrend had excessive turnover and severe drawdown, so simple EMA trend logic remains a negative reference.",
                    {"status": ema_review.get("status"), "mainWeakness": ema_review.get("mainWeakness"), "profitFactor": ema_review.get("profitFactor")},
                ),
            ],
            sourceReports=[SOURCE_REPORTS["benchmarkReview"]],
            proposedMechanism="Simple EMA cross or plain EMA trend entries are rejected as standalone strategy hypotheses.",
            expectedBehavior="EMA context may help define regimes or pullback distance, but simple EMA cross entries should not be implemented.",
            riskNotes=_common_risk_notes(["Tuning a failed simple EMA benchmark would likely overfit a weak base."]),
            requiredData=["EMA only as contextual factor"],
            validationPlan=["Keep EMA trend benchmark as a negative reference."],
            invalidationRules=["Reject any future plan that only changes EMA lengths on the same failed mechanism."],
            priority="low",
        ),
        ResearchHypothesis(
            hypothesisId="HYP-R04",
            name="MACD Volume Only Rejected",
            category="rejected",
            status="rejected",
            evidence=[
                _evidence(
                    SOURCE_REPORTS["benchmarkReview"],
                    "BenchmarkMACDVolume was highly cost sensitive and did not produce usable evidence.",
                    {"status": macd_review.get("status"), "mainWeakness": macd_review.get("mainWeakness"), "profitFactor": macd_review.get("profitFactor")},
                ),
            ],
            sourceReports=[SOURCE_REPORTS["benchmarkReview"]],
            proposedMechanism="MACD plus volume alone is rejected as a standalone strategy hypothesis.",
            expectedBehavior="MACD or volume can be studied as support context only.",
            riskNotes=_common_risk_notes(["Momentum-volume evidence must be filtered by regime, liquidity, and frequency before any strategy work."]),
            requiredData=["MACD histogram", "volume expansion", "regime labels"],
            validationPlan=["Use as rejected benchmark reference and contextual factor only."],
            invalidationRules=["Reject standalone MACD-volume entry proposals."],
            priority="low",
        ),
    ]

    _validate_hypotheses(hypotheses, warnings)
    return HypothesisMiningResult(
        reportId=REPORT_ID,
        version=VERSION,
        status="research_only",
        inputReportSummaries=_input_summaries(reports),
        hypotheses=hypotheses,
        warnings=warnings,
        dryRunApproved=False,
        liveTradingApproved=False,
    )


def _validate_hypotheses(hypotheses: list[ResearchHypothesis], warnings: list[str]) -> None:
    ids = [item.hypothesisId for item in hypotheses]
    duplicate_ids = [item for item, count in Counter(ids).items() if count > 1]
    if duplicate_ids:
        warnings.append(f"Duplicate hypothesis IDs found: {', '.join(duplicate_ids)}")
    for item in hypotheses:
        if item.dryRunApproved or item.liveTradingApproved:
            warnings.append(f"{item.hypothesisId} attempted approval escalation; approvals must remain false.")
        if not item.evidence:
            warnings.append(f"{item.hypothesisId} has no evidence.")
        if not item.riskNotes:
            warnings.append(f"{item.hypothesisId} has no risk notes.")


def summarize_hypotheses(hypotheses: list[ResearchHypothesis]) -> dict[str, Any]:
    return {
        "total": len(hypotheses),
        "byCategory": dict(Counter(item.category for item in hypotheses)),
        "byStatus": dict(Counter(item.status for item in hypotheses)),
        "byPriority": dict(Counter(item.priority for item in hypotheses)),
        "highPriority": [item.hypothesisId for item in hypotheses if item.priority == "high"],
        "rejected": [item.hypothesisId for item in hypotheses if item.status == "rejected"],
    }
