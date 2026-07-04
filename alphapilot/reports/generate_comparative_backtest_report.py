"""Generate V13.4.4 comparative backtest report.

This reads local Freqtrade backtest artifacts only. It does not run Dry-run,
call exchange APIs, read real accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.reports.comparative_backtest_schema import (
    ComparativeBacktestReport,
    ComparativeCandidateResult,
)
from alphapilot.reports.export_backtest_report import _read_freqtrade_result_payload

DEFAULT_MANIFEST = Path("reports/v13_4_4_comparative_manifest.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_4_comparative_backtest_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_4_comparative_backtest_summary.md")
BASELINE_STRATEGY = "AlphaPilotVolumeReboundV01"

CANDIDATE_IDS = {
    "AlphaPilotVolumeReboundV02ATrendStrict": "alpha_volume_rebound_v02_a_trend_strict",
    "AlphaPilotVolumeReboundV02BVolumeQuality": "alpha_volume_rebound_v02_b_volume_quality",
    "AlphaPilotVolumeReboundV02CExitCleanup": "alpha_volume_rebound_v02_c_exit_cleanup",
    "AlphaPilotVolumeReboundV02DEarlyFailureExit": "alpha_volume_rebound_v02_d_early_failure_exit",
    "AlphaPilotVolumeReboundV02EPairRiskWatchlist": "alpha_volume_rebound_v02_e_pair_risk_watchlist",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _round(value: Any, digits: int = 4) -> float | None:
    try:
        if value is None:
            return None
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _pct_from_ratio(value: Any) -> float | None:
    number = _round(value, 8)
    if number is None:
        return None
    return _round(number * 100, 4) if -1 <= number <= 1 else _round(number, 4)


def _select_strategy_payload(payload: dict[str, Any], strategy: str) -> dict[str, Any]:
    strategies = payload.get("strategy")
    if isinstance(strategies, dict):
        if strategy in strategies and isinstance(strategies[strategy], dict):
            return strategies[strategy]
        for value in strategies.values():
            if isinstance(value, dict):
                return value
    return payload if isinstance(payload, dict) else {}


def _sum_fees_from_trades(trades: list[dict[str, Any]]) -> float | None:
    total = 0.0
    found = False
    for trade in trades:
        fee_open = trade.get("fee_open")
        fee_close = trade.get("fee_close")
        for order in trade.get("orders", []) or []:
            cost = order.get("cost")
            if cost is None:
                continue
            fee_rate = fee_open if order.get("ft_is_entry") else fee_close
            if fee_rate is None:
                continue
            total += float(cost) * float(fee_rate)
            found = True
    return _round(total, 8) if found else None


def _max_consecutive_losses(trades: list[dict[str, Any]]) -> int | None:
    if not trades:
        return None
    streak = 0
    max_streak = 0
    for trade in sorted(trades, key=lambda item: item.get("close_timestamp") or item.get("close_date") or ""):
        if (trade.get("profit_abs") or 0) < 0:
            streak += 1
            max_streak = max(max_streak, streak)
        else:
            streak = 0
    return max_streak


def _exit_loss(source: dict[str, Any], reason: str) -> float | None:
    for row in source.get("exit_reason_summary", []) or []:
        if row.get("key") == reason:
            return _round(row.get("profit_total_abs"), 8)
    return None


def _extract_pair_performance(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for row in source.get("results_per_pair", []) or []:
        if row.get("key") == "TOTAL":
            continue
        rows.append(
            {
                "pair": row.get("key"),
                "tradeCount": row.get("trades"),
                "totalProfit": _round(row.get("profit_total_abs"), 8),
                "totalReturnPct": _round(row.get("profit_total_pct"), 4),
                "profitFactor": _round(row.get("profit_factor"), 4),
                "winRate": _round((row.get("winrate") or 0) * 100, 4) if row.get("winrate") is not None else None,
                "maxDrawdownPct": _pct_from_ratio(row.get("max_drawdown_account")),
            }
        )
    return rows


def _extract_monthly_performance(source: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    periodic = source.get("periodic_breakdown")
    month_rows = periodic.get("month", []) if isinstance(periodic, dict) else []
    for row in month_rows:
        rows.append(row)
    return rows


def _metrics_from_result(path: Path, strategy: str) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    payload = _read_freqtrade_result_payload(path)
    source = _select_strategy_payload(payload, strategy) if isinstance(payload, dict) else {}
    trades = source.get("trades", []) if isinstance(source.get("trades"), list) else []
    total_return = _round(source.get("profit_total_pct"), 4)
    if total_return is None:
        total_return = _pct_from_ratio(source.get("profit_total"))
        warnings.append("profit_total_pct missing; normalized profit_total instead.")
    drawdown = _pct_from_ratio(source.get("max_drawdown_account"))
    fees = _sum_fees_from_trades(trades)
    if fees is None:
        warnings.append("feesPaid unavailable from trades/orders.")
    max_losses = source.get("max_consecutive_losses")
    if max_losses is None:
        max_losses = _max_consecutive_losses(trades)
        warnings.append("max_consecutive_losses missing; reconstructed from trades.")

    metrics = {
        "totalReturnPct": total_return,
        "maxDrawdownPct": drawdown,
        "profitFactor": _round(source.get("profit_factor"), 4),
        "tradeCount": source.get("total_trades"),
        "winRate": _round((source.get("winrate") or 0) * 100, 4) if source.get("winrate") is not None else None,
        "maxConsecutiveLosses": max_losses,
        "averageHoldingMinutes": _round((source.get("holding_avg_s") or 0) / 60, 4)
        if source.get("holding_avg_s") is not None
        else None,
        "feesPaid": fees,
        "netReturnAfterCosts": total_return,
        "pairPerformance": _extract_pair_performance(source),
        "monthlyPerformance": _extract_monthly_performance(source),
        "stopLossLoss": _exit_loss(source, "stop_loss"),
        "macdWeakExitLoss": _exit_loss(source, "macd_histogram_two_candle_weakness"),
        "slippageApplied": False,
        "sourceResult": str(path),
    }
    for key, value in metrics.items():
        if value is None and key not in {"macdWeakExitLoss"}:
            warnings.append(f"{key} unavailable.")
    return metrics, warnings


def _delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    fields = [
        "totalReturnPct",
        "maxDrawdownPct",
        "profitFactor",
        "tradeCount",
        "winRate",
        "maxConsecutiveLosses",
        "averageHoldingMinutes",
        "feesPaid",
        "netReturnAfterCosts",
        "stopLossLoss",
        "macdWeakExitLoss",
    ]
    result: dict[str, Any] = {}
    for field in fields:
        cand = candidate.get(field)
        base = baseline.get(field)
        result[field] = _round(cand - base, 4) if isinstance(cand, (int, float)) and isinstance(base, (int, float)) else None
    return result


def _passes_gate(candidate: dict[str, Any], baseline: dict[str, Any]) -> bool:
    if not candidate.get("tradeCount") or candidate.get("tradeCount", 0) < 20:
        return False
    checks = [
        candidate.get("profitFactor") is not None
        and baseline.get("profitFactor") is not None
        and candidate["profitFactor"] > baseline["profitFactor"],
        candidate.get("maxDrawdownPct") is not None
        and baseline.get("maxDrawdownPct") is not None
        and candidate["maxDrawdownPct"] < baseline["maxDrawdownPct"],
        candidate.get("maxConsecutiveLosses") is not None
        and baseline.get("maxConsecutiveLosses") is not None
        and candidate["maxConsecutiveLosses"] <= baseline["maxConsecutiveLosses"],
        candidate.get("totalReturnPct") is not None
        and baseline.get("totalReturnPct") is not None
        and candidate["totalReturnPct"] > baseline["totalReturnPct"],
    ]
    return all(checks)


def _comparison_row(strategy: str, metrics: dict[str, Any], passed: bool) -> dict[str, Any]:
    return {
        "strategy": strategy,
        "totalReturnPct": metrics.get("totalReturnPct"),
        "maxDrawdownPct": metrics.get("maxDrawdownPct"),
        "profitFactor": metrics.get("profitFactor"),
        "tradeCount": metrics.get("tradeCount"),
        "winRate": metrics.get("winRate"),
        "maxConsecutiveLosses": metrics.get("maxConsecutiveLosses"),
        "feesPaid": metrics.get("feesPaid"),
        "stopLossLoss": metrics.get("stopLossLoss"),
        "macdWeakExitLoss": metrics.get("macdWeakExitLoss"),
        "passedComparisonGate": passed,
    }


def build_report(manifest_path: Path) -> ComparativeBacktestReport:
    manifest = _read_json(manifest_path)
    manifest_entries = {entry.get("strategy"): entry for entry in manifest.get("strategies", [])}
    baseline_entry = manifest_entries.get(BASELINE_STRATEGY, {})
    warnings: list[str] = []

    if not baseline_entry.get("succeeded"):
        warnings.append("Baseline backtest missing or failed.")
        baseline_metrics: dict[str, Any] = {}
    else:
        baseline_metrics, baseline_warnings = _metrics_from_result(Path(baseline_entry["stableResult"]), BASELINE_STRATEGY)
        warnings.extend(f"{BASELINE_STRATEGY}: {warning}" for warning in baseline_warnings)

    candidate_results: list[ComparativeCandidateResult] = []
    comparison_table = [_comparison_row(BASELINE_STRATEGY, baseline_metrics, False)] if baseline_metrics else []
    for strategy, candidate_id in CANDIDATE_IDS.items():
        entry = manifest_entries.get(strategy, {})
        if not entry.get("succeeded"):
            error = entry.get("error") or "Backtest result unavailable."
            candidate_results.append(
                ComparativeCandidateResult(
                    strategy=strategy,
                    candidateId=candidate_id,
                    isExecutable=False,
                    backtestReport=entry.get("stableResult"),
                    metrics={},
                    deltaVsBaseline={},
                    passedComparisonGate=False,
                    warnings=[error],
                )
            )
            warnings.append(f"{strategy}: {error}")
            continue

        metrics, metric_warnings = _metrics_from_result(Path(entry["stableResult"]), strategy)
        delta = _delta(metrics, baseline_metrics)
        passed = _passes_gate(metrics, baseline_metrics)
        candidate_results.append(
            ComparativeCandidateResult(
                strategy=strategy,
                candidateId=candidate_id,
                isExecutable=True,
                backtestReport=entry["stableResult"],
                metrics=metrics,
                deltaVsBaseline=delta,
                passedComparisonGate=passed,
                warnings=metric_warnings,
            )
        )
        warnings.extend(f"{strategy}: {warning}" for warning in metric_warnings)
        comparison_table.append(_comparison_row(strategy, metrics, passed))

    ranking = sorted(
        [
            {
                "strategy": row["strategy"],
                "passedComparisonGate": row["passedComparisonGate"],
                "profitFactor": row["profitFactor"],
                "maxDrawdownPct": row["maxDrawdownPct"],
                "totalReturnPct": row["totalReturnPct"],
                "tradeCount": row["tradeCount"],
            }
            for row in comparison_table
            if row["strategy"] != BASELINE_STRATEGY
        ],
        key=lambda row: (
            bool(row["passedComparisonGate"]),
            row["profitFactor"] if row["profitFactor"] is not None else -999,
            row["totalReturnPct"] if row["totalReturnPct"] is not None else -999,
            -(row["maxDrawdownPct"] if row["maxDrawdownPct"] is not None else 999),
        ),
        reverse=True,
    )
    best = next((row["strategy"] for row in ranking if row["passedComparisonGate"]), None)
    reasons = [
        "V13.4.4 is comparative backtesting only.",
        "Dry-run remains blocked until longer-range and broader-pair validation exists.",
        "Slippage is not applied by the Freqtrade command; results are not live-performance estimates.",
    ]
    if best:
        reasons.append(f"{best} passed the first comparison gate but still requires more validation.")
    else:
        reasons.append("No candidate passed the full comparison gate.")

    return ComparativeBacktestReport(
        reportId="v13_4_4_comparative_backtest",
        timerange=str(manifest.get("timerange", "unavailable")),
        pairs=list(manifest.get("pairs", [])),
        baselineStrategy=BASELINE_STRATEGY,
        baselineMetrics=baseline_metrics,
        candidateResults=candidate_results,
        comparisonTable=comparison_table,
        ranking=ranking,
        bestCandidate=best,
        dryRunApproved=False,
        reasons=reasons,
        warnings=warnings,
        slippageApplied=False,
        nextStepRecommendation=(
            "If no candidate passes, redesign V0.2. If one improves materially, run longer timeranges "
            "and more pairs before any Dry-run discussion."
        ),
        generatedAt=_utc_now(),
    )


def _write_summary(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# V13.4.4 Comparative Backtest Summary",
        "",
        "## Decision",
        "",
        f"- Dry-run approved: {report['dryRunApproved']}",
        f"- Best candidate: {report['bestCandidate']}",
        f"- Slippage applied: {report['slippageApplied']}",
        "",
        "## Comparison Table",
        "",
        "| Strategy | Return % | Drawdown % | Profit Factor | Trades | Win Rate % | Max Loss Streak | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in report["comparisonTable"]:
        lines.append(
            f"| {row['strategy']} | {row.get('totalReturnPct')} | {row.get('maxDrawdownPct')} | "
            f"{row.get('profitFactor')} | {row.get('tradeCount')} | {row.get('winRate')} | "
            f"{row.get('maxConsecutiveLosses')} | {row.get('passedComparisonGate')} |"
        )
    lines.extend(["", "## Candidate Details", ""])
    for result in report["candidateResults"]:
        metrics = result["metrics"]
        lines.extend(
            [
                f"### {result['strategy']}",
                "",
                f"- Candidate ID: {result['candidateId']}",
                f"- Executable: {result['isExecutable']}",
                f"- Backtest report: {result['backtestReport']}",
                f"- Passed comparison gate: {result['passedComparisonGate']}",
                f"- Total return: {metrics.get('totalReturnPct')}",
                f"- Max drawdown: {metrics.get('maxDrawdownPct')}",
                f"- Profit factor: {metrics.get('profitFactor')}",
                f"- Trade count: {metrics.get('tradeCount')}",
                f"- Stop-loss loss: {metrics.get('stopLossLoss')}",
                f"- MACD weakness exit loss: {metrics.get('macdWeakExitLoss')}",
                "",
            ]
        )
    lines.extend(["## Reasons", ""])
    lines.extend(f"- {item}" for item in report["reasons"])
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in report["warnings"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "V13.4.4 runs local Freqtrade backtesting only. It does not enter Dry-run, approve live trading, use API keys, call Trade API or Withdraw API, read accounts, create orders, or auto trade.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_report(manifest: Path, output_json: Path, output_summary: Path) -> tuple[Path, Path]:
    report = build_report(manifest).to_dict()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(report, output_summary)
    return output_json, output_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.4 comparative backtest report.")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    args = parser.parse_args()

    output_json, output_summary = export_report(args.manifest, args.output_json, args.output_summary)
    print(f"Exported comparative report: {output_json}")
    print(f"Exported comparative summary: {output_summary}")


if __name__ == "__main__":
    main()
