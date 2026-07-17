"""Atomic V18 formal campaign execution and evidence publication."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic

from .candidate_adapter import CandidateAdapter, validate_candidate_binding
from .formal_event_contract import canonicalize_formal_event
from .formal_input import FormalInputBundle
from .formal_statistics import newey_west_alpha
from .formal_stress import (
    build_funding_stress,
    build_s01_benchmark,
    build_utc_daily_returns,
)
from .formal_walk_forward import assign_events_to_folds
from .v18_formal_execution import (
    attach_point_in_time_context,
    build_daily_market_evidence,
    build_locked_cost_stress,
    build_signal_feature_evidence,
    compare_capital_replays,
    replay_v18_capital_policy,
    summarize_capital_replay,
)


ParityRunner = Callable[..., tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]]
RawReplayRunner = Callable[..., Sequence[Mapping[str, Any]]]


def _utc_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    return (
        timestamp.tz_localize("UTC")
        if timestamp.tzinfo is None
        else timestamp.tz_convert("UTC")
    )


def _utc_iso(value: object) -> str:
    return _utc_timestamp(value).isoformat().replace("+00:00", "Z")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (pd.Timestamp, np.datetime64)):
        return _utc_iso(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _manifest_hash(rows: Sequence[Mapping[str, Any]]) -> str:
    canonical = json.dumps(
        _jsonable(list(rows)),
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(canonical).hexdigest()


def _signal_id(event: Mapping[str, Any]) -> str:
    existing = str(event.get("signalId") or "").strip()
    if existing:
        return existing
    return str(canonicalize_formal_event(event)["signalId"])


def _merge_canonical_events(
    canonical_events: Sequence[Mapping[str, Any]],
    assigned_raw: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], list[str]]:
    raw_by_id = {_signal_id(row): dict(row) for row in assigned_raw}
    merged: list[dict[str, Any]] = []
    missing: list[str] = []
    for canonical in canonical_events:
        signal_id = str(canonical.get("signalId") or "")
        raw = raw_by_id.get(signal_id)
        if raw is None:
            missing.append(signal_id)
            continue
        merged.append(
            {
                **raw,
                **dict(canonical),
                "signalId": signal_id,
                "symbol": str(canonical["symbol"]),
                "instrumentId": str(canonical["symbol"]),
                "stopPrice": float(canonical["initialStop"]),
                "exitLegs": [dict(row) for row in canonical["exitLegs"]],
                "foldId": str(raw["foldId"]),
            }
        )
    return merged, missing


def _metrics_for_trades(
    trades: Sequence[Mapping[str, Any]], *, initial_equity: float
) -> dict[str, Any]:
    ordered = sorted(
        (dict(row) for row in trades),
        key=lambda row: (_utc_timestamp(row["exitTimestamp"]), str(row["signalId"])),
    )
    equity = float(initial_equity)
    curve: list[dict[str, Any]] = [
        {"timestamp": None, "equity": equity, "positionCount": 0}
    ]
    for row in ordered:
        equity += float(row.get("netPnl") or 0.0)
        curve.append(
            {
                "timestamp": _utc_iso(row["exitTimestamp"]),
                "equity": equity,
                "positionCount": 0,
            }
        )
    return summarize_capital_replay(
        {
            "initialEquity": float(initial_equity),
            "finalEquity": equity,
            "trades": ordered,
            "equityCurve": curve,
        }
    )


def _fold_results(
    preregistration: Mapping[str, Any], replay: Mapping[str, Any]
) -> list[dict[str, Any]]:
    initial = float(replay["initialEquity"])
    by_fold: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in replay.get("trades", []):
        by_fold[str(row.get("foldId") or "unassigned")].append(dict(row))
    return [
        {
            "foldId": str(fold["foldId"]),
            **_metrics_for_trades(
                by_fold.get(str(fold["foldId"]), []),
                initial_equity=initial,
            ),
        }
        for fold in preregistration["splitPolicy"]["folds"]
    ]


def _daily_return_panel(
    *,
    trades: Sequence[Mapping[str, Any]],
    benchmark: Mapping[str, Any],
    start: str,
    cutoff_exclusive: str,
    initial_equity: float,
) -> pd.DataFrame:
    candidate = build_utc_daily_returns(
        trades,
        start=start,
        cutoff_exclusive=cutoff_exclusive,
        initial_equity=initial_equity,
    ).rename(columns={"netReturn": "candidateReturn", "netPnl": "candidateNetPnl"})
    benchmark_pnl: dict[pd.Timestamp, float] = defaultdict(float)
    risk_by_id = {
        str(row["signalId"]): float(row.get("riskAmount") or 0.0) for row in trades
    }
    for row in benchmark.get("events", []):
        day = _utc_timestamp(row["benchmarkExitTimestamp"]).floor("D")
        benchmark_pnl[day] += risk_by_id.get(str(row["signalId"]), 0.0) * float(
            row["benchmarkNetR"]
        )
    equity = float(initial_equity)
    benchmark_returns: list[float] = []
    benchmark_pnls: list[float] = []
    for day in pd.DatetimeIndex(candidate["date"]):
        pnl = float(benchmark_pnl.get(_utc_timestamp(day).floor("D"), 0.0))
        benchmark_returns.append(pnl / equity if equity else 0.0)
        benchmark_pnls.append(pnl)
        equity += pnl
    candidate["benchmarkNetPnl"] = benchmark_pnls
    candidate["benchmarkReturn"] = benchmark_returns
    candidate["differentialReturn"] = (
        candidate["candidateReturn"] - candidate["benchmarkReturn"]
    )
    return candidate


def _registered_funding_rate(bundle: FormalInputBundle) -> float | None:
    cost = bundle.preregistration.get("costModel") or {}
    stress = cost.get("conservativeFundingStress") or {}
    value = stress.get("adverseRatePerSettlement")
    if value is None:
        value = bundle.snapshot.get("adverseFundingRatePerSettlement")
    if value is None:
        return None
    rate = float(value)
    return rate if math.isfinite(rate) and rate >= 0.0 else None


def _funding_metrics(
    funding: Mapping[str, Any], trades: Sequence[Mapping[str, Any]]
) -> dict[str, Any] | None:
    if funding.get("gateEvaluable") is not True:
        return None
    trade_by_id = {str(row["signalId"]): dict(row) for row in trades}
    repriced: list[dict[str, Any]] = []
    for row in funding.get("events", []):
        source = trade_by_id.get(str(row["signalId"]))
        if source is None:
            continue
        net_r = float(row["conservativeFundingNetR"])
        risk = float(source["riskAmount"])
        repriced.append(
            {
                **source,
                "realizedNetR": net_r,
                "netPnl": risk * net_r,
            }
        )
    return _metrics_for_trades(
        repriced,
        initial_equity=float(trades[0].get("equityAtEntry") or 10_000.0)
        if trades
        else 10_000.0,
    )


def _unavailable_statistic(name: str, reason: str) -> dict[str, Any]:
    return {
        "schemaVersion": f"s01_v18_{name}_v1",
        "status": "unavailable_predeclared",
        "reason": reason,
        "retroactiveConstructionAllowed": False,
        "statisticalAdmissionBlocked": True,
    }


def _uncertainty_intervals(trades: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = np.asarray(
        [float(row.get("realizedNetR") or 0.0) for row in trades], dtype="float64"
    )
    if len(values) < 2:
        return {
            "schemaVersion": "s01_v18_uncertainty_intervals_v1",
            "status": "insufficient_sample",
            "sampleCount": int(len(values)),
            "averageNetR95Pct": None,
        }
    generator = np.random.default_rng(1801)
    means = np.asarray(
        [generator.choice(values, size=len(values), replace=True).mean() for _ in range(2000)]
    )
    lower, upper = np.quantile(means, [0.025, 0.975])
    return {
        "schemaVersion": "s01_v18_uncertainty_intervals_v1",
        "status": "available",
        "sampleCount": int(len(values)),
        "method": "deterministic_trade_bootstrap",
        "seed": 1801,
        "averageNetR95Pct": {"lower": float(lower), "upper": float(upper)},
    }


def _gate_row(
    gate_id: str,
    *,
    actual: Any,
    threshold: Any,
    passed: bool | None,
    reason: str | None = None,
) -> dict[str, Any]:
    return {
        "gateId": gate_id,
        "actual": actual,
        "threshold": threshold,
        "status": "not_evaluable" if passed is None else ("passed" if passed else "failed"),
        "passed": passed,
        "reason": reason,
    }


def _build_gate_matrix(
    *,
    bundle: FormalInputBundle,
    parity: Mapping[str, Any],
    capital_parity: Mapping[str, Any],
    ranking_audit: Mapping[str, Any],
    context_audit: Mapping[str, Any],
    fold_assignment: Mapping[str, Any],
    fold_results: Sequence[Mapping[str, Any]],
    base_metrics: Mapping[str, Any],
    cost_stress: Mapping[str, Any],
    funding: Mapping[str, Any],
    funding_metrics: Mapping[str, Any] | None,
    benchmark: Mapping[str, Any],
) -> dict[str, Any]:
    gates = bundle.preregistration.get("gates") or {}
    economic = gates.get("economic") or {}
    risk = gates.get("riskAndEvidence") or {}
    cost_by_id = {str(row["scenarioId"]): row for row in cost_stress["scenarios"]}
    cost_1_5x = cost_by_id["cost_1_5x"]["metrics"]
    profit_factor = base_metrics.get("profitFactor")
    cost_profit_factor = cost_1_5x.get("profitFactor")
    rows = [
        _gate_row(
            "translation_parity",
            actual=parity.get("identityParityPct"),
            threshold=float(risk.get("translationParity", 1.0)) * 100.0,
            passed=bool(parity.get("passed")),
        ),
        _gate_row(
            "capital_policy_parity",
            actual=capital_parity.get("capitalAcceptanceParityPct"),
            threshold=100.0,
            passed=bool(capital_parity.get("passed")),
        ),
        _gate_row(
            "ranking_evidence_complete",
            actual=int(ranking_audit.get("missingRankingFieldCount", 0)),
            threshold=0,
            passed=int(ranking_audit.get("missingRankingFieldCount", 0)) == 0,
        ),
        _gate_row(
            "point_in_time_context_complete",
            actual=int(context_audit.get("missingContextFieldCount", 0)),
            threshold=0,
            passed=int(context_audit.get("missingContextFieldCount", 0)) == 0,
        ),
        _gate_row(
            "fold_assignment_complete",
            actual=int(fold_assignment.get("rejectedEventCount", 0)),
            threshold=0,
            passed=int(fold_assignment.get("rejectedEventCount", 0)) == 0,
        ),
        _gate_row(
            "complete_fold_count",
            actual=len(fold_results),
            threshold=int(economic.get("completeFoldCount", len(fold_results))),
            passed=len(fold_results)
            == int(economic.get("completeFoldCount", len(fold_results))),
        ),
        _gate_row(
            "minimum_profit_factor",
            actual=profit_factor,
            threshold=float(economic.get("profitFactorMinimum", 1.05)),
            passed=(
                None
                if profit_factor is None
                else float(profit_factor)
                >= float(economic.get("profitFactorMinimum", 1.05))
            ),
            reason="undefined_no_losses" if profit_factor is None else None,
        ),
        _gate_row(
            "positive_average_net_r",
            actual=base_metrics.get("averageNetR"),
            threshold=float(economic.get("averageNetRMinimumExclusive", 0.0)),
            passed=float(base_metrics.get("averageNetR") or 0.0)
            > float(economic.get("averageNetRMinimumExclusive", 0.0)),
        ),
        _gate_row(
            "positive_total_net_r",
            actual=base_metrics.get("totalNetR"),
            threshold=float(economic.get("totalNetRMinimumExclusive", 0.0)),
            passed=float(base_metrics.get("totalNetR") or 0.0)
            > float(economic.get("totalNetRMinimumExclusive", 0.0)),
        ),
        _gate_row(
            "maximum_drawdown",
            actual=base_metrics.get("maximumDrawdownPercent"),
            threshold=float(economic.get("maximumDrawdownPercent", 25.0)),
            passed=float(base_metrics.get("maximumDrawdownPercent") or 0.0)
            <= float(economic.get("maximumDrawdownPercent", 25.0)),
        ),
        _gate_row(
            "positive_fold_minimum",
            actual=sum(float(row.get("totalNetR") or 0.0) > 0.0 for row in fold_results),
            threshold=int(economic.get("positiveFoldMinimum", 0)),
            passed=sum(float(row.get("totalNetR") or 0.0) > 0.0 for row in fold_results)
            >= int(economic.get("positiveFoldMinimum", 0)),
        ),
        _gate_row(
            "cost_1_5x_profit_factor",
            actual=cost_profit_factor,
            threshold=float(economic.get("cost1_5xProfitFactorMinimum", 1.0)),
            passed=(
                None
                if cost_profit_factor is None
                else float(cost_profit_factor)
                >= float(economic.get("cost1_5xProfitFactorMinimum", 1.0))
            ),
            reason="undefined_no_losses" if cost_profit_factor is None else None,
        ),
        _gate_row(
            "cost_1_5x_average_net_r",
            actual=cost_1_5x.get("averageNetR"),
            threshold=float(economic.get("cost1_5xAverageNetRMinimumExclusive", 0.0)),
            passed=float(cost_1_5x.get("averageNetR") or 0.0)
            > float(economic.get("cost1_5xAverageNetRMinimumExclusive", 0.0)),
        ),
        _gate_row(
            "cost_1_5x_total_net_r",
            actual=cost_1_5x.get("totalNetR"),
            threshold=float(economic.get("cost1_5xTotalNetRMinimumExclusive", 0.0)),
            passed=float(cost_1_5x.get("totalNetR") or 0.0)
            > float(economic.get("cost1_5xTotalNetRMinimumExclusive", 0.0)),
        ),
        _gate_row(
            "conservative_funding_average_net_r",
            actual=(funding_metrics or {}).get("averageNetR"),
            threshold=float(
                economic.get("conservativeFundingAverageNetRMinimumExclusive", 0.0)
            ),
            passed=(
                None
                if funding.get("gateEvaluable") is not True
                else float((funding_metrics or {}).get("averageNetR") or 0.0)
                > float(
                    economic.get(
                        "conservativeFundingAverageNetRMinimumExclusive", 0.0
                    )
                )
            ),
            reason=(
                "registered_same_exchange_funding_history_unavailable"
                if funding.get("gateEvaluable") is not True
                else None
            ),
        ),
        _gate_row(
            "benchmark_total_incremental_net_r",
            actual=benchmark.get("totalIncrementalNetR"),
            threshold=float(
                economic.get("benchmarkTotalIncrementalNetRMinimumExclusive", 0.0)
            ),
            passed=float(benchmark.get("totalIncrementalNetR") or 0.0)
            > float(
                economic.get("benchmarkTotalIncrementalNetRMinimumExclusive", 0.0)
            ),
        ),
        _gate_row(
            "benchmark_positive_increment_fold_minimum",
            actual=benchmark.get("positiveIncrementFoldCount"),
            threshold=int(economic.get("benchmarkPositiveIncrementFoldMinimum", 0)),
            passed=int(benchmark.get("positiveIncrementFoldCount") or 0)
            >= int(economic.get("benchmarkPositiveIncrementFoldMinimum", 0)),
        ),
        _gate_row(
            "single_symbol_concentration",
            actual=base_metrics.get("maximumSingleSymbolPositiveContribution"),
            threshold=float(risk.get("maximumSingleSymbolPositiveContribution", 0.35)),
            passed=float(
                base_metrics.get("maximumSingleSymbolPositiveContribution") or 0.0
            )
            <= float(risk.get("maximumSingleSymbolPositiveContribution", 0.35)),
        ),
        _gate_row(
            "single_month_concentration",
            actual=base_metrics.get("maximumSingleMonthPositiveContribution"),
            threshold=float(risk.get("maximumSingleMonthPositiveContribution", 0.35)),
            passed=float(
                base_metrics.get("maximumSingleMonthPositiveContribution") or 0.0
            )
            <= float(risk.get("maximumSingleMonthPositiveContribution", 0.35)),
        ),
    ]
    return {
        "schemaVersion": "s01_v18_formal_gate_matrix_v1",
        "gates": rows,
        "passedCount": sum(row["passed"] is True for row in rows),
        "failedCount": sum(row["passed"] is False for row in rows),
        "notEvaluableCount": sum(row["passed"] is None for row in rows),
    }


def _route(
    *,
    bundle: FormalInputBundle,
    gate_matrix: Mapping[str, Any],
    implementation_blockers: Sequence[str],
) -> tuple[str, list[str]]:
    stopping = bundle.preregistration.get("stoppingRules") or {}
    blockers = list(dict.fromkeys(str(value) for value in implementation_blockers))
    if blockers:
        return str(
            stopping.get("implementationInvalid")
            or "implementation_invalid_requires_new_campaign"
        ), blockers
    economic_gate_ids = {
        "complete_fold_count",
        "minimum_profit_factor",
        "positive_average_net_r",
        "positive_total_net_r",
        "maximum_drawdown",
        "positive_fold_minimum",
        "cost_1_5x_profit_factor",
        "cost_1_5x_average_net_r",
        "cost_1_5x_total_net_r",
        "conservative_funding_average_net_r",
        "benchmark_total_incremental_net_r",
        "benchmark_positive_increment_fold_minimum",
    }
    failed = [
        str(row["gateId"])
        for row in gate_matrix["gates"]
        if row["gateId"] in economic_gate_ids and row["passed"] is not True
    ]
    if failed:
        return str(stopping.get("economicGateFailure") or "archive_s01_current_version"), failed
    comparable = (
        bundle.preregistration.get("statisticalPolicy", {}).get(
            "comparableCandidatePanel", {}
        )
    )
    if comparable.get("status") == "unavailable_predeclared":
        return str(
            stopping.get("statisticsUnavailable")
            or "walk_forward_research_pass_statistics_unavailable"
        ), ["comparable_candidate_panel_unavailable_predeclared"]
    return "walk_forward_research_pass_no_clean_holdout", ["clean_locked_oos_unavailable"]


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    blockers = "\n".join(f"- `{value}`" for value in summary["blockers"])
    return (
        "# V13.27.1.18 S01 Formal Walk-forward Summary\n\n"
        f"- Campaign: `{summary['campaignId']}`\n"
        f"- Route: `{summary['route']}`\n"
        f"- Base accepted trades: {summary['baseAcceptedTradeCount']}\n"
        f"- Locked OOS reads: {summary['lockedOosAccessCount']}\n"
        "- Release / Demo ARM / orders: 0 / false / 0\n\n"
        "## Blockers\n\n"
        f"{blockers}\n\n"
        "This is research evidence only. It does not create a Release or trading order.\n"
    )


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    columns = [
        "foldId",
        "tradeCount",
        "winCount",
        "lossCount",
        "profitFactor",
        "averageNetR",
        "totalNetR",
        "netPnl",
        "netReturnPercent",
        "maximumDrawdownPercent",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(_jsonable(list(rows)))


def _publish_artifacts(
    output_root: Path,
    *,
    json_payloads: Mapping[str, Any],
    markdown_payloads: Mapping[str, str],
    parquet_payloads: Mapping[str, pd.DataFrame],
    csv_payloads: Mapping[str, Sequence[Mapping[str, Any]]],
    campaign_id: str,
    candidate_id: str,
    candidate_adapter: CandidateAdapter,
    route: str,
) -> str:
    destination = Path(output_root).resolve()
    destination.mkdir(parents=True, exist_ok=True)
    staging = destination / f".v18-formal-staging-{uuid.uuid4().hex}"
    staging.mkdir(parents=False, exist_ok=False)
    try:
        for name, payload in json_payloads.items():
            write_json_atomic(staging / name, _jsonable(payload))
        for name, content in markdown_payloads.items():
            (staging / name).write_text(content, encoding="utf-8", newline="\n")
        for name, frame in parquet_payloads.items():
            frame.to_parquet(staging / name, index=False)
        for name, rows in csv_payloads.items():
            _write_csv(staging / name, rows)
        artifacts = [
            {
                "path": path.name,
                "sizeBytes": path.stat().st_size,
                "sha256": _sha256(path),
            }
            for path in sorted(staging.iterdir(), key=lambda item: item.name)
            if path.is_file()
        ]
        result_manifest_hash = _manifest_hash(artifacts)
        manifest = {
            "schemaVersion": "s01_v18_formal_artifact_manifest_v1",
            "campaignId": campaign_id,
            "candidateId": candidate_id,
            "candidateAdapter": {
                "adapterId": candidate_adapter.adapter_id,
                "adapterVersion": candidate_adapter.adapter_version,
            },
            "route": route,
            "artifacts": artifacts,
            "resultManifestHash": result_manifest_hash,
            "publishedLast": True,
            "lockedOosAccessCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        }
        write_json_atomic(staging / "artifact_manifest.json", manifest)
        for path in sorted(staging.iterdir(), key=lambda item: item.name):
            if path.name == "artifact_manifest.json":
                continue
            os.replace(path, destination / path.name)
        os.replace(
            staging / "artifact_manifest.json",
            destination / "artifact_manifest.json",
        )
        return result_manifest_hash
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def execute_v18_formal_campaign(
    *,
    bundle: FormalInputBundle,
    repo_root: Path,
    output_root: Path,
    candidate_adapter: CandidateAdapter,
    parity_runner: ParityRunner | None = None,
    raw_replay_runner: RawReplayRunner | None = None,
) -> dict[str, Any]:
    """Execute frozen V18 evidence once and publish a manifest-last bundle."""

    preregistration = bundle.preregistration
    campaign_id = str(preregistration["campaignId"])
    candidate_id = str(bundle.candidate["candidateId"])
    validate_candidate_binding(
        adapter=candidate_adapter,
        preregistration=preregistration,
        requested_candidate_id=candidate_id,
    )
    effective_parity_runner = parity_runner or candidate_adapter.run_parity
    effective_raw_replay_runner = raw_replay_runner or candidate_adapter.replay
    parity, reference_canonical, adapter_canonical = effective_parity_runner(
        bundle=bundle,
        repo_root=Path(repo_root).resolve(),
    )
    round_trip_cost = float(
        preregistration.get("costModel", {}).get("baseRoundTripCostRate", 0.0)
    )
    raw_events = [
        {**dict(row), "signalId": _signal_id(row)}
        for row in effective_raw_replay_runner(
            candidate=bundle.candidate,
            frames=bundle.frames,
            round_trip_cost_rate=round_trip_cost,
        )
    ]
    assigned_raw, fold_rejected, fold_audit = assign_events_to_folds(
        raw_events,
        preregistration["splitPolicy"],
    )
    reference_events, reference_missing = _merge_canonical_events(
        reference_canonical,
        assigned_raw,
    )
    adapter_events, adapter_missing = _merge_canonical_events(
        adapter_canonical,
        assigned_raw,
    )
    reference_features, ranking_audit = build_signal_feature_evidence(
        reference_events,
        bundle.frames,
        bundle.candidate,
    )
    adapter_features, adapter_ranking_audit = build_signal_feature_evidence(
        adapter_events,
        bundle.frames,
        bundle.candidate,
    )
    daily_liquidity, return_panel, semantics_audit = build_daily_market_evidence(
        bundle.frames
    )
    del daily_liquidity
    reference_ready, context_audit = attach_point_in_time_context(
        reference_features,
        return_panel,
    )
    adapter_ready, adapter_context_audit = attach_point_in_time_context(
        adapter_features,
        return_panel,
    )
    policy = preregistration["capitalCompetitionPolicy"]
    reference_replay = replay_v18_capital_policy(
        reference_ready,
        bundle.frames,
        policy=policy,
    )
    adapter_replay = replay_v18_capital_policy(
        adapter_ready,
        bundle.frames,
        policy=policy,
    )
    capital_parity = compare_capital_replays(reference_replay, adapter_replay)
    base_metrics = summarize_capital_replay(reference_replay)
    folds = _fold_results(preregistration, reference_replay)
    cost_stress = build_locked_cost_stress(
        reference_replay,
        reference_ready,
        preregistration["costModel"],
    )
    funding = build_funding_stress(
        reference_replay["trades"],
        adverse_rate_per_settlement=_registered_funding_rate(bundle),
    )
    funding_metrics = _funding_metrics(funding, reference_replay["trades"])

    accepted_ids = {str(row["signalId"]) for row in reference_replay["trades"]}
    accepted_raw = []
    trade_by_id = {
        str(row["signalId"]): dict(row) for row in reference_replay["trades"]
    }
    for row in assigned_raw:
        signal_id = str(row["signalId"])
        if signal_id not in accepted_ids:
            continue
        accepted_raw.append(
            {
                **dict(row),
                "realizedNetR": trade_by_id[signal_id]["realizedNetR"],
            }
        )
    benchmark = build_s01_benchmark(accepted_raw, bundle.frames, hold_bars=12)
    split = preregistration["splitPolicy"]
    daily_returns = _daily_return_panel(
        trades=reference_replay["trades"],
        benchmark=benchmark,
        start=str(split["commonStart"]),
        cutoff_exclusive=str(split["commonCutoffExclusive"]),
        initial_equity=float(reference_replay["initialEquity"]),
    )
    newey_west = newey_west_alpha(
        daily_returns["differentialReturn"].to_numpy(),
        lag=int(
            preregistration.get("statisticalPolicy", {})
            .get("neweyWest", {})
            .get("maximumLagDays", 5)
        ),
    )
    unavailable_reason = (
        "No point-in-time daily-return panel for the ten-candidate selection family "
        "was frozen before results; retroactive construction is prohibited."
    )
    unavailable_statistics = {
        "benjamini_hochberg_fdr.json": _unavailable_statistic(
            "benjamini_hochberg_fdr", unavailable_reason
        ),
        "deflated_sharpe.json": _unavailable_statistic(
            "deflated_sharpe", unavailable_reason
        ),
        "pbo.json": _unavailable_statistic("pbo", unavailable_reason),
        "white_reality_check.json": _unavailable_statistic(
            "white_reality_check", unavailable_reason
        ),
        "spa.json": _unavailable_statistic("spa", unavailable_reason),
    }
    gate_matrix = _build_gate_matrix(
        bundle=bundle,
        parity=parity,
        capital_parity=capital_parity,
        ranking_audit=ranking_audit,
        context_audit=context_audit,
        fold_assignment=fold_audit,
        fold_results=folds,
        base_metrics=base_metrics,
        cost_stress=cost_stress,
        funding=funding,
        funding_metrics=funding_metrics,
        benchmark=benchmark,
    )
    implementation_blockers: list[str] = []
    if not parity.get("passed"):
        implementation_blockers.append("translation_parity_failed")
    if not capital_parity.get("passed"):
        implementation_blockers.append("capital_policy_parity_failed")
    if reference_missing or adapter_missing:
        implementation_blockers.append("canonical_event_identity_mapping_incomplete")
    if fold_rejected:
        implementation_blockers.append("formal_event_fold_assignment_incomplete")
    if int(ranking_audit.get("missingRankingFieldCount", 0)) > 0:
        implementation_blockers.append("frozen_signal_ranking_evidence_incomplete")
    if int(adapter_ranking_audit.get("missingRankingFieldCount", 0)) > 0:
        implementation_blockers.append("adapter_signal_ranking_evidence_incomplete")
    if int(context_audit.get("missingContextFieldCount", 0)) > 0:
        implementation_blockers.append("point_in_time_portfolio_context_incomplete")
    if int(adapter_context_audit.get("missingContextFieldCount", 0)) > 0:
        implementation_blockers.append("adapter_point_in_time_context_incomplete")
    if semantics_audit.get("status") != "passed":
        implementation_blockers.append("capacity_data_semantics_failed")
    if funding.get("gateEvaluable") is not True:
        implementation_blockers.append("registered_funding_stress_input_unavailable")
    route, blockers = _route(
        bundle=bundle,
        gate_matrix=gate_matrix,
        implementation_blockers=implementation_blockers,
    )

    route_payload = {
        "schemaVersion": "s01_v18_formal_route_v1",
        "campaignId": campaign_id,
        "route": route,
        "blockers": blockers,
        "formalRunCount": 1,
        "formalInputReadCount": 1,
        "resultDrivenParameterChangeCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    summary = {
        "schemaVersion": "s01_v18_formal_campaign_summary_v1",
        **route_payload,
        "baseRawSignalCount": reference_replay["rawSignalCount"],
        "baseAcceptedTradeCount": reference_replay["acceptedSignalCount"],
        "baseRejectedSignalCount": reference_replay["rejectedSignalCount"],
        "baseMetrics": base_metrics,
        "statisticsUnavailablePredeclared": True,
        "fundingGateEvaluable": funding["gateEvaluable"],
        "cleanLockedOosAvailable": False,
        "formalAdmissionPassed": False,
    }
    failure = {
        "schemaVersion": "s01_v18_formal_failure_attribution_v1",
        "campaignId": campaign_id,
        "route": route,
        "primaryBlocker": blockers[0] if blockers else None,
        "blockers": blockers,
        "strategyPerformanceFailure": route == "archive_s01_current_version",
        "implementationOrEvidenceFailure": route
        == "implementation_invalid_requires_new_campaign",
        "resultDrivenRepairAllowed": False,
    }
    exposure = pd.DataFrame(
        [
            row
            for row in reference_replay["equityCurve"]
            if row.get("timestamp") is not None
        ]
    )
    if exposure.empty:
        exposure = pd.DataFrame(
            columns=("timestamp", "equity", "positionCount", "openRisk")
        )
    comparable = pd.DataFrame(
        columns=("candidateId", "date", "netReturn", "panelIdentityHash")
    )
    return_panel_audit = {
        "schemaVersion": "s01_v18_return_panel_audit_v1",
        "candidateRowCount": len(daily_returns),
        "candidateDateMinimum": (
            _utc_iso(daily_returns.iloc[0]["date"]) if len(daily_returns) else None
        ),
        "candidateDateMaximum": (
            _utc_iso(daily_returns.iloc[-1]["date"]) if len(daily_returns) else None
        ),
        "comparableCandidatePanelStatus": "unavailable_predeclared",
        "comparableCandidatePanelRowCount": 0,
        "retroactiveConstructionAllowed": False,
        "lookaheadReadCount": 0,
    }
    concentration = {
        "schemaVersion": "s01_v18_concentration_v1",
        "maximumSingleSymbolPositiveContribution": base_metrics[
            "maximumSingleSymbolPositiveContribution"
        ],
        "maximumSingleMonthPositiveContribution": base_metrics[
            "maximumSingleMonthPositiveContribution"
        ],
        "bySymbol": base_metrics["positiveContributionBySymbol"],
        "byMonth": base_metrics["positiveContributionByMonth"],
    }
    trial_lineage = {
        "schemaVersion": "s01_v18_trial_lineage_v1",
        "campaignId": campaign_id,
        "candidateId": bundle.candidate.get("candidateId"),
        "formalCandidateCount": int(
            preregistration.get("trialLineagePolicy", {}).get(
                "formalCandidateCount", 1
            )
        ),
        "selectionBiasFamilySize": int(
            preregistration.get("trialLineagePolicy", {}).get(
                "selectionBiasFamilySize", 10
            )
        ),
        "parameterSearchAllowed": False,
        "resultDrivenParameterChangeCount": 0,
    }
    json_payloads = {
        "fold_results.json": {
            "schemaVersion": "s01_v18_fold_results_v1",
            "campaignId": campaign_id,
            "folds": folds,
            "foldAssignmentAudit": fold_audit,
        },
        "capital_competition_results.json": reference_replay,
        "capital_rejection_breakdown.json": {
            "schemaVersion": "s01_v18_capital_rejection_breakdown_v1",
            "rejectionBreakdown": reference_replay["rejectionBreakdown"],
            "rejectedSignalCount": reference_replay["rejectedSignalCount"],
        },
        "position_sizing_results.json": {
            "schemaVersion": "s01_v18_position_sizing_results_v1",
            "accepted": [
                row for row in reference_replay["decisions"] if row["accepted"]
            ],
        },
        "freqtrade_results.json": {
            "schemaVersion": "s01_v18_freqtrade_results_v1",
            "eventCount": len(adapter_canonical),
            "events": adapter_canonical,
            "formalPerformanceClaimed": False,
        },
        "translation_parity.json": parity,
        "signal_identity_parity.json": {
            "schemaVersion": "s01_v18_signal_identity_parity_v1",
            "status": parity.get("status"),
            "passed": parity.get("passed"),
            "signalIdentityParityPct": parity.get("identityParityPct"),
            "referenceEventCount": parity.get("referenceEventCount"),
            "implementationEventCount": parity.get("implementationEventCount"),
            "blockers": parity.get("blockers", []),
        },
        "capital_policy_parity.json": capital_parity,
        "position_size_parity.json": {
            "schemaVersion": "s01_v18_position_size_parity_v1",
            "status": capital_parity.get("status"),
            "passed": capital_parity.get("passed"),
            "positionSizeParityPct": capital_parity.get("positionSizeParityPct"),
            "blockers": capital_parity.get("blockers", []),
        },
        "exit_leg_parity.json": {
            "schemaVersion": "s01_v18_exit_leg_parity_v1",
            "status": parity.get("status"),
            "passed": parity.get("passed"),
            "exitLegParityPct": parity.get("exitLegParityPct"),
            "blockers": parity.get("blockers", []),
        },
        "cost_stress.json": cost_stress,
        "funding_stress.json": {**funding, "metrics": funding_metrics},
        "simple_benchmark_results.json": benchmark,
        "return_panel_audit.json": return_panel_audit,
        "trial_lineage.json": trial_lineage,
        "newey_west_alpha.json": newey_west,
        **unavailable_statistics,
        "concentration.json": concentration,
        "uncertainty_intervals.json": _uncertainty_intervals(
            reference_replay["trades"]
        ),
        "gate_matrix.json": gate_matrix,
        "route_decision.json": route_payload,
        "failure_attribution.json": failure,
        "campaign_summary.json": summary,
    }
    result_manifest_hash = _publish_artifacts(
        Path(output_root),
        json_payloads=json_payloads,
        markdown_payloads={"campaign_summary.md": _summary_markdown(summary)},
        parquet_payloads={
            "portfolio_exposure_daily.parquet": exposure,
            "daily_return_panel.parquet": daily_returns,
            "comparable_candidate_panel.parquet": comparable,
        },
        csv_payloads={"fold_results.csv": folds},
        campaign_id=campaign_id,
        candidate_id=candidate_id,
        candidate_adapter=candidate_adapter,
        route=route,
    )
    return {
        **route_payload,
        "resultManifestHash": result_manifest_hash,
    }
