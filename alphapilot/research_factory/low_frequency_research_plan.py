"""Build the V13.4.31 low-frequency mainstream coin research plan."""

from __future__ import annotations

from alphapilot.research_factory.low_frequency_research_schema import (
    LowFrequencyHypothesis,
    LowFrequencyResearchPlan,
)


PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
PRIMARY_TIMEFRAMES = ["4h", "1d"]
OPTIONAL_TIMEFRAMES = ["1h"]


def build_low_frequency_hypotheses() -> list[LowFrequencyHypothesis]:
    return [
        LowFrequencyHypothesis(
            hypothesisId="LF-HYP-001",
            name="BTC/ETH/SOL 4h Trend Following",
            thesis="On mainstream coins, a 4h trend-following structure may be more stable than 1h high-frequency indicator signals.",
            direction="long_only",
            primaryTimeframe="4h",
            informativeTimeframes=["1d"],
            coreConditions=[
                "4h close > EMA200",
                "4h EMA20 > EMA50",
                "4h trend slope positive",
                "pullback then reclaim EMA20",
            ],
            regimeUse="Long candidates receive higher weight in bull, recovery, and neutral-positive regimes; bear/crash regimes reduce long weight.",
            validationFocus=[
                "trade count reduction versus 1h research",
                "slippage-adjusted performance versus NoTrade and BuyHoldBTC",
                "drawdown behavior by regime",
            ],
        ),
        LowFrequencyHypothesis(
            hypothesisId="LF-HYP-002",
            name="BTC/ETH/SOL 4h Bear Rejection Short",
            thesis="On mainstream coins, 4h rebound-failure shorts may be more stable than broad 1h short conditions.",
            direction="short_only",
            primaryTimeframe="4h",
            informativeTimeframes=["1d"],
            coreConditions=[
                "4h close < EMA200",
                "4h EMA20 < EMA50",
                "price rebounds near EMA20 or EMA50",
                "4h close weakens after rebound",
            ],
            regimeUse="Short candidates can appear outside bear regimes, but bull/recovery regimes reduce short weight and require stronger confirmation.",
            validationFocus=[
                "trade count reduction versus V13.4.29",
                "avoidance of chase shorts",
                "short results by bull, recovery, bear, and crash regimes",
            ],
        ),
        LowFrequencyHypothesis(
            hypothesisId="LF-HYP-003",
            name="1d Regime plus 4h Entry",
            thesis="A 1d regime filter paired with 4h entries may reduce noisy trades compared with single-timeframe 1h logic.",
            direction="long_or_short_separated",
            primaryTimeframe="4h",
            informativeTimeframes=["1d"],
            coreConditions=[
                "1d regime label available",
                "4h setup direction agrees with 1d context",
                "avoidScore remains below threshold",
                "entry occurs after 4h confirmation candle",
            ],
            regimeUse="Regime is not a sole on/off switch; it weights longScore, shortScore, and avoidScore.",
            validationFocus=[
                "whether no-trade decisions reduce drawdown",
                "long/short results separated by regime",
                "exposure reduction during bear, crash, and high-volatility regimes",
            ],
        ),
        LowFrequencyHypothesis(
            hypothesisId="LF-HYP-004",
            name="Breakout Retest on Mainstream Coins",
            thesis="4h breakout or breakdown retest structures may provide cleaner context than pure moving-average pursuit.",
            direction="long_and_short_modules",
            primaryTimeframe="4h",
            informativeTimeframes=["1d"],
            coreConditions=[
                "break above recent N-bar high or below recent N-bar low",
                "retest holds the breakout or breakdown area",
                "volume does not contract materially",
                "avoidScore remains low",
            ],
            regimeUse="Bull/recovery boosts long retests; bear/crash boosts short breakdown retests; sideways increases false-breakout caution.",
            validationFocus=[
                "false breakout rate",
                "reward/risk profile",
                "benchmark comparison against simple 4h breakout retest",
            ],
        ),
        LowFrequencyHypothesis(
            hypothesisId="LF-HYP-005",
            name="NoTrade as Active Decision",
            thesis="In bear, crash, or high-volatility regimes, actively choosing no trade may outperform forced low-quality entries.",
            direction="avoidance_module",
            primaryTimeframe="1d",
            informativeTimeframes=["4h"],
            coreConditions=[
                "bear, crash, or high-volatility regime present",
                "direction scores are conflicted",
                "volatility or drawdown risk elevated",
                "setup quality below research threshold",
            ],
            regimeUse="Regime increases avoidScore and lowers exposure rather than automatically forcing a direction.",
            validationFocus=[
                "noTradeRatio by regime",
                "drawdown avoided versus always-active baselines",
                "opportunity cost versus BuyHoldBTC",
            ],
        ),
    ]


