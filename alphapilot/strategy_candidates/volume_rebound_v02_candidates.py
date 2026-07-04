"""Evidence-based V0.2 candidate definitions.

These candidates are design artifacts only. They are not enabled strategies,
not tuned parameters, and not dry-run approvals.
"""

from __future__ import annotations

from typing import Any

from alphapilot.strategy_candidates.candidate_schema import StrategyCandidate


def evidence_item(source: str, metric: str, value: Any, note: str) -> dict[str, Any]:
    return {
        "source": source,
        "metric": metric,
        "value": value if value is not None else "unavailable",
        "note": note,
    }


def build_volume_rebound_v02_candidates(evidence: dict[str, Any]) -> list[StrategyCandidate]:
    return [
        StrategyCandidate(
            candidateId="alpha_volume_rebound_v02_a_trend_strict",
            name="V0.2A Trend Strict Filter",
            description="Strengthen the 4h trend gate to reduce weak-trend rebound failures.",
            status="candidate_only",
            evidence=[
                evidence_item(
                    "V13.4.2 signal audit",
                    "top_skip_reason",
                    evidence.get("topSkipReason"),
                    "Weak 4h trend was the most common primary skip reason.",
                ),
                evidence_item(
                    "V13.4.2 signal audit",
                    "final_entry_count",
                    evidence.get("finalEntryCount"),
                    "Signals that passed the current 4h gate were still negative overall in V13.4.",
                ),
                evidence_item(
                    "V13.4.1 diagnosis",
                    "profit_factor",
                    evidence.get("profitFactor"),
                    "The V0.1 smoke profit factor is below 1.",
                ),
            ],
            proposedChanges=[
                "Compare close_4h >= ema200_4h instead of close_4h >= ema200_4h * 0.98.",
                "Optionally require 4h EMA20 >= 4h EMA200.",
                "Optionally require non-negative 4h EMA20 slope.",
            ],
            expectedImpact=[
                "Reduce trades in weak trend regimes.",
                "Reduce stop-loss pressure from low-quality rebounds.",
                "Lower total trade count before fees.",
            ],
            risks=[
                "May filter too aggressively and miss early rebounds.",
                "May reduce sample size enough to make results unstable.",
                "Could overfit the V13.4 smoke period if adopted without broader comparison.",
            ],
            whatToTest=[
                "V0.1 baseline versus trend-strict variant on the same BTC/ETH/SOL smoke sample.",
                "Compare total return, max drawdown, profit factor, trade count, and max consecutive losses.",
                "Review pair and month breakdown to ensure April loss does not simply move to another bucket.",
            ],
            doNotAssume=[
                "Do not assume stricter trend automatically improves profit.",
                "Do not approve Dry-run from this candidate alone.",
            ],
        ),
        StrategyCandidate(
            candidateId="alpha_volume_rebound_v02_b_volume_quality",
            name="V0.2B Volume Quality Filter",
            description="Raise the volume-quality bar to reduce low-quality rebound attempts and fee drag.",
            status="candidate_only",
            evidence=[
                evidence_item(
                    "V13.4.2 signal audit",
                    "volume_filter_primary_blocks",
                    evidence.get("volumePrimaryBlocks"),
                    "Volume ratio was a major primary blocker, suggesting the filter is important.",
                ),
                evidence_item(
                    "V13.4.1 diagnosis",
                    "estimated_fees_paid",
                    evidence.get("estimatedFeesPaid"),
                    "Fees are material for the 15m sample.",
                ),
                evidence_item(
                    "V13.4.1 diagnosis",
                    "total_trades",
                    evidence.get("totalTrades"),
                    "The smoke sample traded frequently enough that weak signals have cost impact.",
                ),
            ],
            proposedChanges=[
                "Compare volumeRatio >= 2.0 against the V0.1 threshold of 1.5.",
                "Add a non-isolated spike check so one-candle volume spikes do not qualify alone.",
                "Consider a candle body quality check before accepting a rebound candle.",
            ],
            expectedImpact=[
                "Reduce low-quality trades.",
                "Reduce fee drag by lowering unnecessary entries.",
                "Potentially improve signal selectivity.",
            ],
            risks=[
                "May reject valid early rebounds.",
                "Volume thresholds can be pair-specific and unstable across regimes.",
                "A stricter threshold may reduce trades without improving expectancy.",
            ],
            whatToTest=[
                "Compare trade count reduction versus profit factor improvement.",
                "Review whether SOL remains overrepresented after volume-quality filtering.",
                "Run fee and slippage-adjusted metrics in V13.4.4.",
            ],
            doNotAssume=[
                "Do not treat volumeRatio 2.0 as final before comparative backtesting.",
                "Do not ignore pair-specific volume behavior.",
            ],
        ),
        StrategyCandidate(
            candidateId="alpha_volume_rebound_v02_c_exit_cleanup",
            name="V0.2C Exit Cleanup",
            description="Re-evaluate MACD weakness exit behavior because it lost heavily in V13.4.1.",
            status="candidate_only",
            evidence=[
                evidence_item(
                    "V13.4.1 diagnosis",
                    "macd_weak_exit_net_profit",
                    evidence.get("macdWeakExitNetProfit"),
                    "MACD two-candle weakness was a large losing exit bucket.",
                ),
                evidence_item(
                    "V13.4.1 diagnosis",
                    "stop_loss_net_profit",
                    evidence.get("stopLossNetProfit"),
                    "Stop loss remained the largest losing exit bucket.",
                ),
                evidence_item(
                    "V13.4.1 diagnosis",
                    "average_holding_minutes",
                    evidence.get("averageHoldingMinutes"),
                    "Current exits are concentrated in short holding windows.",
                ),
            ],
            proposedChanges=[
                "Compare MACD weakness exit only when current trade profit is positive.",
                "Compare removing MACD weakness exit and relying on ROI, stoploss, and time stop.",
                "Compare MACD weakness exit only when close is also below EMA20.",
            ],
            expectedImpact=[
                "Reduce noisy exits that cut positions in losing zones.",
                "Clarify whether MACD exit helps or hurts net expectancy.",
                "Potentially improve average loss handling if combined with early failure logic.",
            ],
            risks=[
                "Removing or gating MACD exit may hold losing trades longer.",
                "May increase drawdown or stop-loss count.",
                "Exit changes can interact with ROI and time stop in non-obvious ways.",
            ],
            whatToTest=[
                "Compare exit-reason breakdown after each exit-cleanup variant.",
                "Track stop_loss loss and MACD weakness loss separately.",
                "Require drawdown and max-loss-streak checks before considering any exit variant.",
            ],
            doNotAssume=[
                "Do not assume the MACD exit is bad in every market regime.",
                "Do not remove the exit in production without V13.4.4 comparison.",
            ],
        ),
        StrategyCandidate(
            candidateId="alpha_volume_rebound_v02_d_early_failure_exit",
            name="V0.2D Early Failure Exit",
            description="Add an early failure check for rebounds that do not work soon after entry.",
            status="candidate_only",
            evidence=[
                evidence_item(
                    "V13.4.1 diagnosis",
                    "weakest_holding_bucket",
                    evidence.get("weakestHoldingBucket"),
                    "The 1-3h holding bucket was the weakest result bucket.",
                ),
                evidence_item(
                    "V13.4.1 diagnosis",
                    "max_consecutive_losses",
                    evidence.get("maxConsecutiveLosses"),
                    "Loss streak risk is high in the smoke run.",
                ),
                evidence_item(
                    "V13.4.1 diagnosis",
                    "stop_loss_trade_count",
                    evidence.get("stopLossTradeCount"),
                    "Stop-loss exits are a large realized-loss bucket.",
                ),
            ],
            proposedChanges=[
                "Compare an exit if the trade is not profitable after 4 closed 15m candles.",
                "Compare an exit if the trade is not profitable after 6 closed 15m candles.",
                "Compare replacing 12-candle no-profit time stop with 8 closed 15m candles.",
            ],
            expectedImpact=[
                "Reduce failed rebounds before they reach stop loss.",
                "Reduce time spent in unproductive 1-3h trades.",
                "Potentially reduce max consecutive losses.",
            ],
            risks=[
                "May exit before delayed rebounds recover.",
                "May reduce win rate if early failure rules are too sensitive.",
                "Needs careful slippage/fee treatment because it can add churn.",
            ],
            whatToTest=[
                "Compare 4-candle, 6-candle, and 8-candle variants separately.",
                "Measure changes in 1-3h holding bucket, stop_loss loss, and total fees.",
                "Reject variants that improve return but worsen drawdown materially.",
            ],
            doNotAssume=[
                "Do not assume shorter holding is safer without drawdown evidence.",
                "Do not add an early exit without fee-adjusted comparison.",
            ],
        ),
        StrategyCandidate(
            candidateId="alpha_volume_rebound_v02_e_pair_risk_watchlist",
            name="V0.2E Pair Risk Watchlist",
            description="Track pair-level risk and exposure without permanently excluding SOL.",
            status="candidate_only",
            evidence=[
                evidence_item(
                    "V13.4.1 diagnosis",
                    "largest_pair_loss",
                    evidence.get("largestPairLoss"),
                    "SOL was the largest pair-level loss in the smoke sample.",
                ),
                evidence_item(
                    "V13.4.2 signal audit",
                    "sol_final_entries_actual_trades",
                    evidence.get("solSignalTradeCounts"),
                    "SOL had the highest final-entry and actual-trade count among the three pairs.",
                ),
                evidence_item(
                    "V13.4.1 diagnosis",
                    "sol_profit_factor",
                    evidence.get("solProfitFactor"),
                    "SOL profit factor was below 1 in the smoke sample.",
                ),
            ],
            proposedChanges=[
                "Add pair-level monitoring to the comparison report.",
                "Compare pair-level cooldown after a loss streak.",
                "Compare max trades per pair per day.",
                "Compare pair-level risk cap without permanently excluding SOL.",
            ],
            expectedImpact=[
                "Reduce single-pair overexposure.",
                "Make pair-specific drawdown visible before Top 30 expansion.",
                "Prepare a risk-control layer for broader universes.",
            ],
            risks=[
                "The smoke sample is too small to permanently blacklist a pair.",
                "Pair caps may reduce opportunity without improving expectancy.",
                "Pair-level controls can overfit recent volatility.",
            ],
            whatToTest=[
                "Measure pair contribution before and after pair-level controls.",
                "Compare SOL-specific loss reduction against total return and opportunity cost.",
                "Require the same logic to be tested on BTC and ETH, not SOL only.",
            ],
            doNotAssume=[
                "Do not permanently remove SOL based on one smoke timerange.",
                "Do not treat pair risk watchlist as proof of future underperformance.",
            ],
        ),
    ]


