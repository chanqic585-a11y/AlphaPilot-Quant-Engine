"""Generate V13.5.18 non-OKX expansion replay report.

This report documents the Binance/Bybit Top20 public-data expansion and reruns
the fixed active-pool available-universe replay. It is research-only and does
not approve exchange Dry-run or live trading.
"""

from __future__ import annotations

import argparse
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.derivatives.exchange_feature_panel import discover_exchange_pairs
from alphapilot.reports.generate_v13_5_17_available_universe_exchange_replay_report import (
    DEFAULT_ACTIVE_POOL_ID,
    generate_report as generate_available_universe_report,
)
from alphapilot.reports.generate_v13_5_derivatives_ml_strategy_report import _json_ready, write_json, write_text


VERSION = "V13.5.18"
REPORT_ID = "v13_5_18_non_okx_expansion_replay_report"
DEFAULT_OUTPUT_REPORT = Path("reports/v13_5_18_non_okx_expansion_replay_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_5_18_non_okx_expansion_replay_summary.md")
DEFAULT_OUTPUT_SIGNAL_LOG = Path("reports/v13_5_18_non_okx_expansion_signal_log.json")
DEFAULT_EXCHANGES = ["okx", "binance", "bybit"]
TARGET_NON_OKX_PAIR_COUNT = 20


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_csv(value: str | None, default: list[str]) -> list[str]:
    if not value:
        return default.copy()
    return [item.strip() for item in value.split(",") if item.strip()]


def _expansion_status(exchanges: list[str], data_root: Path, timeframe: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for exchange in exchanges:
        pairs = discover_exchange_pairs(exchange, timeframe=timeframe, data_root=data_root)
        target = TARGET_NON_OKX_PAIR_COUNT if exchange in {"binance", "bybit"} else None
        rows.append(
            {
                "exchange": exchange,
                "timeframe": timeframe,
                "availablePairCount": len(pairs),
                "targetPairCount": target,
                "targetReached": (len(pairs) >= target) if target else None,
                "samplePairs": pairs[:25],
            }
        )
    return rows


def _summary_markdown(report: dict[str, Any]) -> str:
    combined = report["combinedActivePoolMetrics"]
    decision = report["decision"]
    lines = [
        "# AlphaPilot V13.5.18 Non-OKX Expansion Replay",
        "",
        "This report reruns the fixed active pool after expanding Binance and Bybit public 4h data to Top20 candidates.",
        "",
        "## Data Expansion",
        "",
    ]
    for row in report["nonOkxExpansion"]:
        lines.append(
            f"- {row['exchange']}: availablePairCount={row['availablePairCount']}, "
            f"targetPairCount={row['targetPairCount']}, targetReached={row['targetReached']}"
        )
    lines.extend(
        [
            "",
            "## Combined Active Pool Metrics",
            "",
            f"- tradeCount: {combined.get('tradeCount')}",
            f"- winRatePct: {combined.get('winRatePct')}",
            f"- profitFactor: {combined.get('profitFactor')}",
            f"- rewardRiskRatio: {combined.get('rewardRiskRatio')}",
            f"- maxDrawdownPct: {combined.get('maxDrawdownPct')}",
            "",
            "## By Exchange",
            "",
        ]
    )
    for item in report["combinedByExchange"]:
        lines.append(
            f"- {item['label']}: trades={item.get('tradeCount')}, winRate={item.get('winRatePct')}, "
            f"pf={item.get('profitFactor')}, maxDD={item.get('maxDrawdownPct')}"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            f"- sampleAdequate: {decision['sampleAdequate']}",
            f"- exchangeBalanceAdequate: {decision['exchangeBalanceAdequate']}",
            f"- readyForExchangeDryRunReview: {decision['readyForExchangeDryRunReview']}",
            f"- nextAction: {decision['nextAction']}",
            "",
            "## Safety Boundary",
            "",
            "- No Trade API.",
            "- No Withdraw API.",
            "- No API key storage.",
            "- No real account reads.",
            "- No real position reads.",
            "- No order creation.",
            "- No automatic trading.",
        ]
    )
    return "\n".join(lines) + "\n"


def generate_report(args: argparse.Namespace) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    exchanges = _parse_csv(args.exchanges, DEFAULT_EXCHANGES)
    replay_args = Namespace(
        data_root=args.data_root,
        exchanges=",".join(exchanges),
        active_pool_id=args.active_pool_id,
        max_pairs=0,
    )
    report, signals = generate_available_universe_report(replay_args)
    pool_config = report["poolConfig"]
    report["version"] = VERSION
    report["reportId"] = REPORT_ID
    report["generatedAt"] = utc_now()
    report["nonOkxExpansion"] = _expansion_status(exchanges, args.data_root, pool_config["timeframe"])
    report["downloadCommand"] = {
        "script": "scripts/download_historical_robustness_data.ps1",
        "exchanges": "binance,bybit",
        "timeframes": pool_config["timeframe"],
        "timerange": "20200101-",
        "batchSize": 5,
        "prepend": True,
        "pairs": "Top20 research subset",
        "publicDataOnly": True,
    }
    report["decision"]["nonOkxTop20ExpansionCompleted"] = all(
        row["targetReached"] for row in report["nonOkxExpansion"] if row["targetPairCount"] is not None
    )
    report["decision"]["nextAction"] = (
        "review_drawdown_and_exchange_balance_before_any_forward_local_paper_refresh"
        if report["decision"]["exchangeBalanceAdequate"]
        else "expand_non_okx_public_data_or_wait_for_forward_readiness"
    )
    for row in signals:
        row["source"] = "v13_5_18_non_okx_expansion_replay_signal_log"
    return _json_ready(report), _json_ready(signals)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.5.18 non-OKX expansion replay report.")
    parser.add_argument("--data-root", type=Path, default=Path("user_data/data"))
    parser.add_argument("--exchanges", default=",".join(DEFAULT_EXCHANGES))
    parser.add_argument("--active-pool-id", default=DEFAULT_ACTIVE_POOL_ID)
    parser.add_argument("--output-report", type=Path, default=DEFAULT_OUTPUT_REPORT)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--output-signal-log", type=Path, default=DEFAULT_OUTPUT_SIGNAL_LOG)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report, signals = generate_report(args)
    write_json(args.output_report, report)
    write_text(args.output_summary, _summary_markdown(report))
    write_json(args.output_signal_log, signals)
    print(f"Wrote {args.output_report}")
    print(f"Wrote {args.output_summary}")
    print(f"Wrote {args.output_signal_log}")
    print(
        "combinedTrades="
        f"{report['combinedActivePoolMetrics'].get('tradeCount')} "
        f"exchangeBalanceAdequate={report['decision']['exchangeBalanceAdequate']} "
        f"nonOkxTop20ExpansionCompleted={report['decision']['nonOkxTop20ExpansionCompleted']}"
    )


if __name__ == "__main__":
    main()
