"""Schema constants for archived strategy failure attribution.

The analysis is deliberately report-only.  These values describe historical
research evidence and never grant execution eligibility.
"""

from __future__ import annotations

from typing import Final


REPORT_ID: Final = "archived_failed_strategy_failure_analysis_v1"

STATUS_ARCHIVES: Final = (
    "reports/v13_4_6_strategy_status_archive.json",
    "reports/v13_4_24_benchmark_status_archive.json",
    "reports/v13_4_30_short_strategy_status_archive.json",
)

NEUTRAL_BASELINE_IDS: Final = {
    "benchmark_no_trade",
    "benchmark_buy_hold_btc",
}

EVIDENCE_LEVELS: Final = {
    1: "raw_backtest_artifact",
    2: "structured_json_report",
    3: "markdown_summary",
    4: "code_or_prompt_only",
}

METRIC_FIELDS: Final = (
    "tradeCount",
    "totalReturnPct",
    "slippageAdjustedTotalReturnPct",
    "winRatePct",
    "profitFactor",
    "slippageAdjustedProfitFactor",
    "maxDrawdownPct",
    "maxConsecutiveLosses",
    "averageHoldingMinutes",
    "feesPaid",
    "slippageCost",
    "averageNetR",
    "grossRewardRiskR",
    "pairCount",
    "monthCount",
)

FAILURE_TYPES: Final = (
    "signal_edge_failure",
    "risk_model_failure",
    "cost_amplification",
    "overtrading",
    "direction_regime_mismatch",
    "pair_concentration",
    "time_regime_instability",
    "exit_design_failure",
    "data_evidence_gap",
    "runtime_engineering_failure",
    "rejected_risk_design",
)

SAFETY_BOUNDARY: Final = {
    "reportOnly": True,
    "strategyModified": False,
    "parameterTuned": False,
    "backtestExecuted": False,
    "exchangeApiCalled": False,
    "apiKeyReadOrStored": False,
    "accountRead": False,
    "positionRead": False,
    "orderCreated": False,
    "demoStateChanged": False,
    "liveStateChanged": False,
    "autoTradingUsed": False,
}