def recommended_comparison_plan() -> list[dict[str, Any]]:
    metrics = [
        "total_return",
        "max_drawdown",
        "profit_factor",
        "trade_count",
        "win_rate",
        "max_consecutive_losses",
        "pair_performance",
        "monthly_performance",
        "stop_loss_loss",
        "macd_weakness_exit_loss",
        "fees",
        "slippage_adjusted_net_return",
    ]
    return [
        {
            "step": 1,
            "variant": "V0.1 baseline",
            "purpose": "Keep the current V13.4 smoke baseline unchanged for comparison.",
            "metrics": metrics,
        },
        {
            "step": 2,
            "variant": "V0.2A trend strict",
            "purpose": "Test whether stricter 4h trend context reduces weak-trend losses.",
            "metrics": metrics,
        },
        {
            "step": 3,
            "variant": "V0.2B volume quality",
            "purpose": "Test whether a stronger volume-quality gate reduces fee drag and weak signals.",
            "metrics": metrics,
        },
        {
            "step": 4,
            "variant": "V0.2C exit cleanup",
            "purpose": "Test MACD weakness exit gating or removal against stop-loss and drawdown effects.",
            "metrics": metrics,
        },
        {
            "step": 5,
            "variant": "V0.2D early failure exit",
            "purpose": "Test whether earlier failure exits improve 1-3h loss behavior.",
            "metrics": metrics,
        },
        {
            "step": 6,
            "variant": "V0.2E pair risk watchlist",
            "purpose": "Test pair-level risk controls without permanently removing any pair.",
            "metrics": metrics,
        },
    ]


def do_not_change_yet() -> list[str]:
    return [
        "Do not enter Dry-run immediately.",
        "Do not trade live.",
        "Do not permanently remove SOL.",
        "Do not directly change stoploss.",
        "Do not directly change take profit.",
        "Do not raise volumeRatio and treat it as final without comparison.",
        "Do not remove MACD weakness exit and ship it without comparison.",
        "Do not overfit to one smoke timerange.",
        "Do not expand to Top 30 before V0.2 comparison evidence is reviewed.",
    ]

