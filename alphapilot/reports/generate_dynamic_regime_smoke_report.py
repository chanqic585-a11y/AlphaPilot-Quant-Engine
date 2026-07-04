"""Generate V13.4.16 Dynamic Regime smoke backtest report.

This module reads local Freqtrade backtest artifacts and local public OHLCV
files. It does not enter Dry-run, call exchange APIs, read accounts, create
orders, or auto trade.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.reports.dynamic_regime_smoke_schema import DynamicRegimeSmokeReport
from alphapilot.reports.export_backtest_report import (
    _build_metrics,
    _find_latest_freqtrade_result,
    _read_freqtrade_result_payload,
    _select_strategy_payload,
)

REPORT_ID = "v13_4_16_dynamic_regime_smoke_report"
REPORT_VERSION = "V13.4.16"
STRATEGY_CLASS = "AlphaPilotDynamicRegimeV01"
STRATEGY_ID = "alpha_dynamic_regime_v01"
STRATEGY_NAME = "AlphaPilot Dynamic Regime V0.1"
STRATEGY_VERSION = "0.1-v13.4.15"
DEFAULT_PAIRS = ["BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT"]
DEFAULT_TIMERANGE = "20260401-"
DEFAULT_TIMEFRAME = "1h"
DEFAULT_DATA_PATH = Path("user_data/data/okx/futures")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_16_dynamic_regime_smoke_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_16_dynamic_regime_smoke_summary.md")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _pair_stem(pair: str) -> str:
    return pair.replace("/", "_").replace(":", "_")


def _read_ohlcv(pair: str, timeframe: str, data_path: Path) -> pd.DataFrame:
    path = data_path / f"{_pair_stem(pair)}-{timeframe}-futures.feather"
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_feather(path)
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    return frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)


def _local_merge_informative_pair(
    dataframe: pd.DataFrame,
    informative: pd.DataFrame,
    timeframe: str,
    informative_timeframe: str,
    ffill: bool = True,
) -> pd.DataFrame:
    if dataframe.empty or informative.empty or "date" not in informative.columns:
        return dataframe
    left = dataframe.sort_values("date").copy()
    right = informative.sort_values("date").copy()
    rename = {column: f"{column}_{informative_timeframe}" for column in right.columns if column != "date"}
    right = right.rename(columns=rename)
    merged = pd.merge_asof(left, right, on="date", direction="backward")
    return merged.ffill() if ffill else merged


class _LocalDataProvider:
    def __init__(self, pairs: list[str], data_path: Path) -> None:
        self.pairs = pairs
        self.data_path = data_path
        self.cache: dict[tuple[str, str], pd.DataFrame] = {}

    def current_whitelist(self) -> list[str]:
        return self.pairs

    def get_pair_dataframe(self, pair: str, timeframe: str) -> pd.DataFrame:
        key = (pair, timeframe)
        if key not in self.cache:
            self.cache[key] = _read_ohlcv(pair, timeframe, self.data_path)
        return self.cache[key].copy()


def _load_strategy_class() -> type:
    path = Path("user_data/strategies/AlphaPilotDynamicRegimeV01.py")
    spec = importlib.util.spec_from_file_location("AlphaPilotDynamicRegimeV01", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to import strategy from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.merge_informative_pair = _local_merge_informative_pair
    return module.AlphaPilotDynamicRegimeV01


def _timerange_start(timerange: str) -> pd.Timestamp | None:
    start_raw = timerange.split("-", 1)[0]
    if not start_raw:
        return None
    return pd.Timestamp(datetime.strptime(start_raw, "%Y%m%d").replace(tzinfo=timezone.utc))


def _audit_replay(pairs: list[str], timerange: str, data_path: Path) -> dict[str, Any]:
    strategy_class = _load_strategy_class()
    strategy = strategy_class()
    strategy.dp = _LocalDataProvider(pairs, data_path)
    start = _timerange_start(timerange)
    regime_counter: Counter[str] = Counter()
    skip_counter: Counter[str] = Counter()
    totals = {
        "rowsEvaluated": 0,
        "trendModulePass": 0,
        "meanReversionModulePass": 0,
        "probabilityScorePass": 0,
        "probabilityScoreFail": 0,
        "liquidityFallbackUsed": 0,
        "finalEntrySignals": 0,
    }
    warnings: list[str] = []

    for pair in pairs:
        frame = _read_ohlcv(pair, DEFAULT_TIMEFRAME, data_path)
        if frame.empty:
            warnings.append(f"{pair}: missing {DEFAULT_TIMEFRAME} OHLCV for audit replay")
            continue
        if start is not None:
            frame = frame[frame["date"] >= start].copy()
        if frame.empty:
            warnings.append(f"{pair}: no rows inside timerange for audit replay")
            continue
        try:
            analyzed = strategy.populate_indicators(frame.copy(), {"pair": pair})
            analyzed = strategy.populate_entry_trend(analyzed, {"pair": pair})
        except Exception as exc:  # noqa: BLE001 - report audit replay failure without blocking result conversion.
            warnings.append(f"{pair}: audit replay failed: {exc}")
            continue

        totals["rowsEvaluated"] += int(len(analyzed))
        for key, column in [
            ("trendModulePass", "ap_dyn_audit_trend_module_pass"),
            ("meanReversionModulePass", "ap_dyn_audit_mean_reversion_module_pass"),
            ("probabilityScorePass", "ap_dyn_audit_probability_score_pass"),
            ("liquidityFallbackUsed", "ap_dyn_audit_liquidity_gate_pass"),
            ("finalEntrySignals", "ap_dyn_audit_final_entry"),
        ]:
            if column in analyzed.columns:
                totals[key] += int(analyzed[column].fillna(False).astype(bool).sum())
        if "ap_dyn_audit_probability_score_pass" in analyzed.columns:
            totals["probabilityScoreFail"] += int((~analyzed["ap_dyn_audit_probability_score_pass"].fillna(False).astype(bool)).sum())
        if "ap_dyn_audit_regime" in analyzed.columns:
            regime_counter.update(str(value) for value in analyzed["ap_dyn_audit_regime"].fillna("unknown"))
        if "ap_dyn_audit_skip_reason" in analyzed.columns:
            skip_counter.update(str(value) for value in analyzed["ap_dyn_audit_skip_reason"].fillna("unknown"))

    return {
        "regimeBreakdown": dict(sorted(regime_counter.items())),
        "moduleBreakdown": {
            "trendModulePass": totals["trendModulePass"],
            "meanReversionModulePass": totals["meanReversionModulePass"],
            "finalEntrySignals": totals["finalEntrySignals"],
            "skipReasons": dict(skip_counter.most_common(15)),
        },
        "probabilityScoreSummary": {
            "rowsEvaluated": totals["rowsEvaluated"],
            "pass": totals["probabilityScorePass"],
            "fail": totals["probabilityScoreFail"],
            "source": "reports/v13_4_14_probability_score_table.json",
        },
        "liquidityGateSummary": {
            "available": False,
            "fallbackUsedRows": totals["liquidityFallbackUsed"],
            "fallbackPolicy": "allowed for smoke backtest research only; not a real liquidity approval",
        },
        "warnings": warnings,
    }


def _latest_strategy_result() -> tuple[Path | None, dict[str, Any]]:
    result = _find_latest_freqtrade_result()
    if result is None:
        return None, {}
    payload = _read_freqtrade_result_payload(result)
    strategy_name, source = _select_strategy_payload(payload)
    if strategy_name != STRATEGY_CLASS:
        return result, {}
    return result, source


def _metrics(source: dict[str, Any]) -> dict[str, Any]:
    if not source:
        return {
            "tradeCount": 0,
            "totalReturnPct": None,
            "maxDrawdownPct": None,
            "profitFactor": None,
            "winRate": None,
        }
    metrics = _build_metrics(source)
    return {
        "tradeCount": metrics.tradeCount,
        "totalReturnPct": metrics.totalReturnPct,
        "maxDrawdownPct": metrics.maxDrawdownPct,
        "profitFactor": metrics.profitFactor,
        "winRate": metrics.winRate,
        "feesPaid": metrics.feesPaid,
        "averageHoldingMinutes": metrics.averageHoldingMinutes,
    }


def build_report(pairs: list[str], timerange: str, data_path: Path) -> DynamicRegimeSmokeReport:
    result_path, source = _latest_strategy_result()
    audit = _audit_replay(pairs, timerange, data_path)
    warnings = list(audit.get("warnings", []))
    if result_path is None:
        warnings.append("No Freqtrade result found. Report is blocked and not taggable.")
    elif not source:
        warnings.append(f"Latest Freqtrade result is not for {STRATEGY_CLASS}: {result_path}")

    return DynamicRegimeSmokeReport(
        reportId=REPORT_ID,
        version=REPORT_VERSION,
        strategyId=STRATEGY_ID,
        strategyName=STRATEGY_NAME,
        strategyVersion=STRATEGY_VERSION,
        timerange=timerange,
        timeframe=DEFAULT_TIMEFRAME,
        pairs=pairs,
        isMock=False if source else True,
        dryRunApproved=False,
        liveTradingApproved=False,
        metrics=_metrics(source),
        regimeBreakdown=audit["regimeBreakdown"],
        moduleBreakdown=audit["moduleBreakdown"],
        probabilityScoreSummary=audit["probabilityScoreSummary"],
        liquidityGateSummary=audit["liquidityGateSummary"],
        backtestResultPath=str(result_path) if result_path else None,
        reportWarnings=warnings,
        generatedAt=_utc_now(),
    )


def write_summary(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# V13.4.16 Dynamic Regime Smoke Backtest Summary",
        "",
        "## Status",
        "",
        f"- strategyId: {report['strategyId']}",
        f"- isMock: {str(report['isMock']).lower()}",
        f"- dryRunApproved: {str(report['dryRunApproved']).lower()}",
        f"- liveTradingApproved: {str(report['liveTradingApproved']).lower()}",
        f"- timerange: {report['timerange']}",
        f"- timeframe: {report['timeframe']}",
        f"- pairs: {', '.join(report['pairs'])}",
        f"- backtestResultPath: {report['backtestResultPath']}",
        "",
        "## Metrics",
        "",
    ]
    for key, value in report["metrics"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Regime Breakdown", ""])
    if report["regimeBreakdown"]:
        lines.extend(f"- {key}: {value}" for key, value in report["regimeBreakdown"].items())
    else:
        lines.append("- unavailable")
    lines.extend(["", "## Module Breakdown", ""])
    for key, value in report["moduleBreakdown"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Probability Score Summary", ""])
    for key, value in report["probabilityScoreSummary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Liquidity Gate Summary", ""])
    for key, value in report["liquidityGateSummary"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## Warnings", ""])
    if report["reportWarnings"]:
        lines.extend(f"- {warning}" for warning in report["reportWarnings"])
    else:
        lines.append("- none")
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "This is a local Freqtrade smoke backtest report only. It is not Dry-run approval and not live trading approval. No API key, Trade API, Withdraw API, account read, position read, order creation, or auto trading is used.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.16 Dynamic Regime smoke report.")
    parser.add_argument("--pairs", default=",".join(DEFAULT_PAIRS))
    parser.add_argument("--timerange", default=DEFAULT_TIMERANGE)
    parser.add_argument("--data-path", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    args = parser.parse_args()

    pairs = [part.strip() for part in args.pairs.split(",") if part.strip()]
    report = build_report(pairs, args.timerange, args.data_path)
    payload = report.to_dict()
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    write_summary(payload, args.output_summary)
    print(f"Dynamic Regime smoke report: {args.output_json}")
    print(f"Summary: {args.output_summary}")
    print(f"isMock: {report.isMock}")
    print(f"tradeCount: {report.metrics.get('tradeCount')}")


if __name__ == "__main__":
    main()

