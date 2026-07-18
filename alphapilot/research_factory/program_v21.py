"""V21 bounded event prefilter and identity-complete preregistration freeze."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash

from .artifact_paths import ProgramArtifactPaths
from .automatic_prefilter import (
    PREFILTER_GATE_POLICY,
    PREFILTER_GATE_POLICY_HASH,
    build_prefilter_route,
    evaluate_prefilter_events,
)
from .automatic_preregistration import build_candidate_preregistration
from .generated_candidate_adapter import GeneratedDirectionalEventAdapter
from .program_ledger import ProgramLedger
from .program_state import ProgramStateStore
from .program_v19 import _artifact_manifest


PREFILTER_START = "2020-01-01T00:00:00Z"
PREFILTER_END_EXCLUSIVE = "2023-01-01T00:00:00Z"
FORMAL_START = "2023-01-01T00:00:00Z"
FORMAL_END_EXCLUSIVE = "2025-01-01T00:00:00Z"
LOCKED_OOS_START = "2025-01-01T00:00:00Z"
LOCKED_OOS_END_EXCLUSIVE = "2026-05-10T00:00:00Z"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )


def _slice_frames(
    frames: Mapping[str, Mapping[str, pd.DataFrame]],
    *,
    start: str,
    end_exclusive: str,
) -> dict[str, dict[str, pd.DataFrame]]:
    start_at = pd.Timestamp(start)
    end_at = pd.Timestamp(end_exclusive)
    sliced: dict[str, dict[str, pd.DataFrame]] = {}
    for timeframe, symbol_frames in frames.items():
        sliced[timeframe] = {}
        for symbol, raw in symbol_frames.items():
            frame = raw.copy()
            dates = pd.to_datetime(
                frame["date"] if "date" in frame else frame.index,
                utc=True,
                errors="coerce",
            )
            mask = (dates >= start_at) & (dates < end_at)
            selected = frame.loc[mask].copy().reset_index(drop=True)
            if not selected.empty:
                sliced[timeframe][symbol] = selected
    return sliced


def _benchmark_events(
    *,
    candidate: Mapping[str, Any],
    candidate_frames: Mapping[str, pd.DataFrame],
    base_events: Sequence[Mapping[str, Any]],
    round_trip_cost_rate: float,
) -> list[dict[str, Any]]:
    direction = str(candidate["direction"])
    maximum_hold = int(candidate["maximumHoldBars"])
    normalized: dict[str, pd.DataFrame] = {}
    for symbol, raw in candidate_frames.items():
        frame = raw.copy()
        if "date" not in frame:
            frame["date"] = frame.index
        frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
        normalized[symbol] = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    rows: list[dict[str, Any]] = []
    for event in base_events:
        symbol = str(event["symbol"])
        frame = normalized.get(symbol)
        if frame is None:
            continue
        entry_index = int(event["signalBarIndex"]) + 1
        if entry_index >= len(frame):
            continue
        exit_index = min(entry_index + maximum_hold, len(frame) - 1)
        entry = float(event["entryPrice"])
        stop = float(event["initialStopPrice"])
        risk = abs(entry - stop)
        if risk <= 0:
            continue
        exit_price = float(frame.at[exit_index, "close"])
        gross_r = (exit_price - entry) / risk * (1.0 if direction == "long" else -1.0)
        cost_r = entry * float(round_trip_cost_rate) / risk
        observed = frame.iloc[entry_index : exit_index + 1]
        if direction == "long":
            mfe_r = (float(observed["high"].max()) - entry) / risk
            mae_r = (float(observed["low"].min()) - entry) / risk
        else:
            mfe_r = (entry - float(observed["low"].min())) / risk
            mae_r = (entry - float(observed["high"].max())) / risk
        rows.append(
            {
                **dict(event),
                "exitTimestamp": frame.at[exit_index, "date"].isoformat(),
                "exitPrice": exit_price,
                "exitReason": "same_signal_maximum_hold_benchmark",
                "grossR": gross_r,
                "costR": cost_r,
                "netR": gross_r - cost_r,
                "mfeR": mfe_r,
                "maeR": mae_r,
                "benchmark": True,
            }
        )
    return rows


def _frozen_policies(*, candidate_ids: list[str]) -> dict[str, dict[str, Any]]:
    split = {
        "schemaVersion": "automatic_split_policy_v1",
        "ordering": "chronological_utc",
        "prefilter": {"start": PREFILTER_START, "endExclusive": PREFILTER_END_EXCLUSIVE},
        "formal": {"start": FORMAL_START, "endExclusive": FORMAL_END_EXCLUSIVE},
        "futureLockedOos": {
            "start": LOCKED_OOS_START,
            "endExclusive": LOCKED_OOS_END_EXCLUSIVE,
            "accessBeforeV22FinalEvaluation": 0,
        },
        "formalFoldCount": 5,
        "purgeBars": 36,
        "embargoBars": 36,
        "resultDrivenMutationAllowed": False,
    }
    cost = {
        "schemaVersion": "automatic_cost_policy_v1",
        "baseRoundTripCostRate": 0.0012,
        "stressScenarios": [
            {"scenarioId": "base", "multiplier": 1.0, "roundTripCostRate": 0.0012},
            {"scenarioId": "cost_1_5x", "multiplier": 1.5, "roundTripCostRate": 0.0018},
            {"scenarioId": "cost_2_0x", "multiplier": 2.0, "roundTripCostRate": 0.0024},
        ],
        "fundingMissingMayBeFilledWithZero": False,
        "resultDrivenMutationAllowed": False,
    }
    capital = {
        "schemaVersion": "automatic_capital_policy_v1",
        "source": "v18_frozen_numeric_policy",
        "initialCapital": 10000.0,
        "riskPerTrade": 0.01,
        "maximumConcurrentPositions": 6,
        "maximumSingleSymbolRisk": 0.01,
        "maximumSameDirectionRisk": 0.04,
        "maximumOpenRisk": 0.06,
        "maximumCorrelationClusterRisk": 0.02,
        "maximumAbsolutePortfolioBeta": 1.5,
        "numericChangesFromV18": 0,
    }
    benchmark = {
        "schemaVersion": "automatic_benchmark_policy_v1",
        "mainGateBenchmark": "same_signal_maximum_hold",
        "diagnosticBenchmarks": ["no_trade"],
        "candidateEventIdentityMatched": True,
        "resultDrivenMutationAllowed": False,
    }
    statistics = {
        "schemaVersion": "automatic_statistical_policy_v1",
        "familyWiseTrialIds": candidate_ids,
        "methods": [
            "benjamini_hochberg",
            "benjamini_yekutieli",
            "deflated_sharpe_ratio",
            "probability_of_backtest_overfitting",
            "white_reality_check",
            "superior_predictive_ability",
        ],
        "unavailableMethodPolicy": "record_unavailable_with_reason",
        "postResultCandidateAdditionAllowed": False,
    }
    formal_gate = {
        "schemaVersion": "automatic_formal_gate_policy_v1",
        "minimumFormalEvents": {"1h": 120, "4h": 60},
        "minimumProfitFactor": 1.05,
        "minimumAverageNetR": 0.0,
        "minimumTotalNetR": 0.0,
        "maximumDrawdownPct": 15.0,
        "minimumStress1_5xProfitFactor": 1.0,
        "minimumStress1_5xAverageNetR": 0.0,
        "minimumPositiveFoldCount": 3,
        "maximumSingleInstrumentPositiveContribution": 0.45,
        "maximumSingleMonthPositiveContribution": 0.35,
        "targetRGateMode": "advisory",
        "universalTwoRHardGate": False,
        "resultDrivenRelaxationForbidden": True,
    }
    runtime = {
        "schemaVersion": "automatic_candidate_neutral_runtime_v1",
        "candidateAdapter": "generated_directional_event_adapter",
        "candidateSpecificImportsAllowedInFormalCore": False,
        "formalRunCommandInputs": ["preregistrationPath", "candidateId"],
        "artifactPathTemplate": "reports/formal_validation/{campaignId}/{candidateId}",
        "syntheticSecondCandidateFixtureRequired": True,
    }
    io_guard = {
        "schemaVersion": "automatic_io_guard_v1",
        "networkDuringFormal": "forbidden",
        "futureLockedOosReadBeforeFinalEvaluation": "forbidden",
        "resultArtifactPublish": "atomic_after_completion",
        "rawCredentialStorage": "forbidden",
        "withdrawApi": "absent",
    }
    return {
        "split": split,
        "cost": cost,
        "capital": capital,
        "benchmark": benchmark,
        "statistics": statistics,
        "formalGate": formal_gate,
        "runtime": runtime,
        "ioGuard": io_guard,
    }


def _hash_policy(name: str, payload: Mapping[str, Any]) -> str:
    return stable_hash(dict(payload), prefix=f"automatic_{name}_policy")


def run_v21_prefilter_and_freeze(
    *,
    reports_root: Path,
    research_root: Path,
    program_id: str,
    generated_at: str,
    implementation_commit: str,
    frames: Mapping[str, Mapping[str, pd.DataFrame]],
) -> dict[str, Any]:
    paths = ProgramArtifactPaths(Path(reports_root), program_id)
    state_store = ProgramStateStore(paths)
    state = state_store.load()
    campaign_id = str(state.active_campaign_id or f"{program_id}_campaign_01")
    campaign_root = paths.campaign(campaign_id)
    if state.stage == "prefilter_completed" and (campaign_root / "prefilter_route.json").is_file():
        route = _read_json(campaign_root / "prefilter_route.json")
        return {
            "programId": program_id,
            "campaignId": campaign_id,
            "status": "completed",
            "resumed": True,
            "candidateCount": len(_read_json(paths.program_root / "candidate_inventory.json")["candidates"]),
            "formalCandidateCount": len(route["formalCandidateIds"]),
            "formalRunCount": 0,
            "resultReadCount": 0,
            "terminalRoute": route.get("terminalRoute"),
        }
    if state.stage != "candidates_certified":
        raise ValueError(f"v21_stage_not_allowed:{state.stage}")
    if not implementation_commit.strip():
        raise ValueError("implementation_commit_required")

    inventory = _read_json(paths.program_root / "candidate_inventory.json")
    candidates = [dict(row) for row in inventory.get("candidates", [])]
    certifications = _read_json(
        paths.program_root / "candidate_structural_certification.json"
    ).get("certifications", [])
    certified = {
        str(row["candidateId"])
        for row in certifications
        if row.get("status") == "certified"
    }
    candidates = [row for row in candidates if str(row["candidateId"]) in certified]
    candidate_ids = [str(row["candidateId"]) for row in candidates]
    profiles = _read_json(paths.program_root / "data_profiles.json")
    profile = next(
        row
        for row in profiles["profiles"]
        if row.get("profileId") == "ohlcv_core_directional_v1"
    )
    baseline = _read_json(paths.program_root / "baseline_identity.json")
    snapshot_id = str(baseline["dataSnapshotId"])
    prefilter_frames = _slice_frames(
        frames, start=PREFILTER_START, end_exclusive=PREFILTER_END_EXCLUSIVE
    )

    results: list[dict[str, Any]] = []
    for candidate in candidates:
        timeframe = str(candidate["timeframe"])
        candidate_frames = prefilter_frames.get(timeframe, {})
        adapter = GeneratedDirectionalEventAdapter(candidate_id=str(candidate["candidateId"]))
        base_events = list(
            adapter.replay(
                candidate=candidate,
                frames=candidate_frames,
                round_trip_cost_rate=0.0012,
            )
        )
        stress_events = list(
            adapter.replay(
                candidate=candidate,
                frames=candidate_frames,
                round_trip_cost_rate=0.0018,
            )
        )
        benchmark_events = _benchmark_events(
            candidate=candidate,
            candidate_frames=candidate_frames,
            base_events=base_events,
            round_trip_cost_rate=0.0012,
        )
        results.append(
            evaluate_prefilter_events(
                candidate_id=str(candidate["candidateId"]),
                family_id=str(candidate["familyId"]),
                base_events=base_events,
                stress_events=stress_events,
                benchmark_events=benchmark_events,
            )
        )
    route = build_prefilter_route(results)

    policies = _frozen_policies(candidate_ids=candidate_ids)
    policy_hashes = {name: _hash_policy(name, payload) for name, payload in policies.items()}
    panel_plan = {
        "schemaVersion": "automatic_candidate_daily_return_panel_plan_v1",
        "campaignId": campaign_id,
        "candidateIds": candidate_ids,
        "candidateCount": len(candidate_ids),
        "dateWindow": policies["split"]["formal"],
        "universeHash": profile["universeHash"],
        "costHash": policy_hashes["cost"],
        "capitalPolicyHash": policy_hashes["capital"],
        "dailyReturnPanelReadCount": 0,
        "resultReadCount": 0,
        "postResultCandidateAdditionAllowed": False,
    }
    panel_hash = stable_hash(panel_plan, prefix="automatic_candidate_daily_return_panel_plan")
    panel_plan["candidatePanelHash"] = panel_hash
    multiple_testing = {
        "schemaVersion": "automatic_campaign_multiple_testing_scope_v1",
        "campaignId": campaign_id,
        "candidateIds": candidate_ids,
        "trialCount": len(candidate_ids),
        "statisticalPolicyHash": policy_hashes["statistics"],
        "scopeFrozenBeforeFormalResults": True,
        "postResultTrialAdditionAllowed": False,
        "resultReadCount": 0,
    }
    multiple_testing["scopeHash"] = stable_hash(
        multiple_testing, prefix="automatic_multiple_testing_scope"
    )
    locked_identity = {
        "schemaVersion": "automatic_future_locked_oos_identity_v1",
        "campaignId": campaign_id,
        "dataSnapshotId": snapshot_id,
        "window": policies["split"]["futureLockedOos"],
        "accessCount": 0,
        "contentReadCount": 0,
        "resultReadCount": 0,
        "status": "frozen_unread",
    }
    locked_identity["lockedOosIdentityHash"] = stable_hash(
        locked_identity, prefix="automatic_future_locked_oos_identity"
    )

    campaign_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        campaign_root / "prefilter_results.json",
        {
            "schemaVersion": "automatic_prefilter_results_v1",
            "campaignId": campaign_id,
            "candidateCount": len(results),
            "prefilterPassCount": sum(bool(row["passed"]) for row in results),
            "gatePolicy": PREFILTER_GATE_POLICY,
            "gatePolicyHash": PREFILTER_GATE_POLICY_HASH,
            "results": results,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosAccessCount": 0,
        },
    )
    metric_rows = [
        {
            "candidateId": row["candidateId"],
            "familyId": row["familyId"],
            "passed": row["passed"],
            **row["metrics"],
        }
        for row in results
    ]
    gate_rows = [
        {
            "candidateId": row["candidateId"],
            "familyId": row["familyId"],
            "gateName": gate_name,
            **gate,
        }
        for row in results
        for gate_name, gate in row["gates"].items()
    ]
    _write_csv(campaign_root / "prefilter_metric_matrix.csv", metric_rows)
    _write_csv(campaign_root / "prefilter_gate_matrix.csv", gate_rows)
    write_json_atomic(
        campaign_root / "prefilter_failure_attribution.json",
        {
            "schemaVersion": "automatic_prefilter_failure_attribution_v1",
            "candidateFailures": [
                {
                    "candidateId": row["candidateId"],
                    "familyId": row["familyId"],
                    "failedGates": row["failedGates"],
                }
                for row in results
                if row["failedGates"]
            ],
        },
    )
    write_json_atomic(campaign_root / "prefilter_route.json", route)
    write_json_atomic(campaign_root / "candidate_daily_return_panel_plan.json", panel_plan)
    write_json_atomic(campaign_root / "campaign_multiple_testing_scope.json", multiple_testing)
    write_json_atomic(campaign_root / "future_locked_oos_identity.json", locked_identity)
    (campaign_root / "future_locked_oos_access_ledger.jsonl").write_text("", encoding="utf-8")
    for name, payload in policies.items():
        write_json_atomic(
            campaign_root / f"{name}_policy.json",
            {**payload, f"{name}Hash": policy_hashes[name]},
        )

    bindings = {
        "dataProfileHash": str(profile["profileHash"]),
        "dataSnapshotHash": snapshot_id,
        "universeHash": str(profile["universeHash"]),
        "splitHash": policy_hashes["split"],
        "costHash": policy_hashes["cost"],
        "capitalPolicyHash": policy_hashes["capital"],
        "benchmarkHash": policy_hashes["benchmark"],
        "statisticalPolicyHash": policy_hashes["statistics"],
        "gateHash": policy_hashes["formalGate"],
        "runtimeHash": policy_hashes["runtime"],
        "ioGuardHash": policy_hashes["ioGuard"],
        "candidatePanelHash": panel_hash,
    }
    by_id = {str(row["candidateId"]): row for row in candidates}
    preregistrations: list[dict[str, Any]] = []
    prereg_root = Path(research_root) / "preregistrations"
    prereg_root.mkdir(parents=True, exist_ok=True)
    for candidate_id in route["formalCandidateIds"]:
        preregistration = build_candidate_preregistration(
            parent_campaign_id=campaign_id,
            candidate=by_id[candidate_id],
            implementation_commit=implementation_commit,
            generated_at=generated_at,
            bindings=bindings,
        )
        write_json_atomic(
            prereg_root / f"{preregistration['campaignId']}.json", preregistration
        )
        preregistrations.append(preregistration)
    parent = {
        "schemaVersion": "automatic_parent_campaign_preregistration_v1",
        "campaignId": campaign_id,
        "implementationCommit": implementation_commit,
        "generatedAt": generated_at,
        "candidateIds": route["formalCandidateIds"],
        "candidatePreregistrationHashes": {
            row["sourceCandidateId"]: row["preregistrationHash"]
            for row in preregistrations
        },
        "bindings": bindings,
        "multipleTestingScopeHash": multiple_testing["scopeHash"],
        "futureLockedOosIdentityHash": locked_identity["lockedOosIdentityHash"],
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    parent["parentPreregistrationHash"] = stable_hash(
        parent, prefix="automatic_parent_campaign_preregistration"
    )
    write_json_atomic(campaign_root / "parent_campaign_preregistration.json", parent)

    state = state.transition(
        stage="prefilter_completed",
        updated_at=generated_at,
        previous_checkpoint="v20",
        next_allowed_stage="formal_campaign_frozen",
        result_read_count=0,
    )
    state_store.save(state)
    state_store.write_checkpoint(
        stage="v21",
        created_at=generated_at,
        payload={
            "status": "completed",
            "campaignId": campaign_id,
            "candidateCount": len(results),
            "prefilterPassCount": sum(bool(row["passed"]) for row in results),
            "formalCandidateCount": len(route["formalCandidateIds"]),
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosAccessCount": 0,
            "terminalRoute": route.get("terminalRoute"),
        },
    )
    ProgramLedger(paths.ledger).append(
        event_type="v21_prefilter_and_preregistration_frozen",
        stage=state.stage,
        created_at=generated_at,
        payload={
            "campaignId": campaign_id,
            "candidateCount": len(results),
            "formalCandidateCount": len(route["formalCandidateIds"]),
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosAccessCount": 0,
        },
    )
    write_json_atomic(paths.artifact_manifest, _artifact_manifest(paths.program_root))
    return {
        "programId": program_id,
        "campaignId": campaign_id,
        "status": "completed",
        "candidateCount": len(results),
        "prefilterPassCount": sum(bool(row["passed"]) for row in results),
        "formalCandidateCount": len(route["formalCandidateIds"]),
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "terminalRoute": route.get("terminalRoute"),
        "artifactRoot": campaign_root.as_posix(),
    }


__all__ = ["run_v21_prefilter_and_freeze"]
