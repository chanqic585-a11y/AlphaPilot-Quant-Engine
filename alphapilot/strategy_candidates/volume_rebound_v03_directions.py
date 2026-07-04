"""V03 direction candidates after Volume Rebound V0.1/V0.2 rejection.

These are design candidates only. They are not executable strategies, not
trading advice, not Dry-run approval, and not live-trading approval.
"""

from __future__ import annotations

from typing import Any


def build_v03_candidate_directions() -> list[dict[str, Any]]:
    return [
        {
            "candidateId": "alpha_volume_rebound_v03a_trend_pullback_continuation",
            "name": "V03A - Trend Pullback Continuation",
            "positioning": "Trend pullback continuation strategy",
            "coreIdea": (
                "Trade only in clearer bullish trend structures, wait for a pullback into a support or EMA zone, "
                "and require renewed strength confirmation before any historical backtest entry."
            ),
            "ruleDirection": [
                "4h trend is clearly up.",
                "1h structure remains intact.",
                "15m pulls back toward EMA20, EMA50, or a support area.",
                "Price reclaims strength with volume confirmation.",
                "Avoid weak-trend rebound attempts.",
            ],
            "expectedBenefits": [
                "Improves structural context versus random rebound entries.",
                "Reduces weak-trend falling-knife behavior.",
                "May reduce trade frequency and cost drag.",
            ],
            "risks": [
                "Signal count may become too low.",
                "Late confirmation can miss early reversals.",
                "Trend filters can still fail in regime shifts.",
            ],
            "whatToSpecifyNext": [
                "Exact 4h and 1h trend definitions.",
                "Pullback zone definition and support evidence.",
                "Reclaim confirmation candle and volume rules.",
                "Reward/risk and time-stop framework.",
            ],
        },
        {
            "candidateId": "alpha_volume_rebound_v03b_breakout_retest_confirmation",
            "name": "V03B - Breakout Retest Confirmation",
            "positioning": "Breakout retest confirmation strategy",
            "coreIdea": (
                "Avoid random rebounds and wait for a close above a meaningful resistance level, then require a "
                "retest that holds before historical backtest entry."
            ),
            "ruleDirection": [
                "Identify a recent resistance zone.",
                "Require 15m or 1h close above that zone.",
                "Require retest without closing back below the breakout area.",
                "Use volume confirmation and BTC environment safety.",
                "Reject unconfirmed breakout candles.",
            ],
            "expectedBenefits": [
                "Clearer and more explainable entry structure.",
                "Can improve payoff by entering after market acceptance.",
                "Should reduce low-quality rebound attempts.",
            ],
            "risks": [
                "False breakouts remain possible.",
                "Retests may not appear.",
                "The setup may be too sparse for some pairs.",
            ],
            "whatToSpecifyNext": [
                "Resistance detection method.",
                "Retest tolerance and invalidation rules.",
                "Volume and momentum confirmation rules.",
                "Pair-level and daily signal caps.",
            ],
        },
        {
            "candidateId": "alpha_volume_rebound_v03c_high_score_signal_only",
            "name": "V03C - High Score Signal Only",
            "positioning": "Low-frequency high-quality signal strategy",
            "coreIdea": (
                "Keep the volume rebound theme but require a transparent multi-factor score. Only high-score "
                "historical signals enter backtesting."
            ),
            "ruleDirection": [
                "Score market safety, trend context, rebound location, volume quality, momentum improvement, and risk quality.",
                "Require score >= 80 before any backtest entry.",
                "Use pair-level exposure caps and daily signal limits.",
                "Record score components in reports for auditability.",
            ],
            "expectedBenefits": [
                "Directly attacks over-trading and noisy 15m signals.",
                "Makes entry quality measurable and auditable.",
                "Can later support supervised learning without changing the safety boundary.",
            ],
            "risks": [
                "Scoring weights can overfit easily.",
                "Signal count may become too low.",
                "Manual score design needs careful validation.",
            ],
            "whatToSpecifyNext": [
                "Score components and weights.",
                "Minimum sample-size rules.",
                "Ablation tests for each score component.",
                "Slippage-adjusted quality gate before Dry-run.",
            ],
        },
        {
            "candidateId": "alpha_volume_rebound_v03d_1h_main_timeframe",
            "name": "V03D - 1h Main Timeframe",
            "positioning": "Lower-noise 1h strategy direction",
            "coreIdea": (
                "Move the primary signal timeframe from 15m to 1h to reduce noise, trade count, and cost sensitivity."
            ),
            "ruleDirection": [
                "Use 1h candles as the main entry timeframe.",
                "Use 4h market regime and trend filters.",
                "Use 15m only for optional execution refinement in later versions.",
                "Require wider targets or stronger risk/reward than 1:1.",
            ],
            "expectedBenefits": [
                "Lower trade frequency.",
                "Lower fee and slippage sensitivity.",
                "More stable signal context than 15m-only entries.",
            ],
            "risks": [
                "Entries are slower.",
                "Sample size is smaller.",
                "Wider candles may require different stops and targets.",
            ],
            "whatToSpecifyNext": [
                "1h setup definition.",
                "4h regime filter.",
                "Reward/risk target and stop model.",
                "Minimum sample coverage before comparison.",
            ],
        },
    ]


def build_v03_quality_gate() -> dict[str, Any]:
    return {
        "dryRunApprovedByDefault": False,
        "minimumRequirements": [
            "slippage-adjusted total return > 0",
            "slippage-adjusted profit factor > 1.15",
            "max drawdown materially below V0.1/V0.2 expanded validation",
            "max consecutive losses acceptable for the proposed risk model",
            "trade count sufficient for evidence but not excessive",
            "no single pair dominates profit or loss",
            "passes smoke validation and six-month Top30 validation",
            "preferably passes a longer timerange before any Dry-run discussion",
        ],
        "stricterTargets": {
            "slippageAdjustedProfitFactor": ">= 1.2",
            "maxDrawdownPct": "< 25",
            "slippageAdjustedTotalReturnPct": "> 0",
            "tradeCount": "moderate, not high-churn",
            "pairDominance": "no single pair extreme",
        },
        "failureRule": "If these gates are not met, the candidate must not enter Dry-run.",
    }


def build_lessons_learned() -> list[str]:
    return [
        "Relative improvement is not strategy approval when absolute returns remain deeply negative.",
        "The current 15m rebound framework is highly cost-sensitive.",
        "A 1:1 payoff profile is weak when win rate is near the low-40% range and costs are material.",
        "The 4h trend filter blocks many weak contexts but is not sufficient by itself.",
        "Pair-level risk must be measured, capped, and reported instead of handled through permanent one-off exclusions.",
        "V03 should start from entry quality, trade frequency, payoff, and regime design rather than small threshold edits.",
    ]


def build_do_not_proceed_items() -> list[str]:
    return [
        "Do not enter Dry-run with V0.1/V0.2.",
        "Do not continue minor B/C/E threshold edits as the next step.",
        "Do not treat V02C relative improvement as usable performance.",
        "Do not run live trading.",
        "Do not add real API keys.",
        "Do not call Trade API or Withdraw API.",
        "Do not read real accounts or positions.",
        "Do not create real orders.",
        "Do not auto trade.",
    ]

