"""Export AlphaPilot standard backtest reports.

If a Freqtrade backtest JSON exists, this module converts the available fields
into the AlphaPilot report schema. If no real result exists, it exports a sample
report with isMock=true so nobody confuses the artifact with a completed
backtest.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.reports.backtest_report_schema import AlphaPilotBacktestReport, BacktestMetrics
from alphapilot.universe.top30_usdt_swap import get_top30_usdt_swap_pairs

DEFAULT_RESULT_DIR = Path("user_data/backtest_results")
DEFAULT_SAMPLE_OUTPUT = Path("reports/sample_backtest_report.json")
DEFAULT_LATEST_OUTPUT = Path("reports/latest_backtest_report.json")
DEFAULT_SMOKE_OUTPUT = Path("reports/smoke_backtest_report.json")

SKIP_REASONS = [
    "btc_crash_filter",
    "weak_4h_trend",
    "rsi_out_of_range",
    "volume_ratio_too_low",
    "macd_not_improving",
    "price_too_extended",
    "data_missing",
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any] | list[Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _to_float(value: Any, default: float | None = 0.0) -> float | None:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int | None = 0) -> int | None:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _pick_number(source: dict[str, Any], names: list[str], default: float | None = 0.0) -> float | None:
    for name in names:
        if name in source:
            return _to_float(source.get(name), default)
    return default


def _select_strategy_payload(payload: dict[str, Any] | list[Any]) -> dict[str, Any]:
    if isinstance(payload, list):
        return payload[0] if payload and isinstance(payload[0], dict) else {}

    strategy = payload.get("strategy")
    if isinstance(strategy, dict):
        if "AlphaPilotVolumeReboundV01" in strategy and isinstance(strategy["AlphaPilotVolumeReboundV01"], dict):
            return strategy["AlphaPilotVolumeReboundV01"]
        for value in strategy.values():
            if isinstance(value, dict):
                return value
    return payload


def _normalize_pct(value: float | None, source_name: str) -> float | None:
    if value is None:
        return None
    if source_name.endswith("_pct"):
        return value
    if -1.0 <= value <= 1.0:
        return value * 100
    return value


def _build_metrics(source: dict[str, Any]) -> BacktestMetrics:
    total_return_source = "profit_total_pct" if "profit_total_pct" in source else "profit_total"
    total_return = _normalize_pct(_to_float(source.get(total_return_source), None), total_return_source)
    drawdown_source = "max_drawdown_account_pct" if "max_drawdown_account_pct" in source else "max_drawdown"
    raw_drawdown = _normalize_pct(_to_float(source.get(drawdown_source), None), drawdown_source)
    max_drawdown = abs(raw_drawdown) if raw_drawdown is not None else None

    trade_count = _to_int(source.get("total_trades", source.get("trade_count")), None)
    win_count = _to_int(source.get("wins", source.get("winning_trades")), None)
    if trade_count and win_count is not None:
        win_rate = win_count / trade_count * 100
    else:
        win_rate = _to_float(source.get("winrate"), None)

    fees_paid = _pick_number(source, ["total_fee", "fees_paid", "feesPaid"], None)
    holding_seconds = _pick_number(source, ["holding_avg_s", "averageHoldingSeconds"], None)
    return BacktestMetrics(
        totalReturnPct=round(total_return, 4) if total_return is not None else None,
        maxDrawdownPct=round(max_drawdown, 4) if max_drawdown is not None else None,
        winRate=round(win_rate, 4) if win_rate is not None else None,
        profitFactor=(
            round(profit_factor, 4)
            if (profit_factor := _pick_number(source, ["profit_factor", "profitFactor"], None)) is not None
            else None
        ),
        tradeCount=trade_count,
        maxConsecutiveLosses=_to_int(source.get("max_consecutive_losses"), None),
        averageHoldingMinutes=round(holding_seconds / 60, 4) if holding_seconds is not None else None,
        feesPaid=round(fees_paid, 8) if fees_paid is not None else None,
        slippageCost=None,
        netReturnAfterCosts=round(total_return, 4) if total_return is not None else None,
    )


def _build_report_warnings(source: dict[str, Any]) -> list[str]:
    warnings: list[str] = [
        "Slippage is recorded as a planned model but is not applied by the Freqtrade command yet.",
    ]
    if "total_trades" not in source and "trade_count" not in source:
        warnings.append("Trade count was not found in the Freqtrade result payload.")
    if not any(key in source for key in ("profit_total_pct", "profit_total")):
        warnings.append("Total return was not found in the Freqtrade result payload.")
    if not any(key in source for key in ("max_drawdown_account_pct", "max_drawdown")):
        warnings.append("Max drawdown was not found in the Freqtrade result payload.")
    return warnings


def _find_latest_freqtrade_result() -> Path | None:
    if not DEFAULT_RESULT_DIR.exists():
        return None
    candidates = [
        path
        for path in DEFAULT_RESULT_DIR.glob("*.json")
        if path.is_file() and not path.name.lower().endswith(".meta.json")
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_mtime)


def build_sample_report() -> AlphaPilotBacktestReport:
    return AlphaPilotBacktestReport(
        strategyId="alpha_volume_rebound_v01",
        strategyVersion="0.1-v13.3",
        market="OKX USDT swap",
        timeframe="15m",
        universe=get_top30_usdt_swap_pairs(),
        timerange="mock_20240101-20240701",
        config={
            "source": "v13_4_mock_report",
            "dryRunOnly": True,
            "feeRateOneWay": 0.0005,
            "slippageRateOneWay": 0.0005,
            "slippageModel": "planned, not yet applied by engine",
        },
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
        skippedSignals=[
            {"skipReason": reason, "count": 0, "source": "schema_placeholder"} for reason in SKIP_REASONS
        ],
        riskGateSummary={
            "status": "research_schema_ready",
            "liveExecutionAllowed": False,
            "skipReasonsTracked": SKIP_REASONS,
        },
        auditSummary={"status": "sample", "ledger": "reports/audit_ledger.jsonl"},
        reportWarnings=[
            "No real Freqtrade result JSON was found. This is a mock schema sample.",
            "Slippage is recorded as a planned model but is not applied by the Freqtrade command yet.",
        ],
        generatedAt=_utc_now(),
        isMock=True,
        source="alphapilot_report_exporter_v13_4_mock",
    )


def build_report_from_freqtrade_result(path: Path) -> AlphaPilotBacktestReport:
    payload = _read_json(path)
    source = _select_strategy_payload(payload)

    pair_performance = source.get("results_per_pair", [])
    if not isinstance(pair_performance, list):
        pair_performance = []

    monthly_performance = source.get("monthly_breakdown", source.get("results_per_month", []))
    if not isinstance(monthly_performance, list):
        monthly_performance = []

    trades = source.get("trades", [])
    if not isinstance(trades, list):
        trades = []

    timerange = str(source.get("timerange", source.get("backtest_start", "unknown")))
    if source.get("backtest_end") and timerange != "unknown":
        timerange = f"{timerange}-{source.get('backtest_end')}"

    return AlphaPilotBacktestReport(
        strategyId="alpha_volume_rebound_v01",
        strategyVersion="0.1-v13.3",
        market="OKX USDT swap",
        timeframe="15m",
        universe=get_top30_usdt_swap_pairs(),
        timerange=timerange,
        config={
            "sourceResult": str(path),
            "feeRateOneWay": 0.0005,
            "slippageRateOneWay": 0.0005,
            "slippageModel": "planned, not yet applied by engine",
        },
        metrics=_build_metrics(source),
        pairPerformance=pair_performance,
        monthlyPerformance=monthly_performance,
        trades=trades[:500],
        skippedSignals=[
            {"skipReason": reason, "count": 0, "source": "strategy_column_or_future_risk_gate"}
            for reason in SKIP_REASONS
        ],
        riskGateSummary={
            "available": False,
            "reason": "skipped signal aggregation is not implemented in V13.4",
            "status": "backtest_result_converted",
            "liveExecutionAllowed": False,
            "skipReasonsTracked": SKIP_REASONS,
        },
        auditSummary={"status": "converted", "sourceResult": str(path)},
        reportWarnings=_build_report_warnings(source),
        generatedAt=_utc_now(),
        isMock=False,
        source="alphapilot_report_exporter_v13_4_freqtrade_conversion",
    )


def export_report(
    input_path: Path | None = None,
    output_path: Path | None = None,
) -> Path:
    result_path = input_path if input_path and input_path.exists() else _find_latest_freqtrade_result()
    if result_path:
        report = build_report_from_freqtrade_result(result_path)
        output = output_path or DEFAULT_LATEST_OUTPUT
        DEFAULT_SMOKE_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        DEFAULT_SMOKE_OUTPUT.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        report = build_sample_report()
        output = output_path or DEFAULT_SAMPLE_OUTPUT

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return output


if __name__ == "__main__":
    exported_path = export_report()
    print(f"Exported AlphaPilot backtest report: {exported_path}")