def build_long_short_framework() -> dict[str, object]:
    return {
        "scoreNames": ["longScore", "shortScore", "avoidScore"],
        "scoreInputs": {
            "longScore": [
                "4h trend strength",
                "1d regime support",
                "EMA structure",
                "breakout/retest quality",
                "pullback recovery quality",
            ],
            "shortScore": [
                "4h downtrend strength",
                "1d regime pressure",
                "failed rebound quality",
                "breakdown/retest quality",
                "relative weakness",
            ],
            "avoidScore": [
                "bear/crash risk for longs",
                "bull/recovery risk for shorts",
                "high-volatility instability",
                "conflicting indicator context",
                "insufficient data quality",
            ],
        },
        "interpretation": {
            "longCandidate": "longScore high and avoidScore low",
            "shortCandidate": "shortScore high and avoidScore low",
            "noTrade": "avoidScore high or direction scores conflicted",
        },
        "regimeRole": "Market regime adjusts direction scores and risk weight. It is not the only hard entry switch.",
        "directionSeparationRequired": True,
    }


def build_low_frequency_research_plan() -> LowFrequencyResearchPlan:
    return LowFrequencyResearchPlan(
        planId="low_frequency_mainstream_research_plan_v01",
        currentStatus="research_plan_only",
        scope={
            "pairs": PAIRS,
            "primaryTimeframes": PRIMARY_TIMEFRAMES,
            "optionalTimeframes": OPTIONAL_TIMEFRAMES,
            "excludedFromMainline": [
                "Top30 full-market expansion",
                "new listings",
                "low-liquidity altcoins",
                "high-frequency 15m and broad 1h signal loops",
            ],
        },
        principles=[
            "Lower frequency before complexity.",
            "Mainstream coins before broad universe expansion.",
            "No requirement to trade every day.",
            "Long and short research must be evaluated separately.",
            "Regime is a scoring context, not the only hard switch.",
            "Every hypothesis must compare against NoTrade and buy-hold baselines.",
            "Slippage-adjusted evaluation is required before promotion.",
        ],
        hypotheses=build_low_frequency_hypotheses(),
        longShortFramework=build_long_short_framework(),
        minimalConditionsPhilosophy={
            "maxCoreConditionsPerDirection": "4-6",
            "avoid": [
                "10+ gate stacks in first version",
                "small parameter rescue after structural failure",
                "forced trades in noisy regimes",
            ],
            "process": [
                "write a research specification first",
                "validate with real backtest later",
                "archive or downgrade failures instead of endless tuning",
            ],
        },
        benchmarkRequirements=[
            "NoTrade",
            "BuyHoldBTC",
            "BuyHoldETH",
            "BuyHoldSOL",
            "Simple 4h EMA Trend",
            "Simple 4h Bollinger Rebound",
            "Simple 4h Breakout Retest",
        ],
        evaluationMetrics=[
            "tradeCount",
            "tradesPerMonth",
            "totalReturnPct",
            "slippageAdjustedReturnPct",
            "profitFactor",
            "slippageAdjustedProfitFactor",
            "maxDrawdownPct",
            "winRate",
            "maxConsecutiveLosses",
            "averageHoldingHours",
            "exposureTimePct",
            "regimeBreakdown",
            "longShortBreakdown",
            "noTradeRatio",
            "benchmarkComparison",
        ],
        dataRequirements=[
            "BTC/ETH/SOL 4h OHLCV",
            "BTC/ETH/SOL 1d OHLCV",
            "BTC/ETH/SOL 1h OHLCV optional for entry refinement",
            "market regime labels",
            "NoTrade baseline",
            "BuyHoldBTC baseline",
            "BuyHoldETH baseline",
            "BuyHoldSOL baseline",
        ],
        optionalFutureData=[
            "fundingRate",
            "openInterest",
            "spread proxy",
            "orderbook depth",
        ],
        nextStepRecommendation="V13.4.32 - Low-Frequency Data Preparation and Baseline Builder",
        notes=[
            "This plan intentionally follows V13.4.30's failure review by reducing universe size and frequency.",
            "This is not strategy code and does not approve Dry-run or live trading.",
        ],
    )
