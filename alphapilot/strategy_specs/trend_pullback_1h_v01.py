"""Spec-only definition for AlphaPilot Trend Pullback 1H V0.1.

This file is intentionally not a Freqtrade strategy. It contains a structured
research specification for V13.4.8 implementation planning only.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

TREND_PULLBACK_1H_V01_SPEC: dict[str, Any] = {
    "strategyId": "alpha_trend_pullback_1h_v01",
    "name": "AlphaPilot Trend Pullback 1H V0.1",
    "version": "v13.4.7-spec",
    "status": "spec_only",
    "selectedDirection": "V03A+D",
    "positioning": (
        "Long-only 1h trend pullback continuation research strategy. It looks for clearer bullish "
        "trend structure, controlled pullback location, and 1h strength confirmation."
    ),
    "notA": [
        "weak-trend bottom fishing",
        "15m high-frequency rebound strategy",
        "random volume chase",
        "unfiltered full-market scanner",
        "Dry-run-ready strategy",
        "live-trading strategy",
    ],
    "market": {
        "exchange": "okx",
        "marketType": "USDT swap",
        "universe": "fixed Top30 supported pairs",
        "direction": "long_only",
        "primaryTimeframe": "1h",
        "higherTimeframe": "4h",
        "btcFilterTimeframes": ["1h", "4h"],
        "dynamicUniverse": False,
    },
    "entryRules": {
        "allRequired": True,
        "filters": [
            {
                "id": "trend_4h_filter",
                "name": "4h Trend Filter",
                "timeframe": "4h",
                "candidateRules": [
                    "close_4h > ema200_4h",
                    "ema20_4h >= ema50_4h",
                    "ema20_4h_slope >= 0",
                ],
                "purpose": "Search pullback continuation only when the larger structure is not weak.",
            },
            {
                "id": "btc_market_safety_filter",
                "name": "BTC Market Safety Filter",
                "timeframe": "1h/4h",
                "candidateRules": [
                    "btc_1h_3_candle_change_pct > -1.5",
                    "btc_4h_close >= btc_4h_ema200",
                    "btc_1h_macd_hist is not worsening for multiple consecutive candles",
                ],
                "purpose": "Avoid altcoin continuation entries during BTC stress.",
            },
            {
                "id": "pullback_location_filter",
                "name": "1h Pullback Location",
                "timeframe": "1h",
                "candidateRules": [
                    "close_1h >= ema50_1h",
                    "close_1h <= ema20_1h * 1.015",
                    "close_1h >= ema20_1h * 0.985",
                ],
                "purpose": "Enter research sample only near a reasonable trend pullback area, not after extension.",
            },
            {
                "id": "reclaim_confirmation_filter",
                "name": "1h Reclaim / Confirmation",
                "timeframe": "1h",
                "candidateRules": [
                    "close_1h > ema20_1h",
                    "macd_hist_1h > macd_hist_1h.shift(1)",
                ],
                "purpose": "Require renewed strength instead of entering because price is merely lower.",
            },
            {
                "id": "volume_quality_filter",
                "name": "Volume Quality",
                "timeframe": "1h",
                "candidateRules": [
                    "volume_ratio_1h >= 1.2",
                ],
                "purpose": "Require moderate confirmation while avoiding overly strict 15m-style thresholds.",
                "futureVariants": ["volume_ratio_1h >= 1.3", "volume_ratio_1h >= 1.5"],
            },
            {
                "id": "no_chase_filter",
                "name": "No-Chase Filter",
                "timeframe": "1h",
                "candidateRules": [
                    "close_1h <= ema20_1h * 1.02",
                    "rsi14_1h <= 65",
                ],
                "purpose": "Avoid entering after the 1h move is already extended.",
            },
            {
                "id": "risk_quality_filter",
                "name": "Risk Quality Filter",
                "timeframe": "1h",
                "candidateRules": [
                    "atr_pct_1h is not extreme",
                    "current candle body is not overextended",
                    "upper wick is not excessive",
                ],
                "purpose": "Track implementation candidates for candle quality and ATR risk.",
                "implementationStatus": "optional_for_v13_4_8",
            },
        ],
    },
    "exitRules": {
        "defaultProfile": "ExitProfileA",
        "profiles": [
            {
                "id": "ExitProfileA",
                "status": "recommended_first_implementation",
                "stoploss": "-2.5%",
                "takeProfit": "+5%",
                "timeStop": "exit after 8 closed 1h candles if trade is not profitable",
                "momentumExit": "only evaluate momentum exit when trade is profitable",
                "reason": "Simple fixed profile with wider reward/risk than V0.1/V0.2 1:1 payoff.",
            },
            {
                "id": "ExitProfileB",
                "status": "candidate_later",
                "stoploss": "entry - 1.5 * ATR",
                "takeProfit": "2R",
                "timeStop": "exit after 8 closed 1h candles if trade is not profitable",
                "momentumExit": "only evaluate momentum exit when trade is profitable",
                "reason": "More adaptive risk model, but implementation and interpretation are more complex.",
            },
        ],
        "notDefault": [
            "-3% stoploss and +3% take-profit 1:1 payoff",
        ],
    },
    "riskRules": {
        "riskPerTradePct": 1.0,
        "leverage": "5x configurable research cap",
        "marginMode": "isolated",
        "positionSizingFormula": [
            "riskAmount = accountEquity * riskPerTradePct",
            "effectiveStopDistance = stopLossPct + feeRate * 2 + slippageRate * 2",
            "positionNotional = riskAmount / effectiveStopDistance",
            "requiredMargin = positionNotional / leverage",
        ],
        "pairLevelControls": [
            "daily signal cap per pair",
            "pair-level exposure cap",
            "pair risk watchlist in reports",
        ],
    },
    "qualityGate": {
        "dryRunApprovedByDefault": False,
        "minimumRequirements": [
            "slippage-adjusted total return > 0",
            "slippage-adjusted profit factor > 1.15",
            "strict target profit factor >= 1.2",
            "max drawdown materially below V0.1/V0.2 expanded validation",
            "max consecutive losses acceptable for the proposed risk model",
            "trade count sufficient but not excessive",
            "no single pair dominates profit or loss",
            "passes BTC/ETH/SOL smoke validation",
            "passes six-month Top30 validation",
            "preferably passes longer timerange validation",
        ],
        "failureRule": "If these gates are not met, the strategy must not enter Dry-run.",
    },
    "implementationPlan": {
        "targetVersion": "V13.4.8",
        "title": "Implement Trend Pullback 1H V03 Strategy and Smoke Backtest",
        "steps": [
            "Add user_data/strategies/AlphaPilotTrendPullback1HV01.py.",
            "Do not modify old VolumeRebound strategies.",
            "Implement 1h trend pullback entry logic from this spec.",
            "Implement ExitProfileA first.",
            "Run BTC/ETH/SOL smoke backtest.",
            "If smoke runs without runtime errors, run fixed Top30 six-month validation.",
            "Generate slippage-adjusted AlphaPilot report.",
            "Keep dryRunApproved=false unless quality gates are met in a later review.",
        ],
    },
    "safetyBoundary": {
        "realApiKey": False,
        "tradeApi": False,
        "withdrawApi": False,
        "accountReads": False,
        "positionReads": False,
        "realOrderCreation": False,
        "autoTrading": False,
        "dryRunApproved": False,
    },
}


def get_trend_pullback_1h_v01_spec() -> dict[str, Any]:
    """Return a defensive copy of the V13.4.7 spec-only strategy definition."""

    return deepcopy(TREND_PULLBACK_1H_V01_SPEC)

