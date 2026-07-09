"""Diagnose external 5m batch ranking results.

This report only reads local ranking artifacts generated from local Freqtrade
backtests. It does not start dry-run, connect to private endpoints, read
accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


REPORT_ID = "external_5m_failure_diagnosis"
VERSION = "V13.8 external 5m failure diagnosis"
DEFAULT_RANKING = Path("reports/external_5m_strategy_ranking.json")
DEFAULT_OUTPUT_JSON = Path("reports/external_5m_failure_diagnosis.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/external_5m_failure_diagnosis_summary.md")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def safe_float(value: Any, fallback: float | None = 0.0) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return fallback
    return parsed if parsed == parsed else fallback


def safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def add_failure_flags(row: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    trade_count = safe_int(row.get("tradeCount"))
    slip_return = safe_float(row.get("slippageAdjustedReturnPct"), None)
    slip_pf = safe_float(row.get("slippageAdjustedProfitFactor"), None)
    raw_pf = safe_float(row.get("profitFactor"), None)
    max_dd = safe_float(row.get("maxChunkDrawdownPct"), None)
    win_rate = safe_float(row.get("winRate"), None)
    reward_risk = safe_float(row.get("rewardRiskRatio"), None)

    if trade_count < 100:
        flags.append("sample_too_small")
    if slip_return is None or slip_return <= 0:
        flags.append("negative_slippage_adjusted_return")
    if slip_pf is None or slip_pf < 1:
        flags.append("slippage_adjusted_pf_below_1")
    if raw_pf is None or raw_pf < 1:
        flags.append("raw_pf_below_1")
    if max_dd is None or max_dd > 50:
        flags.append("drawdown_above_50pct")
    if win_rate is None or win_rate < 45:
        flags.append("win_rate_below_45pct")
    elif win_rate < 55:
        flags.append("win_rate_below_55pct")
    if reward_risk is None or reward_risk < 2:
        flags.append("reward_risk_below_2")
    return flags


def build_raw_pockets(ranked: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pockets: list[dict[str, Any]] = []
    for row in ranked:
        for pair_row in row.get("topPairsByProfit") or []:
            trade_count = safe_int(pair_row.get("tradeCount"))
            profit_abs = safe_float(pair_row.get("profitAbs"), 0.0) or 0.0
            profit_factor = safe_float(pair_row.get("profitFactor"), 0.0) or 0.0
            win_rate = safe_float(pair_row.get("winRate"), 0.0) or 0.0
            return_pct = safe_float(pair_row.get("returnPctOfTotalCapital"), 0.0) or 0.0
            if trade_count < 100 or profit_abs <= 0 or profit_factor < 1.03:
                continue
            pocket_score = 0.0
            pocket_score += min(trade_count / 500, 1.0) * 25
            pocket_score += min(max(profit_factor - 1.0, 0.0) / 0.35, 1.0) * 30
            pocket_score += min(max(win_rate - 25.0, 0.0) / 30.0, 1.0) * 20
            pocket_score += min(max(return_pct, 0.0) / 5.0, 1.0) * 25
            if profit_factor >= 1.12 and return_pct >= 1.0 and trade_count >= 300:
                tier = "raw_pocket_retest_candidate"
            else:
                tier = "raw_pocket_reference_only"
            pockets.append(
                {
                    "strategyClass": row.get("strategyClass"),
                    "strategyName": row.get("strategyName"),
                    "pair": pair_row.get("pair"),
                    "tier": tier,
                    "pocketScore": round(pocket_score, 2),
                    "tradeCount": trade_count,
                    "rawProfitAbs": round(profit_abs, 8),
                    "rawReturnPctOfTotalCapital": round(return_pct, 4),
                    "rawProfitFactor": round(profit_factor, 4),
                    "rawWinRate": round(win_rate, 4),
                    "warning": "Raw pair pocket only. It must be retested with pair-specific slippage, fees, cooldown, and regime filters before any sandbox promotion.",
                }
            )
    return sorted(
        pockets,
        key=lambda item: (
            item["tier"] != "raw_pocket_retest_candidate",
            -float(item["pocketScore"]),
            -float(item["rawReturnPctOfTotalCapital"]),
        ),
    )


def build_report(ranking_path: Path) -> dict[str, Any]:
    ranking = read_json(ranking_path)
    ranked = [row for row in ranking.get("rankedStrategies") or [] if isinstance(row, dict)]
    flag_counts: Counter[str] = Counter()
    diagnosed_rows = []
    for row in ranked:
        flags = add_failure_flags(row)
        flag_counts.update(flags)
        diagnosed_rows.append(
            {
                "strategyClass": row.get("strategyClass"),
                "strategyName": row.get("strategyName"),
                "tier": row.get("tier"),
                "score": row.get("score"),
                "tradeCount": row.get("tradeCount"),
                "slippageAdjustedReturnPct": row.get("slippageAdjustedReturnPct"),
                "slippageAdjustedProfitFactor": row.get("slippageAdjustedProfitFactor"),
                "winRate": row.get("winRate"),
                "rewardRiskRatio": row.get("rewardRiskRatio"),
                "maxChunkDrawdownPct": row.get("maxChunkDrawdownPct"),
                "failureFlags": flags,
            }
        )
    pockets = build_raw_pockets(ranked)
    pocket_tier_counts = Counter(item["tier"] for item in pockets)
    all_rejected = bool(ranked) and all(row.get("tier") == "reject" for row in ranked)
    return {
        "reportId": REPORT_ID,
        "version": VERSION,
        "status": "completed",
        "rankingPath": ranking_path.as_posix(),
        "sourceRankingStatus": ranking.get("status"),
        "sourceProgressPct": ranking.get("progressPct"),
        "strategyCount": len(ranked),
        "allStrategiesRejected": all_rejected,
        "failureFlagCounts": dict(flag_counts),
        "rawPocketCount": len(pockets),
        "rawPocketTierCounts": dict(pocket_tier_counts),
        "topRawPockets": pockets[:30],
        "strategyDiagnostics": diagnosed_rows,
        "verdict": (
            "Do not promote any full-market 5m strategy. The batch shows severe cost, overtrading, and drawdown failure."
            if all_rejected
            else "Some strategies passed the first ranking gate; review them separately."
        ),
        "recommendedNextActions": [
            "Keep the current full-market 5m strategy batch out of sandbox promotion.",
            "Retest only raw pocket pairs with explicit pair whitelist, higher selectivity, and lower trade frequency.",
            "Add regime/liquidity filters before re-running 5m candidates.",
            "Stress test raw pockets with 5bp and 10bp extra one-way slippage before any forward observation.",
            "Prefer fewer trades with clearer 2R structure over high-frequency overtrading.",
        ],
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
        "# External 5m Failure Diagnosis",
        "",
        f"- Status: `{report['status']}`",
        f"- Source progress: `{format_value(report.get('sourceProgressPct'), '%')}`",
        f"- Strategy count: `{report.get('strategyCount')}`",
        f"- All strategies rejected: `{report.get('allStrategiesRejected')}`",
        f"- Raw pocket count: `{report.get('rawPocketCount')}`",
        "",
        "Safety boundary: local research report only. No Dry-run, no live trading, no private API, no account read, no order creation.",
        "",
        "## Verdict",
        "",
        report.get("verdict", "--"),
        "",
        "## Failure Flags",
        "",
    ]
    for flag, count in sorted((report.get("failureFlagCounts") or {}).items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"- `{flag}`: `{count}`")
    lines.extend(["", "## Top Raw Pair Pockets", ""])
    lines.append("| Rank | Tier | Strategy | Pair | Score | Trades | Raw Return | Raw PF | Raw Win Rate |")
    lines.append("|---:|---|---|---|---:|---:|---:|---:|---:|")
    pockets = report.get("topRawPockets") or []
    if not pockets:
        lines.append("| 0 | none | -- | -- | -- | -- | -- | -- | -- |")
    for index, item in enumerate(pockets[:20], start=1):
        lines.append(
            "| "
            + " | ".join(
                [
                    str(index),
                    str(item.get("tier")),
                    str(item.get("strategyName")),
                    str(item.get("pair")),
                    format_value(item.get("pocketScore")),
                    str(item.get("tradeCount")),
                    format_value(item.get("rawReturnPctOfTotalCapital"), "%"),
                    format_value(item.get("rawProfitFactor")),
                    format_value(item.get("rawWinRate"), "%"),
                ]
            )
            + " |"
        )
    lines.extend(["", "## Recommended Next Actions", ""])
    lines.extend(f"- {item}" for item in report.get("recommendedNextActions") or [])
    lines.append("")
    return "\n".join(lines)


def export_report(ranking: Path, output_json: Path, output_summary: Path) -> tuple[Path, Path]:
    report = build_report(ranking)
    write_json(output_json, report)
    write_text(output_summary, build_summary(report))
    return output_json, output_summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate external 5m failure diagnosis report.")
    parser.add_argument("--ranking", default=DEFAULT_RANKING.as_posix())
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON.as_posix())
    parser.add_argument("--output-summary", default=DEFAULT_OUTPUT_SUMMARY.as_posix())
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_json, output_summary = export_report(
        ranking=Path(args.ranking),
        output_json=Path(args.output_json),
        output_summary=Path(args.output_summary),
    )
    print(f"Wrote {output_json}")
    print(f"Wrote {output_summary}")


if __name__ == "__main__":
    main()
