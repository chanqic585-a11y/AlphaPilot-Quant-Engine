"""Export a mock AlphaPilot standard backtest report.

V13.2 does not convert real Freqtrade results yet. This module creates a stable
sample report so the future mobile app and API adapter can target a schema.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from alphapilot.reports.backtest_report_schema import AlphaPilotBacktestReport, BacktestMetrics
from alphapilot.universe.top30_usdt_swap import get_top30_usdt_swap_pairs


def build_sample_report() -> AlphaPilotBacktestReport:
    return AlphaPilotBacktestReport(
        strategyId="alpha_volume_rebound_v01",
        strategyVersion="0.1-skeleton",
        market="OKX USDT swap",
        timeframe="15m",
        universe=get_top30_usdt_swap_pairs(),
        timerange="mock_20240101-20240701",
        config={"source": "v13_2_mock_report", "dryRunOnly": True},
        metrics=BacktestMetrics(
            totalReturnPct=0.0,
            maxDrawdownPct=0.0,
            winRate=0.0,
            profitFactor=0.0,
            tradeCount=0,
            maxConsecutiveLosses=0,
            averageHoldingMinutes=0.0,
            feesPaid=0.0,
            slippageCost=0.0,
            netReturnAfterCosts=0.0,
        ),
        skippedSignals=[],
        riskGateSummary={"status": "skeleton", "liveExecutionAllowed": False},
        auditSummary={"status": "skeleton", "ledger": "reports/audit_ledger.jsonl"},
        generatedAt=datetime.now(timezone.utc).isoformat(),
    )


def export_sample_report(output_path: Path = Path("reports/sample_backtest_report.json")) -> Path:
    report = build_sample_report()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output_path


if __name__ == "__main__":
    path = export_sample_report()
    print(f"Exported AlphaPilot sample backtest report: {path}")
