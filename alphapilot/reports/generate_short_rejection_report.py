"""Generate V13.4.29 Short Rejection 1H research report.

The generator reads local Freqtrade backtest result files only. It does not run
backtests, enter Dry-run, call private exchange APIs, read accounts, create
orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from alphapilot.reports.short_rejection_report_schema import (
    ShortRejectionReport,
    ShortRejectionRunSummary,
    SlippageAdjustedMetrics,
)

STRATEGY_CLASS = "AlphaPilotShortRejection1HV01"
STRATEGY_ID = "alpha_short_rejection_1h_v01"
STRATEGY_NAME = "AlphaPilot Short Rejection 1H V0.1"
STRATEGY_VERSION = "0.1-v13.4.29"
SMOKE_PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
EXCLUDED_PAIRS = ["FET/USDT:USDT", "TON/USDT:USDT"]
WATCHLIST_PAIRS = ["ORDI/USDT:USDT"]
DEFAULT_RESULT_DIR = Path("user_data/backtest_results")
DEFAULT_OUTPUT_REPORT = Path("reports/v13_4_29_short_rejection_1h_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_29_short_rejection_1h_summary.md")
DEFAULT_REGIME_REPORT = Path("reports/v13_4_28_post_repair_market_regime_data_integrity_report.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any] | list[Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_freqtrade_payload(path: Path) -> dict[str, Any] | list[Any]:
    if path.suffix.lower() != ".zip":
        return _read_json(path)
    with ZipFile(path) as archive:
        result_members = [
            name
            for name in archive.namelist()
            if name.lower().endswith(".json")
            and not name.lower().endswith("_config.json")
            and not name.lower().endswith(".meta.json")
        ]
        if not result_members:
            return {}
        return json.loads(archive.read(result_members[0]).decode("utf-8"))


def _iter_result_files(result_dir: Path) -> list[Path]:
    if not result_dir.exists():
        return []
    candidates = [
        path
        for pattern in ("*.zip", "*.json")
        for path in result_dir.glob(pattern)
        if path.is_file()
        and not path.name.lower().endswith(".meta.json")
        and path.name != ".last_result.json"
    ]
    return sorted(candidates, key=lambda path: path.stat().st_mtime, reverse=True)


def _select_strategy_payload(payload: dict[str, Any] | list[Any]) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    strategy = payload.get("strategy")
    if not isinstance(strategy, dict):
        return None
    if STRATEGY_CLASS in strategy and isinstance(strategy[STRATEGY_CLASS], dict):
        return strategy[STRATEGY_CLASS]
    for value in strategy.values():
        if isinstance(value, dict) and value.get("strategy_name") == STRATEGY_CLASS:
            return value
    return None


def _safe_float(value: Any, default: float | None = None) -> float | None:
    try:
        if value is None:
            return default
        number = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _safe_int(value: Any, default: int | None = None) -> int | None:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _pct_from_source(source: dict[str, Any], pct_key: str, ratio_key: str) -> float | None:
    pct = _safe_float(source.get(pct_key), None)
    if pct is not None:
        return round(pct, 4)
    ratio = _safe_float(source.get(ratio_key), None)
    if ratio is None:
        return None
    return round(ratio * 100 if -1 <= ratio <= 1 else ratio, 4)


def _drawdown_pct(source: dict[str, Any]) -> float | None:
    for pct_key in ("max_drawdown_account_pct", "max_drawdown_pct"):
        value = _safe_float(source.get(pct_key), None)
        if value is not None:
            return round(abs(value), 4)
    for ratio_key in ("max_drawdown_account", "max_drawdown"):
        value = _safe_float(source.get(ratio_key), None)
        if value is not None:
            return round(abs(value * 100 if -1 <= value <= 1 else value), 4)
    return None


def _win_rate(source: dict[str, Any], trade_count: int) -> float | None:
    wins = _safe_int(source.get("wins"), None)
    if trade_count and wins is not None:
        return round(wins / trade_count * 100, 4)
    value = _safe_float(source.get("winrate"), None)
    if value is None:
        return None
    return round(value * 100 if 0 <= value <= 1 else value, 4)


def _max_consecutive_losses(source: dict[str, Any]) -> int | None:
    direct = _safe_int(source.get("max_consecutive_losses"), None)
    if direct is not None:
        return direct
    trades = source.get("trades") or []
    if not isinstance(trades, list):
        return None
    ordered = sorted(trades, key=lambda item: item.get("close_timestamp") or item.get("open_timestamp") or 0)
    best = 0
    current = 0
    for trade in ordered:
        profit = _safe_float(trade.get("profit_abs"), _safe_float(trade.get("profit_ratio"), 0.0))
        if profit is not None and profit < 0:
            current += 1
            best = max(best, current)
        else:
            current = 0
    return best


def _slippage_metrics(source: dict[str, Any], rate: float) -> SlippageAdjustedMetrics:
    trades = source.get("trades") or []
    starting_balance = _safe_float(source.get("starting_balance"), 0.0) or 0.0
    positive = 0.0
    negative = 0.0
    total = 0.0
    total_cost = 0.0
    if not isinstance(trades, list):
        trades = []
    for trade in trades:
        profit_abs = _safe_float(trade.get("profit_abs"), 0.0) or 0.0
        stake = _safe_float(trade.get("max_stake_amount"), _safe_float(trade.get("stake_amount"), 0.0)) or 0.0
        leverage = _safe_float(trade.get("leverage"), 1.0) or 1.0
        notional = stake * leverage
        cost = notional * rate * 2
        adjusted = profit_abs - cost
        total += adjusted
        total_cost += cost
        if adjusted > 0:
            positive += adjusted
        elif adjusted < 0:
            negative += adjusted
    return_pct = round(total / starting_balance * 100, 4) if starting_balance else None
    profit_factor = round(positive / abs(negative), 4) if negative < 0 else None
    return SlippageAdjustedMetrics(
        slippageRateOneWay=rate,
        totalSlippageCost=round(total_cost, 8),
        totalReturnPct=return_pct,
        profitFactor=profit_factor,
    )


def _pairlist(source: dict[str, Any]) -> list[str]:
    pairs = source.get("pairlist")
    if isinstance(pairs, list):
        return [str(pair) for pair in pairs]
    trades = source.get("trades") or []
    if not isinstance(trades, list):
        return []
    return sorted({str(trade.get("pair")) for trade in trades if trade.get("pair")})


def _scope_for_run(source: dict[str, Any]) -> str:
    pairs = set(_pairlist(source))
    timerange = str(source.get("timerange") or "")
    if pairs == set(SMOKE_PAIRS) and timerange.startswith("20260401"):
        return "smoke"
    if len(pairs) > len(SMOKE_PAIRS) and timerange.startswith("20260101"):
        return "expanded"
    return "unknown"


def _compact_rows(rows: Any, max_rows: int = 40) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        return []
    output = []
    for row in rows[:max_rows]:
        if isinstance(row, dict):
            output.append(row)
    return output


def _monthly_performance(source: dict[str, Any]) -> list[dict[str, Any]]:
    periodic = source.get("periodic_breakdown", {})
    if not isinstance(periodic, dict):
        return []
    return _compact_rows(periodic.get("month", []), max_rows=60)


def _build_run(path: Path, source: dict[str, Any]) -> ShortRejectionRunSummary:
    trade_count = _safe_int(source.get("total_trades", source.get("trade_count")), 0) or 0
    short_count = _safe_int(source.get("trade_count_short"), None)
    long_count = _safe_int(source.get("trade_count_long"), None)
    trades = source.get("trades") or []
    if isinstance(trades, list):
        if short_count is None:
            short_count = sum(1 for trade in trades if bool(trade.get("is_short")))
        if long_count is None:
            long_count = sum(1 for trade in trades if not bool(trade.get("is_short")))
    short_count = short_count or 0
    long_count = long_count or 0
    slippage_stress = [_slippage_metrics(source, rate) for rate in (0.0005, 0.001, 0.002)]
    base_slippage = slippage_stress[0]
    warnings = []
    if long_count:
        warnings.append("Long trades detected in a short-only research strategy result.")
    if trade_count == 0:
        warnings.append("No trades were generated in this backtest run.")
    return ShortRejectionRunSummary(
        scope=_scope_for_run(source),
        resultPath=path.as_posix(),
        isRealBacktest=True,
        strategyName=str(source.get("strategy_name") or STRATEGY_CLASS),
        pairs=_pairlist(source),
        timerange=source.get("timerange"),
        timeframe=source.get("timeframe"),
        tradeCount=trade_count,
        shortTradeCount=short_count,
        longTradeCount=long_count,
        totalReturnPct=_pct_from_source(source, "profit_total_pct", "profit_total"),
        slippageAdjustedTotalReturnPct=base_slippage.totalReturnPct,
        maxDrawdownPct=_drawdown_pct(source),
        profitFactor=round(value, 4) if (value := _safe_float(source.get("profit_factor"), None)) is not None else None,
        slippageAdjustedProfitFactor=base_slippage.profitFactor,
        winRate=_win_rate(source, trade_count),
        maxConsecutiveLosses=_max_consecutive_losses(source),
        exitReasonBreakdown=_compact_rows(source.get("exit_reason_summary", []), max_rows=40),
        pairPerformance=_compact_rows(source.get("results_per_pair", []), max_rows=60),
        monthlyPerformance=_monthly_performance(source),
        slippageStress=slippage_stress,
        warnings=warnings,
    )


def _load_runs(result_dir: Path) -> list[ShortRejectionRunSummary]:
    runs: list[ShortRejectionRunSummary] = []
    seen: set[str] = set()
    for path in _iter_result_files(result_dir):
        try:
            payload = _read_freqtrade_payload(path)
        except Exception:
            continue
        source = _select_strategy_payload(payload)
        if not source:
            continue
        key = f"{source.get('timerange')}|{','.join(_pairlist(source))}|{source.get('backtest_run_start_ts')}"
        if key in seen:
            continue
        seen.add(key)
        runs.append(_build_run(path, source))
    return runs


def _pick_primary(runs: list[ShortRejectionRunSummary]) -> ShortRejectionRunSummary | None:
    expanded = [run for run in runs if run.scope == "expanded"]
    if expanded:
        return expanded[0]
    smoke = [run for run in runs if run.scope == "smoke"]
    if smoke:
        return smoke[0]
    return runs[0] if runs else None


def _regime_background(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"status": "unavailable", "reason": f"{path.as_posix()} not found"}
    try:
        report = _read_json(path)
    except Exception as exc:  # noqa: BLE001 - preserve report limitation.
        return {"status": "unavailable", "reason": str(exc)}
    if not isinstance(report, dict):
        return {"status": "unavailable", "reason": "regime report is not an object"}
    regime = report.get("btcRegime", {})
    integrity = report.get("dataIntegrity", {}).get("summary", {})
    return {
        "status": "available",
        "source": path.as_posix(),
        "dominantRegimes": regime.get("dominantRegimes", []),
        "regimeDistribution": regime.get("regimeDistribution", {}),
        "dataIntegrityStatus": integrity.get("status"),
        "missingFileCount": integrity.get("missingFileCount"),
        "notes": "Regime background is not used as a hard entry gate in V13.4.29.",
    }


def _research_gate(primary: ShortRejectionRunSummary | None) -> dict[str, Any]:
    if primary is None:
        return {
            "researchWorthContinuing": False,
            "reason": "no_real_backtest_result",
            "criteria": {
                "slippageAdjustedProfitFactorGt105": False,
                "tradeCountAtLeast20": False,
                "maxDrawdownAcceptable": False,
                "maxConsecutiveLossesAcceptable": False,
                "noSinglePairDominates": False,
            },
        }
    pair_counts = [
        int(row.get("trades") or 0)
        for row in primary.pairPerformance
        if row.get("key") not in {None, "TOTAL"}
    ]
    top_share = max(pair_counts) / primary.tradeCount if primary.tradeCount and pair_counts else 0
    criteria = {
        "slippageAdjustedProfitFactorGt105": bool(
            primary.slippageAdjustedProfitFactor is not None and primary.slippageAdjustedProfitFactor > 1.05
        ),
        "tradeCountAtLeast20": primary.tradeCount >= 20,
        "maxDrawdownAcceptable": bool(primary.maxDrawdownPct is not None and primary.maxDrawdownPct <= 35),
        "maxConsecutiveLossesAcceptable": bool(
            primary.maxConsecutiveLosses is not None and primary.maxConsecutiveLosses <= 20
        ),
        "noSinglePairDominates": top_share <= 0.5,
    }
    return {
        "researchWorthContinuing": all(criteria.values()),
        "reason": "criteria_passed" if all(criteria.values()) else "criteria_not_met",
        "topPairTradeShare": round(top_share, 4),
        "criteria": criteria,
        "dryRunApproved": False,
    }


def build_report(args: argparse.Namespace) -> ShortRejectionReport:
    runs = _load_runs(Path(args.result_dir))
    smoke_runs = [run for run in runs if run.scope == "smoke"]
    expanded_runs = [run for run in runs if run.scope == "expanded"]
    primary = _pick_primary(runs)
    is_mock = len(smoke_runs) == 0
    warnings: list[str] = []
    if is_mock:
        warnings.append("No real smoke backtest result found for AlphaPilotShortRejection1HV01.")
    if not expanded_runs:
        warnings.append("Expanded backtest result not found or failed before report generation.")
    warnings.extend(item for run in runs for item in run.warnings)
    safety = {
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "tradeApiUsed": False,
        "withdrawApiUsed": False,
        "apiKeyStored": False,
        "accountRead": False,
        "positionRead": False,
        "orderCreated": False,
        "autoTrading": False,
        "mobileAppChanged": False,
    }
    if primary is None:
        primary_payload = {
            "scope": None,
            "pairs": [],
            "timerange": None,
            "tradeCount": 0,
            "shortTradeCount": 0,
            "totalReturnPct": None,
            "slippageAdjustedTotalReturnPct": None,
            "maxDrawdownPct": None,
            "profitFactor": None,
            "slippageAdjustedProfitFactor": None,
            "winRate": None,
            "maxConsecutiveLosses": None,
            "exitReasonBreakdown": [],
            "pairPerformance": [],
            "monthlyPerformance": [],
        }
    else:
        primary_payload = primary.to_dict()
    primary_for_gate = primary
    gate = _research_gate(primary_for_gate)
    if primary_for_gate is not None and not gate.get("researchWorthContinuing"):
        warnings.append("Research gate failed; this short-only idea is not approved for continuation without redesign.")

    return ShortRejectionReport(
        reportId="v13_4_29_short_rejection_1h_research",
        version="V13.4.29",
        status="completed" if not is_mock else "blocked_no_real_smoke_result",
        isMock=is_mock,
        strategyId=STRATEGY_ID,
        strategyName=STRATEGY_NAME,
        strategyVersion=STRATEGY_VERSION,
        timeframe="1h",
        direction="short_only",
        primaryRunScope=primary_payload.get("scope"),
        pairs=primary_payload.get("pairs", []),
        timerange=primary_payload.get("timerange"),
        tradeCount=int(primary_payload.get("tradeCount") or 0),
        shortTradeCount=int(primary_payload.get("shortTradeCount") or 0),
        totalReturnPct=primary_payload.get("totalReturnPct"),
        slippageAdjustedTotalReturnPct=primary_payload.get("slippageAdjustedTotalReturnPct"),
        maxDrawdownPct=primary_payload.get("maxDrawdownPct"),
        profitFactor=primary_payload.get("profitFactor"),
        slippageAdjustedProfitFactor=primary_payload.get("slippageAdjustedProfitFactor"),
        winRate=primary_payload.get("winRate"),
        maxConsecutiveLosses=primary_payload.get("maxConsecutiveLosses"),
        exitReasonBreakdown=primary_payload.get("exitReasonBreakdown", []),
        pairPerformance=primary_payload.get("pairPerformance", []),
        monthlyPerformance=primary_payload.get("monthlyPerformance", []),
        regimeBackground=_regime_background(Path(args.regime_report)),
        excludedPairs=EXCLUDED_PAIRS,
        watchlistPairs=WATCHLIST_PAIRS,
        exclusionReasons={
            "FET/USDT:USDT": "V13.4.28 post-repair local OHLCV coverage still missing 1h/4h futures files.",
            "TON/USDT:USDT": "V13.4.28 post-repair local OHLCV coverage still missing 1h/4h futures files.",
            "ORDI/USDT:USDT": "Kept as watchlist pair because V13.4.28 still flags a 4h extreme-return warning.",
        },
        backtestRuns=[run.to_dict() for run in runs],
        smokeBacktestSucceeded=bool(smoke_runs),
        expandedBacktestSucceeded=bool(expanded_runs),
        expandedFailed=not bool(expanded_runs),
        researchGate=gate,
        slippageAppliedByFreqtrade=False,
        slippageAppliedByPostProcessing=True,
        dryRunApproved=False,
        liveTradingApproved=False,
        safetyBoundary=safety,
        generatedAt=utc_now(),
        warnings=warnings,
    )


def _summary_markdown(report: dict[str, Any]) -> str:
    gate = report.get("researchGate", {})
    warnings = report.get("warnings", [])
    return f"""# AlphaPilot V13.4.29 Short Rejection 1H Research Report

