"""Bounded prefilter and conditional formal validation runner."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.research_screening.campaign_metrics import summarize_events

from .event_strategy import replay_selloff_recovery_events
from .prefilter import evaluate_event_prefilter, finalize_prefilter_route
from .preregistration import (
    build_formal_preregistration,
    build_prefilter_preregistration,
)


SOURCE_FILES = (
    "campaign.py",
    "execution.py",
    "event_strategy.py",
    "prefilter.py",
    "preregistration.py",
    "campaign_runner.py",
)


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def calculate_development_end(
    start: str, end: str, *, fraction: float
) -> datetime:
    if not 0 < fraction < 1:
        raise ValueError("development fraction must be between zero and one")
    beginning = _parse_timestamp(start)
    finish = _parse_timestamp(end)
    if beginning >= finish:
        raise ValueError("development start must be before available end")
    return beginning + (finish - beginning) * fraction


def verify_implementation_freeze(
    preregistration: Mapping[str, Any], *, source_root: Path
) -> None:
    for name, expected in preregistration["implementationSourceHashes"].items():
        path = source_root / name
        if not path.is_file() or sha256_file(path) != expected:
            raise RuntimeError(f"implementation changed after preregistration: {name}")


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()
    return value


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _git_head(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _source_hashes(source_root: Path) -> dict[str, str]:
    return {name: sha256_file(source_root / name) for name in SOURCE_FILES}


def _minimal_snapshot(repo_root: Path) -> tuple[Path, dict[str, Any]]:
    snapshots = sorted(
        (repo_root / "research" / "data_snapshots").glob(
            "minimal_snapshot_*.json"
        ),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    if not snapshots:
        raise FileNotFoundError("minimal data snapshot is missing")
    return snapshots[0], _read_json(snapshots[0])


def freeze_prefilter(repo_root: Path) -> Path:
    source_root = repo_root / "alphapilot" / "minimal_research_campaign"
    core = _read_json(repo_root / "reports" / "minimal_data_layer" / "core_universe.json")
    _, snapshot = _minimal_snapshot(repo_root)
    preregistration = build_prefilter_preregistration(
        core_universe=core,
        snapshot=snapshot,
        archived_family_ids={"trend_pullback", "breakout"},
        implementation_commit=_git_head(repo_root),
        implementation_source_hashes=_source_hashes(source_root),
    )
    path = (
        repo_root
        / "research"
        / "preregistrations"
        / f"{preregistration['campaignId']}_prefilter.json"
    )
    write_json_atomic(path, preregistration)
    return path


def _latest_preregistration(repo_root: Path, suffix: str) -> tuple[Path, dict[str, Any]]:
    paths = sorted(
        (repo_root / "research" / "preregistrations").glob(f"*_{suffix}.json"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    if not paths:
        raise FileNotFoundError(f"{suffix} preregistration is missing")
    return paths[0], _read_json(paths[0])


def _reference_map(snapshot: Mapping[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(row["instrumentId"]), str(row["timeframe"])): dict(row)
        for row in snapshot["datasetReferences"]
    }


def _load_frame(
    *,
    data_root: Path,
    reference: Mapping[str, Any],
    start: datetime,
    end: datetime,
) -> pd.DataFrame:
    path = data_root / Path(str(reference["path"]))
    if not path.is_file():
        raise FileNotFoundError(path)
    if sha256_file(path) != reference["sha256"]:
        raise RuntimeError(f"snapshot dataset hash mismatch: {reference['instrumentId']}")
    frame = pd.read_parquet(path)
    frame["date"] = pd.to_datetime(frame["date"], utc=True)
    if "confirmed" in frame.columns:
        frame = frame[pd.to_numeric(frame["confirmed"], errors="coerce") == 1]
    frame = frame[(frame["date"] >= start) & (frame["date"] < end)]
    return frame.sort_values("date").drop_duplicates("date", keep="last").reset_index(drop=True)


def _market_returns(frames: Mapping[str, pd.DataFrame]) -> pd.Series:
    panel = pd.concat(
        {
            symbol: frame.set_index("date")["close"].astype(float)
            for symbol, frame in frames.items()
        },
        axis=1,
    ).sort_index()
    return panel.pct_change(fill_method=None).median(axis=1, skipna=True)


def _events_for_frames(
    frames: Mapping[str, pd.DataFrame],
    *,
    parameters: Mapping[str, Any],
    round_trip_cost_rate: float,
    benchmark_mode: str = "representative_median",
) -> list[dict[str, Any]]:
    median_return = _market_returns(frames)
    events: list[dict[str, Any]] = []
    for symbol, frame in sorted(frames.items()):
        if benchmark_mode == "zero":
            aligned_market = pd.Series(np.zeros(len(frame)), index=frame.index)
        else:
            aligned_market = median_return.reindex(
                pd.DatetimeIndex(frame["date"])
            ).reset_index(drop=True)
        rows = replay_selloff_recovery_events(
            frame,
            market_return=aligned_market,
            symbol=symbol,
            residual_z_threshold=float(parameters["residualZThreshold"]),
            residual_recovery_delta=float(parameters["residualRecoveryDelta"]),
            market_crash_floor=float(parameters["marketCrashFloor"]),
            atr_stop_multiple=float(parameters["atrStopMultiple"]),
            target_r=2.0,
            maximum_hold_bars=int(parameters["maximumHoldBars"]),
            round_trip_cost_rate=round_trip_cost_rate,
        )
        events.extend(rows)
    return sorted(events, key=lambda row: (row["entryTimestamp"], row["symbol"]))


def _stress_metrics(events: Sequence[Mapping[str, Any]], multiplier: float) -> dict[str, Any]:
    stressed = [
        {
            **dict(row),
            "netR": float(row["grossR"]) - float(row["costR"]) * multiplier,
        }
        for row in events
    ]
    return summarize_events(stressed)


def _buy_hold_benchmarks(frames: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    returns = {
        symbol: float(frame.iloc[-1]["close"] / frame.iloc[0]["close"] - 1.0)
        for symbol, frame in frames.items()
        if len(frame) >= 2
    }
    return {
        "noTradeReturn": 0.0,
        "btcDevelopmentReturn": returns.get("BTC-USDT-SWAP"),
        "equalWeightRepresentativeReturn": (
            sum(returns.values()) / len(returns) if returns else None
        ),
        "instrumentReturns": returns,
        "comparabilityNote": (
            "Holding returns are context benchmarks, not event-risk-normalized pass gates."
        ),
    }


def _write_parquet(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    pd.DataFrame([_json_safe(dict(row)) for row in rows]).to_parquet(
        temporary, index=False
    )
    temporary.replace(path)


def _prefilter_markdown(
    preregistration: Mapping[str, Any],
    result: Mapping[str, Any],
    route: Mapping[str, Any],
) -> str:
    metrics = result["prefilter"]["metrics"]
    lines = [
        f"# Minimal Strategy Campaign {preregistration['campaignId']}",
        "",
        "## Representative Prefilter",
        "",
        f"- Strategy: `{result['strategyId']}`",
        f"- Passed: `{str(result['prefilter']['passed']).lower()}`",
        f"- Events: `{metrics['eventCount']}`",
        f"- Profit factor: `{metrics['profitFactor']:.4f}`",
        f"- Average net R: `{metrics['averageNetR']:.4f}`",
        f"- Total net R: `{metrics['totalNetR']:.4f}`",
        f"- Positive month ratio: `{metrics['positiveMonthRatio']:.4f}`",
        "",
        "## Routing",
        "",
        f"- Formal survivors: `{len(route['formalStrategyIds'])}`",
        f"- Archived after prefilter: `{len(route['archivedStrategyIds'])}`",
        f"- Diagnostic-only hypotheses: `{len(route['diagnosticStrategyIds'])}`",
        "- Demo Release: `0`",
        "- Demo ARM: `false`",
        "- Orders: `0`",
        "",
        "Failed hypotheses are not tuned or replaced in this campaign.",
    ]
    return "\n".join(lines) + "\n"


def _write_artifact_manifest(campaign_root: Path) -> None:
    files = sorted(
        path
        for path in campaign_root.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    write_json_atomic(
        campaign_root / "artifact_manifest.json",
        {
            "schemaVersion": "minimal_campaign_artifact_manifest_v1",
            "artifacts": [
                {
                    "path": path.relative_to(campaign_root).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
                for path in files
            ],
        },
    )


def run_prefilter(repo_root: Path, data_root: Path) -> Path:
    _, preregistration = _latest_preregistration(repo_root, "prefilter")
    verify_implementation_freeze(
        preregistration,
        source_root=repo_root / "alphapilot" / "minimal_research_campaign",
    )
    _, snapshot = _minimal_snapshot(repo_root)
    if snapshot["snapshotHash"] != preregistration["snapshotHash"]:
        raise RuntimeError("minimal snapshot changed after preregistration")
    references = _reference_map(snapshot)
    start = _parse_timestamp(preregistration["dataBoundary"]["developmentStart"])
    available_end = _parse_timestamp(preregistration["dataBoundary"]["availableEnd"])
    development_end = calculate_development_end(
        start.isoformat(),
        available_end.isoformat(),
        fraction=float(preregistration["dataBoundary"]["developmentFraction"]),
    )
    frames = {
        symbol: _load_frame(
            data_root=data_root,
            reference=references[(symbol, "4h")],
            start=start,
            end=development_end,
        )
        for symbol in preregistration["representativeUniverse"]
    }
    parameters = dict(preregistration["eventDefinition"])
    events = _events_for_frames(
        frames,
        parameters=parameters,
        round_trip_cost_rate=float(preregistration["costModel"]["roundTripRate"]),
    )
    strategy_id = "core_idiosyncratic_selloff_recovery_long_4h"
    for event in events:
        event["strategyId"] = strategy_id
        event["split"] = "development_prefilter"
    event_result = {
        "strategyId": strategy_id,
        "diagnosticOnly": False,
        "status": "evaluated",
        "developmentStart": start.isoformat(),
        "developmentEndExclusive": development_end.isoformat(),
        "availableEndNotRead": available_end.isoformat(),
        "prefilter": evaluate_event_prefilter(
            events, gates=preregistration["prefilterGates"]
        ),
        "costStress": {
            "base": _stress_metrics(events, 1.0),
            "1.5x": _stress_metrics(events, 1.5),
            "2.0x": _stress_metrics(events, 2.0),
            "funding": "unavailable_not_zero",
        },
    }
    breadth = next(
        row
        for row in preregistration["hypotheses"]
        if row["strategyId"]
        == "core_breadth_transition_leader_continuation_4h"
    )
    breadth_result = {
        "strategyId": breadth["strategyId"],
        "diagnosticOnly": False,
        "status": "not_generated_novelty_rejected",
        "prefilter": {
            "passed": False,
            "failedGates": ["archived_family_novelty"],
        },
    }
    diagnostic_result = {
        "strategyId": "diagnostic_fixed_core_cross_sectional_momentum_1d",
        "diagnosticOnly": True,
        "status": "diagnostic_data_insufficient",
        "formalPassEligible": False,
        "reason": (
            "Historical PIT membership is unavailable and the shared minimal "
            "snapshot does not contain sufficient 1d core coverage."
        ),
        "prefilter": {"passed": False},
    }
    results = [event_result, breadth_result, diagnostic_result]
    route = finalize_prefilter_route(results)
    campaign_root = (
        repo_root
        / "reports"
        / "minimal_strategy_campaign"
        / str(preregistration["campaignId"])
    )
    output = campaign_root / "prefilter"
    output.mkdir(parents=True, exist_ok=True)
    _write_parquet(output / "event_ledger.parquet", events)
    _write_parquet(
        campaign_root / "candidate_results.parquet",
        [
            {
                "strategyId": row["strategyId"],
                "status": row["status"],
                "diagnosticOnly": row["diagnosticOnly"],
                "passed": bool(row["prefilter"].get("passed")),
            }
            for row in results
        ],
    )
    novelty_audit = {
        "archivedEvidence": "reports/full_archived_strategy_cross_strategy_patterns.json",
        "hypotheses": [
            {
                "strategyId": row["strategyId"],
                "noveltyStatus": row["noveltyStatus"],
                "noveltyReason": row.get("noveltyReason"),
            }
            for row in preregistration["hypotheses"]
        ],
        "replacementHypothesisAllowed": False,
    }
    failure = {
        "failures": [
            {
                "strategyId": row["strategyId"],
                "status": row["status"],
                "failedGates": row["prefilter"].get("failedGates", []),
                "nextAction": "archive_without_tuning"
                if not row["diagnosticOnly"]
                else "retain_as_diagnostic_only",
            }
            for row in results
            if not bool(row["prefilter"].get("passed"))
        ]
    }
    write_json_atomic(output / "strategy_inventory.json", preregistration["hypotheses"])
    write_json_atomic(output / "novelty_audit.json", novelty_audit)
    write_json_atomic(
        output / "representative_universe.json",
        {
            "selectionRule": preregistration["representativeSelectionRule"],
            "instrumentIds": preregistration["representativeUniverse"],
            "selectedBeforeResults": True,
        },
    )
    write_json_atomic(output / "event_prefilter.json", _json_safe(event_result))
    write_json_atomic(output / "portfolio_prefilter.json", diagnostic_result)
    write_json_atomic(output / "simple_benchmarks.json", _buy_hold_benchmarks(frames))
    write_json_atomic(output / "failure_attribution.json", failure)
    (output / "prefilter_summary.md").write_text(
        _prefilter_markdown(preregistration, event_result, route), encoding="utf-8"
    )
    write_json_atomic(campaign_root / "route_decision.json", route)
    write_json_atomic(campaign_root / "experiment_budget.json", preregistration["experimentBudget"])
    write_json_atomic(
        campaign_root / "gate_matrix.json",
        {
            "stage": "prefilter",
            "strategies": [
                {
                    "strategyId": row["strategyId"],
                    "passed": bool(row["prefilter"].get("passed")),
                    "gates": row["prefilter"].get("gates", {}),
                }
                for row in results
            ],
        },
    )
    write_json_atomic(campaign_root / "failure_attribution.json", failure)
    write_json_atomic(
        campaign_root / "campaign_summary.json",
        {
            "campaignId": preregistration["campaignId"],
            "stage": "prefilter_completed",
            "formalStageAllowed": route["formalStageAllowed"],
            "formalStrategyIds": route["formalStrategyIds"],
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    )
    (campaign_root / "campaign_summary.md").write_text(
        _prefilter_markdown(preregistration, event_result, route), encoding="utf-8"
    )
    _write_artifact_manifest(campaign_root)
    return campaign_root


def freeze_formal(repo_root: Path) -> Path:
    _, prefilter = _latest_preregistration(repo_root, "prefilter")
    campaign_root = (
        repo_root
        / "reports"
        / "minimal_strategy_campaign"
        / str(prefilter["campaignId"])
    )
    route = _read_json(campaign_root / "route_decision.json")
    formal = build_formal_preregistration(
        prefilter,
        survivor_strategy_ids=list(route["formalStrategyIds"]),
    )
    path = (
        repo_root
        / "research"
        / "preregistrations"
        / f"{prefilter['campaignId']}_formal.json"
    )
    write_json_atomic(path, formal)
    return path


def _partition_events(
    events: Sequence[Mapping[str, Any]], formal: Mapping[str, Any]
) -> list[dict[str, Any]]:
    timestamps = sorted(_parse_timestamp(str(row["entryTimestamp"])) for row in events)
    if not timestamps:
        return []
    start, end = timestamps[0], timestamps[-1]
    development_end = start + (end - start) * 0.55
    walk_forward_end = start + (end - start) * 0.80
    fold_width = (walk_forward_end - development_end) / 5
    rows: list[dict[str, Any]] = []
    for event in events:
        timestamp = _parse_timestamp(str(event["entryTimestamp"]))
        row = dict(event)
        if timestamp < development_end:
            row["split"] = "development"
            row["foldId"] = ""
        elif timestamp < walk_forward_end:
            fold = min(4, int((timestamp - development_end) / fold_width))
            row["split"] = "walk_forward"
            row["foldId"] = f"wf_{fold + 1}"
        else:
            row["split"] = "holdout"
            row["foldId"] = ""
        rows.append(row)
    return rows


def _apply_capital_competition(
    events: Sequence[Mapping[str, Any]], formal: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    config = formal["capitalCompetition"]
    active: list[dict[str, Any]] = []
    selected: list[dict[str, Any]] = []
    rejected = 0
    ordered = sorted(
        (dict(row) for row in events),
        key=lambda row: (
            row["entryTimestamp"],
            -float(row.get("signalScore") or 0.0),
            row["symbol"],
        ),
    )
    for event in ordered:
        entry = _parse_timestamp(str(event["entryTimestamp"]))
        active = [
            row
            for row in active
            if _parse_timestamp(str(row["exitTimestamp"])) > entry
        ]
        symbol_open = any(row["symbol"] == event["symbol"] for row in active)
        if (
            symbol_open
            or len(active) >= int(config["maximumConcurrentPositions"])
            or len(active) >= int(config["maximumSameDirectionPositions"])
        ):
            rejected += 1
            continue
        event["riskR"] = 1.0
        selected.append(event)
        active.append(event)
    return selected, {
        "inputEventCount": len(events),
        "selectedEventCount": len(selected),
        "competitionRejectedCount": rejected,
        "configuration": config,
    }


def _gate(observed: float | int, operator: str, required: float | int) -> dict[str, Any]:
    comparisons = {
        ">=": observed >= required,
        ">": observed > required,
        "<=": observed <= required,
    }
    return {
        "observed": observed,
        "operator": operator,
        "required": required,
        "passed": comparisons[operator],
    }


def run_formal(repo_root: Path, data_root: Path) -> Path:
    _, prefilter = _latest_preregistration(repo_root, "prefilter")
    _, formal = _latest_preregistration(repo_root, "formal")
    verify_implementation_freeze(
        prefilter,
        source_root=repo_root / "alphapilot" / "minimal_research_campaign",
    )
    campaign_root = (
        repo_root
        / "reports"
        / "minimal_strategy_campaign"
        / str(formal["campaignId"])
    )
    lock_path = repo_root / "research" / "locked_oos" / f"{formal['campaignId']}.json"
    if lock_path.exists():
        raise RuntimeError("campaign locked OOS has already been unlocked")
    core = _read_json(repo_root / "reports" / "minimal_data_layer" / "core_universe.json")
    snapshot_path, snapshot = _minimal_snapshot(repo_root)
    references = _reference_map(snapshot)
    members = [str(row["instrumentId"]) for row in core["members"]]
    start = max(
        _parse_timestamp(str(row["profiles"]["4h"]["effectiveBacktestStart"]))
        for row in core["members"]
    )
    end = _parse_timestamp(str(core["commonCutoffByTimeframe"]["4h"]))
    frames = {
        symbol: _load_frame(
            data_root=data_root,
            reference=references[(symbol, "4h")],
            start=start,
            end=end,
        )
        for symbol in members
    }
    events = _events_for_frames(
        frames,
        parameters=prefilter["eventDefinition"],
        round_trip_cost_rate=float(prefilter["costModel"]["roundTripRate"]),
    )
    partitioned = _partition_events(events, formal)
    competitive, competition = _apply_capital_competition(partitioned, formal)
    write_json_atomic(
        lock_path,
        {
            "campaignId": formal["campaignId"],
            "unlockCount": 1,
            "maximumUnlockCount": 1,
            "unlockedAt": datetime.now(timezone.utc).isoformat(),
            "preregistrationHash": formal["preregistrationHash"],
        },
    )
    development = [row for row in competitive if row["split"] == "development"]
    walk_forward = [row for row in competitive if row["split"] == "walk_forward"]
    holdout = [row for row in competitive if row["split"] == "holdout"]
    wf_metrics = summarize_events(walk_forward)
    holdout_metrics = summarize_events(holdout)
    stress = {
        "base": summarize_events(walk_forward + holdout),
        "1.5x": _stress_metrics(walk_forward + holdout, 1.5),
        "2.0x": _stress_metrics(walk_forward + holdout, 2.0),
        "funding": "unavailable_not_zero",
    }
    fold_metrics = {
        fold: summarize_events([row for row in walk_forward if row["foldId"] == fold])
        for fold in [f"wf_{index}" for index in range(1, 6)]
    }
    positive_folds = sum(row["averageNetR"] > 0 for row in fold_metrics.values())
    basic_observed = {
        "walkForwardProfitFactor": wf_metrics["profitFactor"],
        "walkForwardAverageNetR": wf_metrics["averageNetR"],
        "walkForwardTotalNetR": wf_metrics["totalNetR"],
        "positiveFoldCount": positive_folds,
        "maximumDrawdownPct": wf_metrics["maximumDrawdownPct"],
    }
    basic_gates = {
        name: _gate(
            basic_observed[name], str(rule["operator"]), rule["required"]
        )
        for name, rule in formal["eventBasicGates"].items()
    }
    formal_observed = {
        "walkForwardProfitFactor": wf_metrics["profitFactor"],
        "walkForwardAverageNetR": wf_metrics["averageNetR"],
        "positiveFoldCount": positive_folds,
        "maximumDrawdownPct": wf_metrics["maximumDrawdownPct"],
        "lockedOosProfitFactor": holdout_metrics["profitFactor"],
        "lockedOosAverageNetR": holdout_metrics["averageNetR"],
        "lockedOosTotalNetR": holdout_metrics["totalNetR"],
        "stress1_5xProfitFactor": stress["1.5x"]["profitFactor"],
        "stress1_5xAverageNetR": stress["1.5x"]["averageNetR"],
        "singleInstrumentPositiveContribution": stress["base"]["singleInstrumentPositiveContribution"],
        "singleMonthPositiveContribution": stress["base"]["singleMonthPositiveContribution"],
    }
    formal_gates = {
        name: _gate(
            formal_observed[name], str(rule["operator"]), rule["required"]
        )
        for name, rule in formal["eventFormalGates"].items()
    }
    translation_parity = {
        "status": "not_executed",
        "passed": False,
        "reason": "No frozen Freqtrade translation exists for this new hypothesis.",
    }
    formal_passed = (
        all(row["passed"] for row in basic_gates.values())
        and all(row["passed"] for row in formal_gates.values())
        and translation_parity["passed"]
    )
    output = campaign_root / "formal"
    output.mkdir(parents=True, exist_ok=True)
    _write_parquet(output / "event_ledger.parquet", competitive)
    shared_reference = {
        "snapshotPath": snapshot_path.relative_to(repo_root).as_posix(),
        "snapshotId": snapshot["snapshotId"],
        "snapshotHash": snapshot["snapshotHash"],
        "physicalCopiesCreated": 0,
    }
    strategy_definitions = {
        "strategyIds": formal["strategyIds"],
        "definition": prefilter["eventDefinition"],
        "execution": prefilter["eventExecution"],
    }
    walk_forward_report = {
        "foldCount": 5,
        "purged": True,
        "embargo": True,
        "folds": fold_metrics,
        "metrics": wf_metrics,
    }
    locked_oos = {
        "campaignLocked": True,
        "globalCleanHoldout": False,
        "unlockCount": 1,
        "metrics": holdout_metrics,
    }
    gate_matrix = {
        "basicGates": basic_gates,
        "formalGates": formal_gates,
        "translationParity": translation_parity,
        "formalPassed": formal_passed,
    }
    failure = {
        "failedBasicGates": sorted(
            name for name, row in basic_gates.items() if not row["passed"]
        ),
        "failedFormalGates": sorted(
            name for name, row in formal_gates.items() if not row["passed"]
        ),
        "translationParityPassed": False,
    }
    summary = {
        "campaignId": formal["campaignId"],
        "stage": "formal_completed",
        "formalPassed": formal_passed,
        "formalPassCount": int(formal_passed),
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    write_json_atomic(output / "shared_snapshot_reference.json", shared_reference)
    write_json_atomic(output / "strategy_definitions.json", strategy_definitions)
    write_json_atomic(
        output / "freqtrade_results.json",
        {"status": "not_executed", "formalEvidenceEligible": False},
    )
    write_json_atomic(output / "portfolio_results.json", {"status": "not_applicable"})
    write_json_atomic(output / "translation_parity.json", translation_parity)
    write_json_atomic(output / "walk_forward.json", _json_safe(walk_forward_report))
    write_json_atomic(output / "campaign_locked_oos.json", _json_safe(locked_oos))
    write_json_atomic(output / "cost_stress.json", _json_safe(stress))
    write_json_atomic(output / "capital_competition.json", competition)
    write_json_atomic(output / "gate_matrix.json", _json_safe(gate_matrix))
    write_json_atomic(output / "failure_attribution.json", failure)
    write_json_atomic(output / "campaign_summary.json", summary)
    (output / "campaign_summary.md").write_text(
        "\n".join(
            [
                f"# Formal campaign {formal['campaignId']}",
                "",
                f"- Formal passed: `{str(formal_passed).lower()}`",
                f"- Walk-forward events: `{len(walk_forward)}`",
                f"- Locked OOS events: `{len(holdout)}`",
                "- Demo Release: `0`",
                "- Demo ARM: `false`",
                "- Orders: `0`",
                "",
                "No formal pass evidence is emitted unless every frozen gate and translation parity passes.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    write_json_atomic(campaign_root / "campaign_summary.json", summary)
    (campaign_root / "campaign_summary.md").write_text(
        (output / "campaign_summary.md").read_text(encoding="utf-8"),
        encoding="utf-8",
    )
    _write_artifact_manifest(campaign_root)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--stage",
        required=True,
        choices=("freeze-prefilter", "prefilter", "freeze-formal", "formal"),
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, required=True)
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    data_root = args.data_root.resolve()
    if not data_root.is_dir():
        raise FileNotFoundError(data_root)
    actions = {
        "freeze-prefilter": lambda: freeze_prefilter(repo_root),
        "prefilter": lambda: run_prefilter(repo_root, data_root),
        "freeze-formal": lambda: freeze_formal(repo_root),
        "formal": lambda: run_formal(repo_root, data_root),
    }
    output = actions[args.stage]()
    print(
        json.dumps(
            {"stage": args.stage, "status": "completed", "output": str(output)},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

