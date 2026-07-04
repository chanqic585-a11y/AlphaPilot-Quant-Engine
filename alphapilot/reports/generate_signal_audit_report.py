"""Generate V13.4.2 signal audit reports.

The audit reconstructs AlphaPilot Volume Rebound V0.1 filter columns from local
Freqtrade OHLCV data. It does not tune parameters, call exchange APIs, enter
dry-run, place orders, or read accounts.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zipfile import ZipFile

from alphapilot.reports.signal_audit_schema import SignalAuditReport

DEFAULT_BACKTEST_REPORT = Path("reports/v13_4_smoke_backtest_report.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_2_signal_audit_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_2_signal_audit_summary.md")
DEFAULT_DATA_DIR = Path("user_data/data/okx/futures")

SKIP_REASONS = [
    "data_missing",
    "btc_crash_filter",
    "weak_4h_trend",
    "rsi_out_of_range",
    "volume_ratio_too_low",
    "macd_not_improving",
    "ema20_reclaim_failed",
    "price_too_extended",
    "entry_signal_passed",
    "unknown",
]

FILTER_DEFS = [
    ("data_ready", "Data Ready", "ap_audit_data_ready", "data_missing"),
    ("btc_crash_filter", "BTC Crash Filter", "ap_audit_pass_btc_crash_filter", "btc_crash_filter"),
    ("4h_trend_filter", "4h Trend Filter", "ap_audit_pass_4h_trend_filter", "weak_4h_trend"),
    ("rsi_filter", "RSI Filter", "ap_audit_pass_rsi_filter", "rsi_out_of_range"),
    ("volume_filter", "Volume Ratio Filter", "ap_audit_pass_volume_filter", "volume_ratio_too_low"),
    ("macd_filter", "MACD Filter", "ap_audit_pass_macd_filter", "macd_not_improving"),
    (
        "ema20_reclaim_filter",
        "EMA20 Reclaim Filter",
        "ap_audit_pass_ema20_reclaim_filter",
        "ema20_reclaim_failed",
    ),
    ("no_chase_filter", "No Chase Filter", "ap_audit_pass_no_chase_filter", "price_too_extended"),
]


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


def _find_docker() -> str | None:
    docker = shutil.which("docker")
    if docker:
        return docker
    candidate = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
    return str(candidate) if candidate.exists() else None


def _maybe_rerun_in_docker(argv: list[str]) -> bool:
    if os.environ.get("ALPHAPILOT_SIGNAL_AUDIT_IN_DOCKER") == "1" or "--no-docker-fallback" in argv:
        return False

    try:
        import pyarrow  # noqa: F401

        return False
    except ModuleNotFoundError:
        docker = _find_docker()
        if not docker:
            return False

    repo_root = Path.cwd().resolve()
    docker_args = [
        docker,
        "run",
        "--rm",
        "-e",
        "ALPHAPILOT_SIGNAL_AUDIT_IN_DOCKER=1",
        "-v",
        f"{repo_root}:/workspace",
        "-w",
        "/workspace",
        "--entrypoint",
        "python",
        "freqtradeorg/freqtrade:stable",
        "-m",
        "alphapilot.reports.generate_signal_audit_report",
    ]
    docker_args.extend(arg for arg in argv if arg != "--no-docker-fallback")
    docker_args.append("--no-docker-fallback")
    completed = subprocess.run(docker_args, check=False)
    sys.exit(completed.returncode)


def _pair_to_file_stem(pair: str) -> str:
    return pair.replace("/", "_").replace(":", "_")


def _load_backtest_payload(source_result: Path) -> dict[str, Any]:
    if source_result.suffix.lower() == ".zip":
        with ZipFile(source_result) as archive:
            members = [
                name
                for name in archive.namelist()
                if name.endswith(".json")
                and not name.endswith("_config.json")
                and not name.endswith(".meta.json")
            ]
            if not members:
                return {}
            payload = json.loads(archive.read(members[0]).decode("utf-8"))
    else:
        payload = _read_json(source_result)
    strategy = payload.get("strategy", {})
    if "AlphaPilotVolumeReboundV01" in strategy:
        return strategy["AlphaPilotVolumeReboundV01"]
    if isinstance(strategy, dict) and strategy:
        first = next(iter(strategy.values()))
        return first if isinstance(first, dict) else {}
    return payload


def _import_pandas() -> tuple[Any, Any]:
    import numpy as np
    import pandas as pd

    return pd, np


def _load_ohlcv(data_dir: Path, pair: str, timeframe: str):
    pd, _ = _import_pandas()
    path = data_dir / f"{_pair_to_file_stem(pair)}-{timeframe}-futures.feather"
    if not path.exists():
        raise FileNotFoundError(path)
    frame = pd.read_feather(path)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    return frame.sort_values("date").reset_index(drop=True)


def _add_core_indicators(frame: Any) -> Any:
    pd, np = _import_pandas()
    frame = frame.copy()
    frame["ema20"] = frame["close"].ewm(span=20, adjust=False).mean()
    frame["ema200"] = frame["close"].ewm(span=200, adjust=False).mean()

    delta = frame["close"].diff()
    gain = delta.clip(lower=0).rolling(14, min_periods=14).mean()
    loss = (-delta.clip(upper=0)).rolling(14, min_periods=14).mean()
    rs = gain / loss.replace(0, np.nan)
    frame["rsi14"] = 100 - (100 / (1 + rs))

    ema12 = frame["close"].ewm(span=12, adjust=False).mean()
    ema26 = frame["close"].ewm(span=26, adjust=False).mean()
    frame["macd"] = ema12 - ema26
    frame["macd_signal"] = frame["macd"].ewm(span=9, adjust=False).mean()
    frame["macd_histogram"] = frame["macd"] - frame["macd_signal"]

    frame["volume_mean_20"] = frame["volume"].rolling(20, min_periods=20).mean()
    frame["volume_ratio"] = frame["volume"] / frame["volume_mean_20"].replace(0, np.nan)

    middle = frame["close"].rolling(20, min_periods=20).mean()
    std = frame["close"].rolling(20, min_periods=20).std()
    frame["bb_middle"] = middle
    frame["bb_upper"] = middle + std * 2
    frame["bb_lower"] = middle - std * 2
    return frame


def _merge_asof(base: Any, informative: Any, columns: list[str], suffix: str) -> Any:
    pd, _ = _import_pandas()
    info = informative[["date", *columns]].copy().sort_values("date")
    info = info.rename(columns={column: f"{column}_{suffix}" for column in columns})
    return pd.merge_asof(base.sort_values("date"), info, on="date", direction="backward")


def _audit_pair(
    data_dir: Path,
    pair: str,
    btc_frame: Any,
    start: Any,
    end: Any,
) -> Any:
    pd, _ = _import_pandas()
    frame = _add_core_indicators(_load_ohlcv(data_dir, pair, "15m"))
    h4 = _add_core_indicators(_load_ohlcv(data_dir, pair, "4h"))
    frame = _merge_asof(frame, h4, ["close", "ema20", "ema200"], "4h")

    btc = btc_frame[["date", "close"]].copy()
    btc["btc_close_15m"] = btc["close"]
    btc["btc_3_candle_return_15m"] = (btc["close"] / btc["close"].shift(3)) - 1
    frame = frame.merge(btc[["date", "btc_close_15m", "btc_3_candle_return_15m"]], on="date", how="left")

    frame["btc_data_missing"] = frame["btc_3_candle_return_15m"].isna()
    frame["trend_4h_data_missing"] = frame[["close_4h", "ema200_4h"]].isna().any(axis=1)
    frame["btc_crash_filter_blocked"] = frame["btc_data_missing"] | (frame["btc_3_candle_return_15m"] <= -0.01)
    frame["trend_4h_ok"] = (
        frame["close_4h"].notna()
        & frame["ema200_4h"].notna()
        & (frame["close_4h"] >= frame["ema200_4h"] * 0.98)
    )
    frame["rsi_ok"] = frame["rsi14"].between(30, 55, inclusive="both")
    frame["volume_rebound_ok"] = frame["volume_ratio"] >= 1.5
    frame["macd_improving"] = frame["macd_histogram"] > frame["macd_histogram"].shift(1)
    frame["near_ema20_ok"] = frame["close"] >= frame["ema20"] * 0.995
    frame["pullback_zone_ok"] = frame["close"] <= frame["bb_middle"] * 1.01
    frame["skip_data_missing"] = frame[
        ["btc_data_missing", "trend_4h_data_missing", "volume_ratio", "bb_middle", "ema20", "rsi14"]
    ].isna().any(axis=1) | frame[["btc_data_missing", "trend_4h_data_missing"]].any(axis=1)

    frame["ap_audit_data_ready"] = ~frame["skip_data_missing"]
    frame["ap_audit_base_candidate"] = frame["ap_audit_data_ready"]
    frame["ap_audit_pass_btc_crash_filter"] = ~frame["btc_crash_filter_blocked"]
    frame["ap_audit_pass_4h_trend_filter"] = frame["trend_4h_ok"]
    frame["ap_audit_pass_rsi_filter"] = frame["rsi_ok"]
    frame["ap_audit_pass_volume_filter"] = frame["volume_rebound_ok"]
    frame["ap_audit_pass_macd_filter"] = frame["macd_improving"]
    frame["ap_audit_pass_ema20_reclaim_filter"] = frame["near_ema20_ok"]
    frame["ap_audit_pass_no_chase_filter"] = frame["pullback_zone_ok"]
    frame["ap_audit_final_entry"] = (
        frame["ap_audit_data_ready"]
        & frame["ap_audit_pass_btc_crash_filter"]
        & frame["ap_audit_pass_4h_trend_filter"]
        & frame["ap_audit_pass_rsi_filter"]
        & frame["ap_audit_pass_volume_filter"]
        & frame["ap_audit_pass_macd_filter"]
        & frame["ap_audit_pass_ema20_reclaim_filter"]
        & frame["ap_audit_pass_no_chase_filter"]
    )

    conditions = [
        frame["ap_audit_final_entry"],
        ~frame["ap_audit_data_ready"],
        ~frame["ap_audit_pass_btc_crash_filter"],
        ~frame["ap_audit_pass_4h_trend_filter"],
        ~frame["ap_audit_pass_rsi_filter"],
        ~frame["ap_audit_pass_volume_filter"],
        ~frame["ap_audit_pass_macd_filter"],
        ~frame["ap_audit_pass_ema20_reclaim_filter"],
        ~frame["ap_audit_pass_no_chase_filter"],
    ]
    choices = [
        "entry_signal_passed",
        "data_missing",
        "btc_crash_filter",
        "weak_4h_trend",
        "rsi_out_of_range",
        "volume_ratio_too_low",
        "macd_not_improving",
        "ema20_reclaim_failed",
        "price_too_extended",
    ]
    _, np = _import_pandas()
    frame["ap_audit_skip_reason"] = np.select(conditions, choices, default="unknown")

    frame["pair"] = pair
    mask = (frame["date"] >= start) & (frame["date"] <= end)
    return frame.loc[mask].reset_index(drop=True)


def _filter_stats(frame: Any) -> list[dict[str, Any]]:
    stats = []
    total = len(frame)
    primary_counts = Counter(frame["ap_audit_skip_reason"].astype(str).tolist()) if total else Counter()
    data_ready = frame["ap_audit_data_ready"] if total else []
    for filter_id, name, column, primary_reason in FILTER_DEFS:
        denominator = total if filter_id == "data_ready" else int(data_ready.sum())
        if denominator:
            subset = frame if filter_id == "data_ready" else frame[frame["ap_audit_data_ready"]]
            pass_count = int(subset[column].sum())
            fail_count = int(denominator - pass_count)
            pass_rate = pass_count / denominator * 100
            fail_rate = fail_count / denominator * 100
        else:
            pass_count = 0
            fail_count = 0
            pass_rate = None
            fail_rate = None
        stats.append(
            {
                "filterId": filter_id,
                "name": name,
                "passCount": pass_count,
                "failCount": fail_count,
                "passRate": _round(pass_rate),
                "failRate": _round(fail_rate),
                "blockedAsPrimaryReason": int(primary_counts.get(primary_reason, 0)),
                "notes": "Counts are evaluated on data-ready rows except data_ready itself.",
            }
        )
    return stats


def _skip_counts(frame: Any) -> list[dict[str, Any]]:
    total = len(frame)
    counts = Counter(frame["ap_audit_skip_reason"].astype(str).tolist()) if total else Counter()
    return [
        {
            "skipReason": reason,
            "count": int(counts.get(reason, 0)),
            "percentage": _round((counts.get(reason, 0) / total * 100) if total else None),
        }
        for reason in SKIP_REASONS
    ]


def _pair_breakdown(frame: Any, actual_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trade_counts = Counter(trade.get("pair") for trade in actual_trades)
    rows = []
    for pair, group in frame.groupby("pair"):
        top_reasons = sorted(_skip_counts(group), key=lambda item: item["count"], reverse=True)[:5]
        rows.append(
            {
                "pair": pair,
                "candlesEvaluated": int(len(group)),
                "baseCandidateCount": int(group["ap_audit_base_candidate"].sum()),
                "finalEntryCount": int(group["ap_audit_final_entry"].sum()),
                "actualTradeCount": int(trade_counts.get(pair, 0)),
                "topSkipReasons": top_reasons,
                "filterStats": _filter_stats(group),
            }
        )
    return rows


def _monthly_breakdown(frame: Any, actual_trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    trade_months = Counter(str(trade.get("close_date", ""))[:7] for trade in actual_trades)
    working = frame.copy()
    working["month"] = working["date"].dt.strftime("%Y-%m")
    rows = []
    for month, group in working.groupby("month"):
        top_reasons = sorted(_skip_counts(group), key=lambda item: item["count"], reverse=True)[:5]
        rows.append(
            {
                "month": month,
                "candlesEvaluated": int(len(group)),
                "baseCandidateCount": int(group["ap_audit_base_candidate"].sum()),
                "finalEntryCount": int(group["ap_audit_final_entry"].sum()),
                "actualTradeCount": int(trade_months.get(month, 0)),
                "topSkipReasons": top_reasons,
            }
        )
    return rows


def _build_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    filter_stats = report["filterStats"]
    skip_counts = report["skipReasonCounts"]
    primary_skips = [item for item in skip_counts if item["skipReason"] not in {"entry_signal_passed"}]
    top_skip = max(primary_skips, key=lambda item: item["count"], default=None)
    filter_failures = [item for item in filter_stats if item["filterId"] != "data_ready"]
    most_blocking = max(filter_failures, key=lambda item: item["blockedAsPrimaryReason"], default=None)
    least_blocking = min(filter_failures, key=lambda item: item["blockedAsPrimaryReason"], default=None)
    data_missing = next((item for item in skip_counts if item["skipReason"] == "data_missing"), {"count": 0})
    final_entries = report["overall"]["finalEntryCount"]
    actual_trades = report["overall"]["actualTradeCount"]

    return [
        {
            "id": "filter_effectiveness_available",
            "severity": "info",
            "finding": "Filter effectiveness is available from offline OHLCV audit reconstruction.",
            "evidence": {"filterStatsCount": len(filter_stats), "skipReasonCount": len(skip_counts)},
        },
        {
            "id": "top_skip_reason",
            "severity": "medium",
            "finding": f"Most common primary skip reason is {top_skip['skipReason'] if top_skip else 'unavailable'}.",
            "evidence": top_skip,
        },
        {
            "id": "most_blocking_filter",
            "severity": "medium",
            "finding": f"Most blocking filter is {most_blocking['filterId'] if most_blocking else 'unavailable'}.",
            "evidence": most_blocking,
        },
        {
            "id": "least_blocking_filter",
            "severity": "medium",
            "finding": f"Least blocking filter is {least_blocking['filterId'] if least_blocking else 'unavailable'}.",
            "evidence": least_blocking,
        },
        {
            "id": "data_missing_check",
            "severity": "info" if data_missing.get("count", 0) == 0 else "medium",
            "finding": f"Data missing count is {data_missing.get('count', 0)}.",
            "evidence": data_missing,
        },
        {
            "id": "signal_to_trade_gap",
            "severity": "info",
            "finding": "Final entry signals and actual trades can differ because Freqtrade applies wallet, max-open-trade, and engine execution constraints.",
            "evidence": {"finalEntryCount": final_entries, "actualTradeCount": actual_trades},
        },
        {
            "id": "v02_design_ready",
            "severity": "info",
            "finding": "Signal audit evidence is now available for V0.2 candidate design, but parameters were not changed in V13.4.2.",
            "evidence": {"nextStep": "V13.4.3 Strategy V0.2 Candidate Design"},
        },
    ]


def _unavailable_report(backtest_report: dict[str, Any], reason: str) -> SignalAuditReport:
    actual_trade_count = backtest_report.get("metrics", {}).get("tradeCount")
    return SignalAuditReport(
        reportId="v13_4_2_signal_audit",
        strategyId=str(backtest_report.get("strategyId", "alpha_volume_rebound_v01")),
        sourceBacktestReport=str(DEFAULT_BACKTEST_REPORT),
        isMock=False,
        timerange=str(backtest_report.get("timerange", "unknown")),
        pairs=list(backtest_report.get("universe", [])),
        overall={
            "candlesEvaluated": None,
            "baseCandidateCount": None,
            "finalEntryCount": None,
            "actualTradeCount": actual_trade_count,
            "conversionRate": None,
            "filterEffectivenessAvailable": False,
            "reason": reason,
        },
        filterStats=[
            {
                "filterId": filter_id,
                "name": name,
                "passCount": 0,
                "failCount": 0,
                "passRate": None,
                "failRate": None,
                "blockedAsPrimaryReason": 0,
                "notes": "Unavailable in this run.",
            }
            for filter_id, name, _, _ in FILTER_DEFS
        ],
        skipReasonCounts=[{"skipReason": reason_id, "count": 0, "percentage": None} for reason_id in SKIP_REASONS],
        pairBreakdown=[],
        monthlyBreakdown=[],
        dataAvailability={"filterEffectivenessAvailable": False, "reason": reason},
        findings=[
            {
                "id": "filter_effectiveness_unavailable",
                "severity": "warning",
                "finding": "Filter effectiveness could not be calculated.",
                "evidence": reason,
            }
        ],
        warnings=[reason],
        generatedAt=_utc_now(),
    )


def _build_report(backtest_report_path: Path, data_dir: Path) -> SignalAuditReport:
    pd, _ = _import_pandas()
    backtest_report = _read_json(backtest_report_path)
    if backtest_report.get("isMock") is not False:
        raise ValueError("Signal audit requires an isMock=false backtest report.")

    source_result = Path(backtest_report.get("config", {}).get("sourceResult", ""))
    source_payload = _load_backtest_payload(source_result) if source_result.exists() else {}
    actual_trades = list(source_payload.get("trades", backtest_report.get("trades", [])))
    pairs = sorted({trade.get("pair") for trade in actual_trades if trade.get("pair")})
    if not pairs:
        pairs = list(backtest_report.get("universe", []))

    btc_frame = _add_core_indicators(_load_ohlcv(data_dir, "BTC/USDT:USDT", "15m"))
    start = pd.to_datetime(source_payload.get("backtest_start", "2026-04-03 17:00:00"), utc=True)
    end = pd.to_datetime(source_payload.get("backtest_end", "2026-07-04 16:45:00"), utc=True)

    audited_frames = [_audit_pair(data_dir, pair, btc_frame, start, end) for pair in pairs]
    frame = pd.concat(audited_frames, ignore_index=True) if audited_frames else pd.DataFrame()
    candles = int(len(frame))
    base_candidates = int(frame["ap_audit_base_candidate"].sum()) if candles else 0
    final_entries = int(frame["ap_audit_final_entry"].sum()) if candles else 0
    actual_trade_count = int(backtest_report.get("metrics", {}).get("tradeCount") or len(actual_trades))

    report_dict = {
        "overall": {
            "candlesEvaluated": candles,
            "baseCandidateCount": base_candidates,
            "finalEntryCount": final_entries,
            "actualTradeCount": actual_trade_count,
            "conversionRate": _round(final_entries / base_candidates * 100 if base_candidates else None),
            "filterEffectivenessAvailable": True,
        },
        "filterStats": _filter_stats(frame),
        "skipReasonCounts": _skip_counts(frame),
        "pairBreakdown": _pair_breakdown(frame, actual_trades),
        "monthlyBreakdown": _monthly_breakdown(frame, actual_trades),
    }
    findings = _build_findings(report_dict)

    return SignalAuditReport(
        reportId="v13_4_2_signal_audit",
        strategyId=str(backtest_report.get("strategyId", "alpha_volume_rebound_v01")),
        sourceBacktestReport=str(backtest_report_path),
        isMock=False,
        timerange=str(backtest_report.get("timerange", "unknown")),
        pairs=pairs,
        overall=report_dict["overall"],
        filterStats=report_dict["filterStats"],
        skipReasonCounts=report_dict["skipReasonCounts"],
        pairBreakdown=report_dict["pairBreakdown"],
        monthlyBreakdown=report_dict["monthlyBreakdown"],
        dataAvailability={
            "filterEffectivenessAvailable": True,
            "dataDir": str(data_dir),
            "sourceResult": str(source_result),
            "method": "offline_reconstruction_from_freqtrade_feather_data",
        },
        findings=findings,
        warnings=[
            "Audit counts are reconstructed from local OHLCV data and strategy-equivalent conditions.",
            "Final entry signals may differ from actual trade count due Freqtrade wallet, max-open-trade, and engine constraints.",
            "No strategy parameters were changed by V13.4.2.",
        ],
        generatedAt=_utc_now(),
    )


def _write_summary(report: dict[str, Any], path: Path) -> None:
    top_skip = max(
        [item for item in report["skipReasonCounts"] if item["skipReason"] != "entry_signal_passed"],
        key=lambda item: item["count"],
        default={"skipReason": "unavailable", "count": 0},
    )
    least_filter = min(
        [item for item in report["filterStats"] if item["filterId"] != "data_ready"],
        key=lambda item: item["blockedAsPrimaryReason"],
        default={"filterId": "unavailable", "blockedAsPrimaryReason": 0},
    )
    lines = [
        "# V13.4.2 Signal Audit Summary",
        "",
        "## Conclusion",
        "",
        "V13.4.2 adds signal audit instrumentation and does not tune strategy parameters or enter Dry-run.",
        "",
        "## Overall",
        "",
        f"- Candles evaluated: {report['overall'].get('candlesEvaluated')}",
        f"- Base candidate count: {report['overall'].get('baseCandidateCount')}",
        f"- Final entry count: {report['overall'].get('finalEntryCount')}",
        f"- Actual trade count: {report['overall'].get('actualTradeCount')}",
        f"- Conversion rate: {report['overall'].get('conversionRate')}%",
        f"- Filter effectiveness available: {report['overall'].get('filterEffectivenessAvailable')}",
        "",
        "## Skip Reasons",
        "",
    ]
    lines.extend(f"- {item['skipReason']}: {item['count']} ({item['percentage']}%)" for item in report["skipReasonCounts"])
    lines.extend(
        [
            "",
            "## Filter Stats",
            "",
        ]
    )
    lines.extend(
        f"- {item['filterId']}: pass={item['passCount']}, fail={item['failCount']}, primaryBlocks={item['blockedAsPrimaryReason']}"
        for item in report["filterStats"]
    )
    lines.extend(
        [
            "",
            "## Pair Breakdown",
            "",
        ]
    )
    lines.extend(
        f"- {item['pair']}: candles={item['candlesEvaluated']}, base={item['baseCandidateCount']}, final={item['finalEntryCount']}, trades={item['actualTradeCount']}"
        for item in report["pairBreakdown"]
    )
    lines.extend(
        [
            "",
            "## Main Findings",
            "",
            f"- Most common skip reason: {top_skip['skipReason']} ({top_skip['count']})",
            f"- Least primary-blocking filter: {least_filter['filterId']} ({least_filter['blockedAsPrimaryReason']})",
            "- V13.4.2 cannot approve Dry-run; it only prepares evidence for V13.4.3 strategy design.",
            "",
            "## Safety",
            "",
            "This audit reads local backtest and OHLCV files only. It does not use API keys, call Trade API or Withdraw API, read accounts, create orders, execute Dry-run, or auto trade.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_signal_audit(
    backtest_report_path: Path,
    output_json: Path,
    output_summary: Path,
    data_dir: Path,
) -> tuple[Path, Path]:
    backtest_report = _read_json(backtest_report_path)
    try:
        report = _build_report(backtest_report_path, data_dir)
    except Exception as exc:  # Keep report explicit instead of fabricating counts.
        report = _unavailable_report(backtest_report, f"{type(exc).__name__}: {exc}")

    report_dict = report.to_dict()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report_dict, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(report_dict, output_summary)
    return output_json, output_summary


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    _maybe_rerun_in_docker(argv)

    parser = argparse.ArgumentParser(description="Generate AlphaPilot V13.4.2 signal audit report.")
    parser.add_argument("--backtest-report", type=Path, default=DEFAULT_BACKTEST_REPORT)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DATA_DIR)
    parser.add_argument("--no-docker-fallback", action="store_true")
    args = parser.parse_args(argv)

    output_json, output_summary = export_signal_audit(
        args.backtest_report,
        args.output_json,
        args.output_summary,
        args.data_dir,
    )
    print(f"Exported signal audit report: {output_json}")
    print(f"Exported signal audit summary: {output_summary}")


if __name__ == "__main__":
    main()
