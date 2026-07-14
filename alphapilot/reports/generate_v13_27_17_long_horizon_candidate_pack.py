"""Generate the V13.27.17 1h/4h/1d five-candidate research packs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from alphapilot.low_frequency.long_horizon_candidate_pack import (
    TIMEFRAMES,
    build_long_horizon_candidate_specs,
    build_long_horizon_report,
    classify_event_window_prescreen_result,
    classify_research_evidence,
    deterministic_symbol_split,
)
from alphapilot.low_frequency.strategy_candidate_factory import (
    StrategyCandidateSpec,
    _candidate_specs,
    _load_prepared_frames,
    _metrics,
    _simulate_candidate,
    _walk_forward_metrics,
)
from alphapilot.short_cycle.event_window_candidates import (
    one_hour_factor_successor_candidate_pool,
)
from alphapilot.short_cycle.event_window_research import (
    EventWindowPrescreenConfig,
    run_event_window_prescreen,
)


DEFAULT_DATA_PATH = Path("user_data/data/okx/futures")
DEFAULT_SHORT_CYCLE_PRESCREEN = Path(
    "reports/v13_27_16_event_window_prescreen.json"
)
DEFAULT_OUTPUT = Path("reports/v13_27_17_long_horizon_candidate_pack.json")
DEFAULT_SUMMARY = Path("reports/v13_27_17_long_horizon_candidate_pack_summary.md")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _before_locked_window(trades: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    locked_start = pd.Timestamp("2025-01-01", tz="UTC")
    selected: list[dict[str, Any]] = []
    for trade in trades:
        entry = pd.Timestamp(str(trade["entryTimestamp"]))
        exit_time = pd.Timestamp(str(trade["exitTimestamp"]))
        if entry < locked_start and exit_time < locked_start:
            selected.append(dict(trade))
    return selected


def _positive(metrics: Mapping[str, Any], *, minimum_trades: int) -> bool:
    return (
        int(metrics.get("tradeCount") or 0) >= minimum_trades
        and float(metrics.get("profitFactor") or 0) > 1.0
        and float(metrics.get("totalReturnPct") or 0) > 0
    )


def _strategy_candidate_from_spec(spec: Mapping[str, Any]) -> StrategyCandidateSpec:
    parameters = dict(spec["parameters"])
    return StrategyCandidateSpec(
        candidate_id=str(spec["candidateId"]),
        display_name=str(spec["displayName"]),
        family=str(spec["family"]),
        timeframe=str(spec["timeframe"]),
        btc_regimes=tuple(parameters.pop("btc_regimes")),
        atr_multiplier=float(parameters.pop("atr_multiplier")),
        max_hold_bars=int(parameters.pop("max_hold_bars")),
        min_volume_ratio=float(parameters.pop("min_volume_ratio")),
        **parameters,
    )


def _screen_low_frequency_specs(
    specs: list[dict[str, Any]],
    *,
    data_path: Path,
    timerange: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for timeframe in ("4h", "1d"):
        timeframe_specs = [item for item in specs if item["timeframe"] == timeframe]
        config, prepared, warnings = _load_prepared_frames(data_path, timerange, timeframe)
        if warnings and not prepared:
            raise RuntimeError("; ".join(warnings))
        pair_split = deterministic_symbol_split(tuple(prepared))
        minimum_total = 60 if timeframe == "4h" else 25
        minimum_split = 10 if timeframe == "4h" else 4
        for item in timeframe_specs:
            if timeframe == "1d":
                legacy_id = str(item["parameters"]["legacy_candidate_id"])
                candidate_spec = next(
                    candidate
                    for candidate in _candidate_specs()
                    if candidate.candidate_id == legacy_id
                )
            else:
                candidate_spec = _strategy_candidate_from_spec(item)

            trades = _simulate_candidate(candidate_spec, prepared)
            selection_trades = _before_locked_window(trades)
            development_trades = [
                trade
                for trade in selection_trades
                if str(trade["pair"]) in pair_split["development"]
            ]
            holdback_trades = [
                trade
                for trade in selection_trades
                if str(trade["pair"]) in pair_split["holdback"]
            ]
            selection_metrics = _metrics(selection_trades, config)
            development_metrics = _metrics(development_trades, config)
            holdback_metrics = _metrics(holdback_trades, config)
            walk_forward = _walk_forward_metrics(trades, config)
            splits = {split["splitId"]: split for split in walk_forward}
            train = splits.get("train_2020_2022", {})
            validation = splits.get("validation_2023_2024", {})
            locked = splits.get("test_2025_2026", {})
            checks = {
                "targetRAtLeastTwo": float(item["targetR"]) >= 2.0,
                "selectionTradeCount": int(selection_metrics.get("tradeCount") or 0) >= minimum_total,
                "selectionProfitFactor": float(selection_metrics.get("profitFactor") or 0) >= 1.15,
                "selectionReturnPositive": float(selection_metrics.get("totalReturnPct") or 0) > 0,
                "selectionDrawdownAtMost30Pct": float(selection_metrics.get("maxDrawdownPct") or 999) <= 30,
                "developmentTimePositive": _positive(train, minimum_trades=minimum_split),
                "temporalValidationPositive": _positive(validation, minimum_trades=minimum_split),
                "developmentSymbolsPositive": _positive(development_metrics, minimum_trades=minimum_split),
                "symbolHoldbackPositive": _positive(holdback_metrics, minimum_trades=minimum_split),
            }
            evidence = classify_research_evidence(
                {
                    **item,
                    "metrics": selection_metrics,
                    "selectionChecks": checks,
                    "selectionScore": round(
                        float(selection_metrics.get("profitFactor") or 0) * 100
                        + float(selection_metrics.get("totalReturnPct") or 0)
                        - float(selection_metrics.get("maxDrawdownPct") or 0),
                        6,
                    ),
                    "symbolSplit": pair_split,
                    "developmentSymbolMetrics": development_metrics,
                    "symbolHoldbackMetrics": holdback_metrics,
                    "timeSplitMetrics": {
                        "developmentTrain": train,
                        "temporalValidation": validation,
                    },
                    "lockedEvidence": locked,
                    "dataWarnings": warnings,
                }
            )
            rows.append(evidence)
    return rows


def _screen_one_hour_candidates(
    prescreen_config_report: Mapping[str, Any],
) -> list[dict[str, Any]]:
    config_values = dict(prescreen_config_report["config"])
    config = EventWindowPrescreenConfig(
        canonicalRoot=Path(str(config_values["canonicalRoot"])),
        derivationSymbols=tuple(config_values["derivationSymbols"]),
        holdbackSymbols=tuple(config_values["holdbackSymbols"]),
        trainStart=str(config_values["trainStart"]),
        trainEnd=str(config_values["trainEnd"]),
        validationEnd=str(config_values["validationEnd"]),
        targetR=float(config_values["targetR"]),
        feeRate=float(config_values["feeRate"]),
        slippageRate=float(config_values["slippageRate"]),
    )
    candidates = one_hour_factor_successor_candidate_pool()
    direct_report = run_event_window_prescreen(candidates, config)
    direct_by_key = {
        str(item["candidateKey"]): item for item in direct_report["results"]
    }
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        rows.append(
            classify_event_window_prescreen_result(
                {
                    "candidateId": candidate.familyKey,
                    "displayName": candidate.displayName,
                    "timeframe": candidate.timeframe,
                    "family": candidate.signalFamily,
                    "direction": candidate.direction,
                    "targetR": config.targetR,
                    "correlationGroup": f"1h_{candidate.signalFamily}",
                    "evidenceLineage": "v13_27_17_direct_event_factor_prescreen",
                    "parameters": dict(candidate.parameters),
                    "researchMetadata": dict(candidate.researchMetadata or {}),
                    "researchOnly": True,
                    "executionEnabled": False,
                },
                direct_by_key[candidate.familyKey],
            )
        )
    return rows


def render_summary(report: Mapping[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# AlphaPilot V13.27.17 Long-Horizon Candidate Pack",
        "",
        "本报告为研究筛选，不代表盈利承诺，不创建 Demo/Live Release，也不下单。",
        "候选数量与正式资格严格分开；锁定段只报告，不参与选择。",
        "",
        "## Summary",
        "",
        f"- selectedCandidateCount: {summary['selectedCandidateCount']}",
        f"- selectedByTimeframe: {summary['selectedByTimeframe']}",
        f"- researchEligibleByTimeframe: {summary['researchEligibleByTimeframe']}",
        f"- shadowOnlyByTimeframe: {summary['shadowOnlyByTimeframe']}",
        f"- rejectedByTimeframe: {summary['rejectedByTimeframe']}",
        "- targetR: 2.0",
        "",
    ]
    for timeframe in TIMEFRAMES:
        lines.extend([f"## {timeframe.upper()} Candidates", ""])
        lines.append("| Candidate | Tier | PF | Trades | Failed checks | Correlation group |")
        lines.append("| --- | --- | ---: | ---: | --- | --- |")
        for item in report["candidatePacks"][timeframe]:
            metrics = item.get("metrics") or {}
            lines.append(
                "| {name} | {tier} | {pf} | {trades} | {failed} | {group} |".format(
                    name=item["displayName"],
                    tier=item["selectionTier"],
                    pf=metrics.get("profitFactor", "--"),
                    trades=metrics.get("tradeCount", "--"),
                    failed=", ".join(item.get("failedSelectionChecks") or []) or "--",
                    group=item.get("correlationGroup", "--"),
                )
            )
        lines.append("")
    lines.extend(
        [
            "## Interpretation",
            "",
            "- 1H 候选采用事件窗口、可选确认计分和透明市场状态因子，避免把所有条件硬塞进同一根 K 线。",
            "- 1H 表格中的 PF/样本来自候选自身的直接三段预筛；未通过者保持影子或拒绝，不借用旧家族指标。",
            "- 4H 候选隔离 BTC 牛市状态下的回踩收回结构；同组参数变体高度相关，不能视为五种独立风险来源。",
            "- 1D 候选复核既有低频定义；即使 research_eligible，也仍需独立前向与 Demo 证据才能晋级。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-path", default=DEFAULT_DATA_PATH.as_posix())
    parser.add_argument("--timerange", default="20200101-")
    parser.add_argument(
        "--short-cycle-prescreen",
        default=DEFAULT_SHORT_CYCLE_PRESCREEN.as_posix(),
    )
    parser.add_argument("--output", default=DEFAULT_OUTPUT.as_posix())
    parser.add_argument("--summary", default=DEFAULT_SUMMARY.as_posix())
    args = parser.parse_args()

    specs = list(build_long_horizon_candidate_specs())
    rows = _screen_one_hour_candidates(
        _load_json(Path(args.short_cycle_prescreen)),
    )
    rows.extend(
        _screen_low_frequency_specs(
            specs,
            data_path=Path(args.data_path),
            timerange=args.timerange,
        )
    )
    report = build_long_horizon_report(rows)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    summary_path = Path(args.summary)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(render_summary(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
