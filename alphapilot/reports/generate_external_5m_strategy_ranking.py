"""Generate a ranking report for external 5m batch backtests.

This module only reads local Freqtrade backtest artifacts and local manifests.
It does not run backtests, start dry-run, call private exchange APIs, read
accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.reports.generate_low_frequency_directional_report import (
    _drawdown_pct,
    _max_consecutive_losses,
    _profit_factor_for_trades,
    _read_freqtrade_payload,
    _safe_float,
    _safe_int,
    _slippage_adjustment_for_trades,
    _trades,
    _win_rate_for_trades,
)


REPORT_ID = "external_5m_strategy_ranking"
VERSION = "V13.8 external 5m ranking"
DEFAULT_MANIFEST = Path("reports/external_5m_all_strategy_backtest_manifest.json")
DEFAULT_OUTPUT_JSON = Path("reports/external_5m_strategy_ranking.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/external_5m_strategy_ranking_summary.md")
DEFAULT_SLIPPAGE_RATE = 0.0005


STRATEGY_DISPLAY_NAMES = {
    "AlphaPilotBatchA_EMATrendLong4H": "4H EMA趋势做多",
    "AlphaPilotBatchB_EMATrendShort4H": "4H EMA趋势做空",
    "AlphaPilotBatchC_BreakoutRetestLong4H": "4H 突破回踩做多",
    "AlphaPilotBatchD_BreakdownRetestShort4H": "4H 跌破反抽做空",
    "AlphaPilotBatchE_BollingerReversionLong4H": "4H 布林均值回归做多",
    "AlphaPilotBatchF_BollingerReversionShort4H": "4H 布林均值回归做空",
    "AlphaPilotBatchG_RelativeStrengthLong4H": "4H 相对强度做多",
    "AlphaPilotBatchH_VolatilityCompressionBreakout4H": "4H 波动压缩突破",
    "AlphaPilotDynamicRegimeV01": "动态市场状态策略",
    "AlphaPilotLowFrequencyDirectional4HV01": "低频4H方向策略",
    "AlphaPilotShortRejection1HV01": "1H 空头拒绝策略",
    "AlphaPilotTrendPullback1HV01": "1H 趋势回调策略",
    "AlphaPilotVolumeReboundV01": "15m 放量反弹策略",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def select_strategy_payload(payload: dict[str, Any] | list[Any], strategy_class: str) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    strategies = payload.get("strategy")
    if not isinstance(strategies, dict):
        return None
    direct = strategies.get(strategy_class)
    if isinstance(direct, dict):
        return direct
    for value in strategies.values():
        if isinstance(value, dict) and value.get("strategy_name") == strategy_class:
            return value
    return None


def trade_profit_abs(trade: dict[str, Any]) -> float:
    return _safe_float(trade.get("profit_abs"), 0.0) or 0.0


def starting_balance(source: dict[str, Any]) -> float:
    return _safe_float(source.get("starting_balance"), 0.0) or 0.0


def total_return_pct(total_profit_abs: float, total_starting_balance: float) -> float | None:
    if total_starting_balance <= 0:
        return None
    return round(total_profit_abs / total_starting_balance * 100, 4)


def average_win_loss(trades: list[dict[str, Any]]) -> tuple[float | None, float | None, float | None]:
    wins = [trade_profit_abs(trade) for trade in trades if trade_profit_abs(trade) > 0]
    losses = [abs(trade_profit_abs(trade)) for trade in trades if trade_profit_abs(trade) < 0]
    average_win = round(sum(wins) / len(wins), 8) if wins else None
    average_loss = round(sum(losses) / len(losses), 8) if losses else None
    reward_risk = round(average_win / average_loss, 4) if average_win is not None and average_loss else None
    return average_win, average_loss, reward_risk


def pair_trade_rows(trades: list[dict[str, Any]], total_starting_balance: float) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        grouped[str(trade.get("pair") or "unknown")].append(trade)
    rows = []
    for pair, pair_trades in grouped.items():
        profit_abs = sum(trade_profit_abs(trade) for trade in pair_trades)
        rows.append(
            {
                "pair": pair,
                "tradeCount": len(pair_trades),
                "profitAbs": round(profit_abs, 8),
                "returnPctOfTotalCapital": total_return_pct(profit_abs, total_starting_balance),
                "winRate": _win_rate_for_trades(pair_trades),
                "profitFactor": _profit_factor_for_trades(pair_trades),
            }
        )
    return sorted(rows, key=lambda item: (_safe_float(item.get("profitAbs"), 0.0) or 0.0), reverse=True)


def month_coverage(trades: list[dict[str, Any]]) -> int:
    months = set()
    for trade in trades:
        timestamp = trade.get("close_timestamp") or trade.get("open_timestamp")
        if timestamp is None:
            continue
        try:
            months.add(datetime.fromtimestamp(int(timestamp) / 1000, tz=UTC).strftime("%Y-%m"))
        except (TypeError, ValueError, OSError):
            continue
    return len(months)


def pair_concentration(trades: list[dict[str, Any]]) -> float:
    if not trades:
        return 0.0
    counts = Counter(str(trade.get("pair") or "unknown") for trade in trades)
    return round(max(counts.values()) / len(trades), 4)


def score_strategy(metrics: dict[str, Any]) -> tuple[float, str, list[str]]:
    reasons: list[str] = []
    score = 0.0
    trade_count = _safe_int(metrics.get("tradeCount"), 0) or 0
    total_return = _safe_float(metrics.get("slippageAdjustedReturnPct"), None)
    raw_return = _safe_float(metrics.get("totalReturnPct"), None)
    drawdown = _safe_float(metrics.get("maxChunkDrawdownPct"), None)
    profit_factor = _safe_float(metrics.get("profitFactor"), None)
    slippage_pf = _safe_float(metrics.get("slippageAdjustedProfitFactor"), None)
    win_rate = _safe_float(metrics.get("winRate"), None)
    reward_risk = _safe_float(metrics.get("rewardRiskRatio"), None)
    concentration = _safe_float(metrics.get("pairTradeConcentration"), 1.0) or 1.0
    covered_pairs = _safe_int(metrics.get("coveredPairCount"), 0) or 0
    covered_months = _safe_int(metrics.get("coveredMonthCount"), 0) or 0

    if trade_count >= 100:
        score += 20
        reasons.append("样本数充足。")
    elif trade_count >= 40:
        score += 12
        reasons.append("样本数达到初筛要求。")
    else:
        reasons.append("样本数偏少。")

    if total_return is not None and total_return > 0:
        score += 15
        reasons.append("滑点后收益为正。")
    elif raw_return is not None and raw_return > 0:
        score += 6
        reasons.append("原始收益为正，但滑点后表现不足。")
    else:
        reasons.append("收益没有通过初筛。")

    if slippage_pf is not None and slippage_pf >= 1.15:
        score += 20
        reasons.append("滑点后 profit factor 较好。")
    elif slippage_pf is not None and slippage_pf >= 1.03:
        score += 12
        reasons.append("滑点后 profit factor 勉强可观察。")
    elif profit_factor is not None and profit_factor > 1:
        score += 5
        reasons.append("原始 profit factor 大于 1，但成本压力明显。")
    else:
        reasons.append("profit factor 不足。")

    if drawdown is not None and drawdown <= 20:
        score += 15
        reasons.append("最大 chunk 回撤可控。")
    elif drawdown is not None and drawdown <= 35:
        score += 8
        reasons.append("最大 chunk 回撤偏高但未淘汰。")
    else:
        reasons.append("回撤过高或不可用。")

    if win_rate is not None and win_rate >= 55:
        score += 10
        reasons.append("胜率达到 55% 观察线。")
    elif win_rate is not None and win_rate >= 45:
        score += 5
        reasons.append("胜率未达 55%，但仍可结合盈亏比观察。")
    else:
        reasons.append("胜率不足。")

    if reward_risk is not None and reward_risk >= 2:
        score += 10
        reasons.append("平均盈亏比达到 2R 目标。")
    elif reward_risk is not None and reward_risk >= 1.2:
        score += 5
        reasons.append("平均盈亏比未达 2R，但仍有观察价值。")
    else:
        reasons.append("平均盈亏比不足或不可用。")

    if covered_pairs >= 15 and concentration <= 0.35:
        score += 5
        reasons.append("币种覆盖较分散。")
    elif covered_pairs >= 5:
        score += 2
        reasons.append("币种覆盖有限。")
    else:
        reasons.append("币种覆盖不足。")

    if covered_months >= 12:
        score += 5
        reasons.append("跨月份覆盖较好。")
    elif covered_months >= 4:
        score += 2
        reasons.append("跨月份覆盖有限。")
    else:
        reasons.append("时间覆盖不足。")

    hard_fail = (
        trade_count < 20
        or total_return is None
        or total_return <= 0
        or slippage_pf is None
        or slippage_pf < 1
        or (drawdown is not None and drawdown > 50)
    )
    if not hard_fail and score >= 65:
        tier = "sandbox_candidate"
    elif not hard_fail and score >= 45:
        tier = "watchlist"
    else:
        tier = "reject"
    return round(score, 2), tier, reasons


def build_strategy_metrics(strategy_class: str, rows: list[dict[str, Any]], slippage_rate: float) -> dict[str, Any]:
    all_trades: list[dict[str, Any]] = []
    total_starting_balance = 0.0
    total_profit_abs = 0.0
    chunk_drawdowns: list[float] = []
    loaded_chunks = 0
    warnings: list[str] = []
    source_files = []
    for row in rows:
        result_path = row.get("resultZipPath")
        if not result_path or not Path(result_path).exists():
            warnings.append(f"Missing result zip for chunk {row.get('chunkIndex')}.")
            continue
        try:
            payload = _read_freqtrade_payload(Path(result_path))
            source = select_strategy_payload(payload, strategy_class)
        except Exception as exc:  # noqa: BLE001 - report parser should not stop on one bad zip.
            warnings.append(f"Failed to read {result_path}: {exc}")
            continue
        if not source:
            warnings.append(f"Strategy payload not found in {result_path}.")
            continue
        trades = _trades(source)
        all_trades.extend(trades)
        chunk_starting_balance = starting_balance(source)
        total_starting_balance += chunk_starting_balance
        total_profit_abs += sum(trade_profit_abs(trade) for trade in trades)
        drawdown = _drawdown_pct(source)
        if drawdown is not None:
            chunk_drawdowns.append(drawdown)
        loaded_chunks += 1
        source_files.append(result_path)

    slippage = _slippage_adjustment_for_trades(all_trades, total_starting_balance, slippage_rate)
    average_win, average_loss, reward_risk = average_win_loss(all_trades)
    pair_rows = pair_trade_rows(all_trades, total_starting_balance)
    metrics: dict[str, Any] = {
        "strategyClass": strategy_class,
        "strategyName": STRATEGY_DISPLAY_NAMES.get(strategy_class, strategy_class),
        "chunkCount": len(rows),
        "loadedChunkCount": loaded_chunks,
        "tradeCount": len(all_trades),
        "totalProfitAbs": round(total_profit_abs, 8),
        "totalStartingBalance": round(total_starting_balance, 8),
        "totalReturnPct": total_return_pct(total_profit_abs, total_starting_balance),
        "slippageRateOneWay": slippage_rate,
        "slippageCost": slippage.get("totalSlippageCost"),
        "slippageAdjustedReturnPct": slippage.get("totalReturnPct"),
        "profitFactor": _profit_factor_for_trades(all_trades),
        "slippageAdjustedProfitFactor": slippage.get("profitFactor"),
        "winRate": _win_rate_for_trades(all_trades),
        "averageWinAbs": average_win,
        "averageLossAbs": average_loss,
        "rewardRiskRatio": reward_risk,
        "maxConsecutiveLosses": _max_consecutive_losses({}, all_trades),
        "maxChunkDrawdownPct": round(max(chunk_drawdowns), 4) if chunk_drawdowns else None,
        "coveredPairCount": len({str(trade.get("pair") or "unknown") for trade in all_trades}),
        "coveredMonthCount": month_coverage(all_trades),
        "pairTradeConcentration": pair_concentration(all_trades),
        "topPairsByProfit": pair_rows[:10],
        "bottomPairsByProfit": sorted(pair_rows, key=lambda item: _safe_float(item.get("profitAbs"), 0.0) or 0.0)[:10],
        "sourceResultCount": len(source_files),
        "sourceResultsPreview": source_files[:5],
        "warnings": warnings,
    }
    score, tier, reasons = score_strategy(metrics)
    metrics["score"] = score
    metrics["tier"] = tier
    metrics["decisionReasons"] = reasons
    return metrics


def build_report(manifest_path: Path, slippage_rate: float) -> dict[str, Any]:
    manifest = read_json(manifest_path)
    results = [row for row in manifest.get("results", []) or [] if isinstance(row, dict)]
    strategy_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        strategy = str(row.get("strategyClass") or "unknown")
        strategy_rows[strategy].append(row)
    expected_chunks = None
    if results:
        expected_chunks = (manifest.get("selectedStrategyCount") or 0) * max(int(row.get("chunkCount") or 0) for row in results)
    completed_chunks = (
        int(manifest.get("successCount") or 0)
        + int(manifest.get("failedCount") or 0)
        + int(manifest.get("resultMissingCount") or 0)
    )
    report_status = "completed" if expected_chunks and completed_chunks >= expected_chunks else "partial_preliminary"
    strategy_metrics = [
        build_strategy_metrics(strategy, rows, slippage_rate)
        for strategy, rows in sorted(strategy_rows.items())
    ]
    ranked = sorted(strategy_metrics, key=lambda item: _safe_float(item.get("score"), 0.0) or 0.0, reverse=True)
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": report_status,
        "isPreliminary": report_status != "completed",
        "manifestPath": manifest_path.as_posix(),
        "timerange": manifest.get("timerange"),
        "dataDir": manifest.get("dataDir"),
        "pairCount": manifest.get("pairCount"),
        "selectedStrategyCount": manifest.get("selectedStrategyCount"),
        "expectedChunkCount": expected_chunks,
        "completedChunkCount": completed_chunks,
        "successCount": manifest.get("successCount"),
        "failedCount": manifest.get("failedCount"),
        "resultMissingCount": manifest.get("resultMissingCount"),
        "progressPct": round(completed_chunks / expected_chunks * 100, 4) if expected_chunks else None,
        "slippageRateOneWay": slippage_rate,
        "tierCounts": dict(Counter(item["tier"] for item in ranked)),
        "rankedStrategies": ranked,
        "sandboxCandidates": [item for item in ranked if item["tier"] == "sandbox_candidate"],
        "watchlist": [item for item in ranked if item["tier"] == "watchlist"],
        "rejected": [item for item in ranked if item["tier"] == "reject"],
        "safetyBoundary": {
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyStored": False,
            "accountRead": False,
            "positionRead": False,
            "orderCreated": False,
            "autoTradingUsed": False,
        },
        "warnings": [
            "This report is preliminary until the external 5m batch manifest reaches 100% completion."
        ]
        if report_status != "completed"
        else [],
        "generatedAt": utc_now(),
    }


def format_value(value: Any, suffix: str = "") -> str:
    if value is None:
        return "--"
    if isinstance(value, float):
        return f"{value:.4f}{suffix}"
    return f"{value}{suffix}"


def build_summary(report: dict[str, Any]) -> str:
    lines = [
        "# External 5m Strategy Ranking",
        "",
        f"- Status: `{report['status']}`",
        f"- Timerange: `{report.get('timerange')}`",
        f"- Progress: `{report.get('completedChunkCount')}/{report.get('expectedChunkCount')}` ({format_value(report.get('progressPct'), '%')})",
        f"- Pair count: `{report.get('pairCount')}`",
        f"- Strategy count: `{report.get('selectedStrategyCount')}`",
        f"- Slippage model: `{report.get('slippageRateOneWay')}` one-way extra stress",
        "",
        "Safety boundary: local research report only. No Dry-run, no live trading, no private API, no account read, no order creation.",
        "",
        "## Tier Counts",
        "",
    ]
    for tier, count in sorted((report.get("tierCounts") or {}).items()):
        lines.append(f"- {tier}: `{count}`")
    lines.extend(["", "## Top Strategies", ""])
    header = "| Rank | Tier | Strategy | Score | Trades | Slip Return | Slip PF | Win Rate | R/R | Max DD | Pairs |"
    lines.append(header)
    lines.append("|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|")
    for index, item in enumerate(report.get("rankedStrategies", [])[:15], start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    str(item.get("tier")),
                    str(item.get("strategyName")),
                    format_value(item.get("score")),
                    str(item.get("tradeCount")),
                    format_value(item.get("slippageAdjustedReturnPct"), "%"),
                    format_value(item.get("slippageAdjustedProfitFactor")),
                    format_value(item.get("winRate"), "%"),
                    format_value(item.get("rewardRiskRatio")),
                    format_value(item.get("maxChunkDrawdownPct"), "%"),
                    str(item.get("coveredPairCount")),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Sandbox Candidates", ""])
    candidates = report.get("sandboxCandidates") or []
    if not candidates:
        lines.append("- None yet. Wait for the full batch to complete or review watchlist items.")
    for item in candidates:
        lines.append(f"- **{item.get('strategyName')}** (`{item.get('strategyClass')}`): score `{item.get('score')}`")
        for reason in item.get("decisionReasons", [])[:5]:
            lines.append(f"  - {reason}")
    lines.extend(["", "## Watchlist", ""])
    watchlist = report.get("watchlist") or []
    if not watchlist:
        lines.append("- None.")
    for item in watchlist[:10]:
        lines.append(f"- {item.get('strategyName')}: score `{item.get('score')}`, trades `{item.get('tradeCount')}`")
    if report.get("warnings"):
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {warning}" for warning in report["warnings"])
    lines.append("")
    return "\n".join(lines)


def export_report(manifest: Path, output_json: Path, output_summary: Path, slippage_rate: float) -> tuple[Path, Path]:
    report = build_report(manifest, slippage_rate)
    write_json(output_json, report)
    write_text(output_summary, build_summary(report))
    return output_json, output_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate external 5m strategy ranking report.")
    parser.add_argument("--manifest", default=DEFAULT_MANIFEST.as_posix())
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON.as_posix())
    parser.add_argument("--output-summary", default=DEFAULT_OUTPUT_SUMMARY.as_posix())
    parser.add_argument("--slippage-rate", type=float, default=DEFAULT_SLIPPAGE_RATE)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_json, output_summary = export_report(
        manifest=Path(args.manifest),
        output_json=Path(args.output_json),
        output_summary=Path(args.output_summary),
        slippage_rate=args.slippage_rate,
    )
    print(f"Wrote {output_json}")
    print(f"Wrote {output_summary}")


if __name__ == "__main__":
    main()