Status: {report.get("status")}

V13.4.29 adds a short-only 1h rejection research strategy and reports local
Freqtrade backtest results. It does not enter Dry-run, live trading, private
exchange APIs, account reads, position reads, order creation, or auto trading.

## Strategy

- strategyId: {report.get("strategyId")}
- strategyName: {report.get("strategyName")}
- timeframe: {report.get("timeframe")}
- direction: {report.get("direction")}
- primaryRunScope: {report.get("primaryRunScope")}
- isMock: {report.get("isMock")}

## Primary Metrics

- pairs: {", ".join(report.get("pairs", [])) or "none"}
- timerange: {report.get("timerange")}
- tradeCount: {report.get("tradeCount")}
- shortTradeCount: {report.get("shortTradeCount")}
- totalReturnPct: {report.get("totalReturnPct")}
- slippageAdjustedTotalReturnPct: {report.get("slippageAdjustedTotalReturnPct")}
- maxDrawdownPct: {report.get("maxDrawdownPct")}
- profitFactor: {report.get("profitFactor")}
- slippageAdjustedProfitFactor: {report.get("slippageAdjustedProfitFactor")}
- winRate: {report.get("winRate")}
- maxConsecutiveLosses: {report.get("maxConsecutiveLosses")}

## Scope Decisions

