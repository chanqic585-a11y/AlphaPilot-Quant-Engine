"""Contracts for the report-only full archived strategy evidence analysis."""

from __future__ import annotations

from pathlib import Path
from typing import Final


REPORT_ID: Final = "full_archived_strategy_evidence_analysis_v2"

OUTPUTS: Final = {
    "inventoryJson": Path("reports/full_archived_strategy_inventory.json"),
    "inventoryCsv": Path("reports/full_archived_strategy_inventory.csv"),
    "coverageAudit": Path("reports/full_archived_strategy_coverage_audit.json"),
    "evidenceIndex": Path("reports/full_archived_strategy_evidence_index.json"),
    "evidenceGaps": Path("reports/full_archived_strategy_evidence_gaps.json"),
    "metricsJson": Path("reports/full_archived_strategy_metrics_matrix.json"),
    "metricsCsv": Path("reports/full_archived_strategy_metrics_matrix.csv"),
    "tradeLevelJsonl": Path("reports/full_archived_strategy_trade_level_metrics.jsonl"),
    "tradeSampleCsv": Path("reports/full_archived_strategy_trade_level_sample.csv"),
    "signalFunnel": Path("reports/full_archived_strategy_signal_funnel_matrix.json"),
    "attributionJson": Path("reports/full_archived_strategy_failure_attribution.json"),
    "failureCsv": Path("reports/full_archived_strategy_failure_matrix.csv"),
    "patterns": Path("reports/full_archived_strategy_cross_strategy_patterns.json"),
    "negativeRules": Path("reports/full_archived_strategy_negative_rules.json"),
    "reusableComponents": Path("reports/full_archived_strategy_reusable_components.json"),
    "revivalCandidates": Path("reports/full_archived_strategy_revival_candidates.json"),
    "continueArchive": Path("reports/full_archived_strategy_continue_archive.json"),
    "prohibitedRoutes": Path("reports/full_archived_strategy_prohibited_routes.json"),
    "summary": Path("reports/full_archived_strategy_analysis_summary.md"),
}

FULL_TRADE_OUTPUT: Final = Path(
    "reports/generated/full_archived_strategy_trade_level_metrics.jsonl"
)
STRATEGY_DOCS_DIR: Final = Path("docs/archived-strategies")

EVIDENCE_LEVELS: Final = {
    1: "真实 Freqtrade ZIP/JSON，可提取逐笔交易",
    2: "由真实研究流程生成的结构化 JSON/SQLite 证据",
    3: "Markdown、README 或人工生命周期摘要",
    4: "仅代码、提示词、注释、样例或 Mock",
}

CORE_METRIC_FIELDS: Final = (
    "tradeCount",
    "profitFactor",
    "averageNetR",
    "maximumDrawdownR",
    "winRatePct",
    "totalReturnPct",
    "feesPaid",
    "fundingFees",
    "slippageCost",
)

FAILURE_LABELS_ZH: Final = {
    "signal_edge_failure": "信号边际为负",
    "risk_model_failure": "账户风险路径不合格",
    "cost_amplification": "成本放大后失效",
    "overtrading": "过度交易与噪声放大",
    "direction_regime_mismatch": "方向与市场状态不匹配",
    "pair_concentration": "币种贡献过度集中",
    "time_regime_instability": "时间分段表现不稳定",
    "exit_design_failure": "退出设计失效",
    "zero_trade_or_blocked": "零交易或流程阻塞",
    "small_sample": "样本不足",
    "data_evidence_gap": "证据不完整",
    "runtime_engineering_failure": "运行或工程故障",
    "rejected_risk_design": "风险设计被禁止",
}

SAFETY_BOUNDARY: Final = {
    "reportOnly": True,
    "strategyModified": False,
    "parameterTuned": False,
    "backtestExecuted": False,
    "marketDataDownloaded": False,
    "exchangeApiCalled": False,
    "apiKeyReadOrStored": False,
    "accountRead": False,
    "positionRead": False,
    "orderCreated": False,
    "demoStateChanged": False,
    "liveStateChanged": False,
    "autoTradingUsed": False,
}

STRATEGY_CORE_PRINCIPLES: Final = (
    "先写市场假设，再选择指标。",
    "每条策略只保留一个核心形态，其他指标只能确认、过滤或否决。",
    "数据完整性和可追溯性先于绩效判断。",
    "高周期定义环境，低周期负责触发；市场状态是上下文，不是脆弱的单一开关。",
    "组合风险按相关性、Beta 和同向暴露管理，不能只数持仓数量。",
    "风险统一用 R 表达；杠杆不能改变最大允许亏损。",
    "初始净目标原则上不低于 2R；达到目标后可保留趋势尾仓，但不能放宽初始止损。",
    "自适应参数必须有边界、版本和可复现证据。",
    "机器学习只做元标签、排序或否决，不直接凭黑箱生成买卖信号。",
    "使用时间隔离的 Walk-forward、锁定样本、成本压力与跨币种验证。",
    "多重试验必须记录，防止选择偏差、PBO 和虚高 Sharpe。",
    "回测必须计入手续费、资金费、滑点、延迟、部分成交和容量约束。",
    "失败结果必须保留；达到尝试上限仍不合格时停止，不强制放行。",
    "策略从回测到前向、Demo、实盘必须使用不可变 Release。",
)