- excludedPairs: {", ".join(report.get("excludedPairs", [])) or "none"}
- watchlistPairs: {", ".join(report.get("watchlistPairs", [])) or "none"}
- smokeBacktestSucceeded: {report.get("smokeBacktestSucceeded")}
- expandedBacktestSucceeded: {report.get("expandedBacktestSucceeded")}
- expandedFailed: {report.get("expandedFailed")}

## Research Gate

```json
{json.dumps(gate, ensure_ascii=False, indent=2)}
```

The research gate may decide whether this idea is worth further research, but
it does not approve Dry-run or live trading.

## Exit Reason Breakdown

{chr(10).join(f"- {item.get('key')}: trades={item.get('trades')} profit_total_pct={item.get('profit_total_pct')}" for item in report.get("exitReasonBreakdown", [])) or "- none"}

## Safety Boundary

- dryRunApproved: {report.get("dryRunApproved")}
- liveTradingApproved: {report.get("liveTradingApproved")}
- slippageAppliedByFreqtrade: {report.get("slippageAppliedByFreqtrade")}
- slippageAppliedByPostProcessing: {report.get("slippageAppliedByPostProcessing")}
- no Trade API
- no Withdraw API
- no real API key storage
- no account or position reads
- no order creation
- no auto trading

Warnings:

{chr(10).join(f"- {item}" for item in warnings) or "- none"}
"""


def run(args: argparse.Namespace) -> dict[str, Any]:
    report = build_report(args)
    payload = report.to_dict()
    _write_json(Path(args.output_report), payload)
    _write_text(Path(args.output_summary), _summary_markdown(payload))
    return payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate V13.4.29 Short Rejection 1H report.")
    parser.add_argument("--result-dir", default=str(DEFAULT_RESULT_DIR))
    parser.add_argument("--regime-report", default=str(DEFAULT_REGIME_REPORT))
    parser.add_argument("--output-report", default=str(DEFAULT_OUTPUT_REPORT))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    report = run(args)
    print(f"V13.4.29 status: {report.get('status')}")
    print(f"isMock: {report.get('isMock')}")
    print(f"primaryRunScope: {report.get('primaryRunScope')}")
    print(f"tradeCount: {report.get('tradeCount')}")
    print(f"Report: {args.output_report}")
    print(f"Summary: {args.output_summary}")


if __name__ == "__main__":
    main()
