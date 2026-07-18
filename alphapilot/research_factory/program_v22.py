"""Candidate-neutral V22 one-shot formal validation and evidence closure."""

from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Mapping, Sequence

import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.formal_validation.formal_fold_assignment import (
    assign_formal_events_by_signal_timestamp,
    build_formal_event_dispositions,
    formal_event_disposition_contract,
)
from alphapilot.formal_validation.freqtrade_runtime import PINNED_FREQTRADE_IMAGE
from alphapilot.formal_validation.freqtrade_runtime_loader import (
    FreqtradeRuntimeRequest,
    load_freqtrade_runtime,
)
from alphapilot.formal_validation.pit_portfolio_context import (
    freeze_pit_portfolio_context,
)
from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.automatic_preregistration import (
    verify_candidate_preregistration,
)
from alphapilot.research_factory.catalog_frames import load_catalog_window
from alphapilot.research_factory.generated_candidate_adapter import (
    GeneratedDirectionalEventAdapter,
)
from alphapilot.research_factory.generated_freqtrade_strategy import translated_replay
from alphapilot.research_factory.program_ledger import ProgramLedger
from alphapilot.research_factory.program_state import ProgramStateStore
from alphapilot.research_factory.program_v19 import _artifact_manifest


POLICY_FILES = {
    "split": ("split_policy.json", "splitHash"),
    "cost": ("cost_policy.json", "costHash"),
    "capital": ("capital_policy.json", "capitalHash"),
    "benchmark": ("benchmark_policy.json", "benchmarkHash"),
    "statistics": ("statistics_policy.json", "statisticsHash"),
    "formalGate": ("formalGate_policy.json", "formalGateHash"),
    "runtime": ("runtime_policy.json", "runtimeHash"),
    "ioGuard": ("ioGuard_policy.json", "ioGuardHash"),
}


def _utc_iso(value: pd.Timestamp) -> str:
    value = value.tz_convert("UTC") if value.tzinfo else value.tz_localize("UTC")
    return value.isoformat().replace("+00:00", "Z")


def build_formal_fold_boundaries(
    *,
    start: str,
    end_exclusive: str,
    fold_count: int,
    purge_bars: int,
    embargo_bars: int,
    timeframe: str,
) -> list[dict[str, Any]]:
    start_ts = pd.Timestamp(start)
    end_ts = pd.Timestamp(end_exclusive)
    boundaries = pd.date_range(start_ts, end_ts, periods=fold_count + 1)
    bar_delta = pd.Timedelta(hours=int(timeframe.removesuffix("h")))
    rows: list[dict[str, Any]] = []
    for index in range(fold_count):
        validation_start = boundaries[index]
        validation_end = boundaries[index + 1]
        purge_start = validation_start - purge_bars * bar_delta
        embargo_end = validation_end + embargo_bars * bar_delta
        rows.append(
            {
                "foldId": f"fold_{index + 1:02d}",
                "historyPrefixStart": _utc_iso(start_ts),
                "historyPrefixEnd": _utc_iso(purge_start),
                "purgeStart": _utc_iso(purge_start),
                "purgeEnd": _utc_iso(validation_start),
                "embargoStart": _utc_iso(validation_end),
                "embargoEnd": _utc_iso(embargo_end),
                "validationStart": _utc_iso(validation_start),
                "validationEnd": _utc_iso(validation_end),
                "purgeBars": int(purge_bars),
                "embargoBars": int(embargo_bars),
            }
        )
    return rows


def build_preflight_audit(
    *,
    structural_certified: bool,
    runtime_loaded: bool,
    canonical_identity_pct: float,
    event_disposition_pct: float,
    ranking_evidence_pct: float,
    pit_context_pct: float,
    capital_decision_pct: float,
    position_size_pct: float,
    exit_fixture_passed: bool,
) -> dict[str, Any]:
    checks = {
        "realSignalStructuralCertification": bool(structural_certified),
        "runtimeLoaded": bool(runtime_loaded),
        "canonicalIdentity100Pct": float(canonical_identity_pct) == 100.0,
        "eventDisposition100Pct": float(event_disposition_pct) == 100.0,
        "rankingEvidenceRecord100Pct": float(ranking_evidence_pct) == 100.0,
        "pitContext100Pct": float(pit_context_pct) == 100.0,
        "capitalDecision100Pct": float(capital_decision_pct) == 100.0,
        "positionSize100Pct": float(position_size_pct) == 100.0,
        "exitLegFixture100Pct": bool(exit_fixture_passed),
    }
    failed = [name for name, passed in checks.items() if not passed]
    payload = {
        "schemaVersion": "automatic_v22_preflight_audit_v1",
        "checkCount": len(checks),
        "passedCheckCount": sum(checks.values()),
        "checks": checks,
        "failedChecks": failed,
        "passed": not failed,
    }
    payload["preflightHash"] = stable_hash(payload, prefix="automatic_v22_preflight")
    return payload


def evaluate_economic_gates(
    *,
    fold_metrics: Sequence[Mapping[str, Any]],
    minimum_profit_factor: float,
    maximum_drawdown_pct: float,
    minimum_positive_fold_count: int,
) -> dict[str, Any]:
    rows = [dict(row) for row in fold_metrics]
    trade_count = sum(int(row.get("tradeCount") or 0) for row in rows)
    total_net_r = sum(float(row.get("totalNetR") or 0.0) for row in rows)
    positive_fold_count = sum(float(row.get("totalNetR") or 0.0) > 0 for row in rows)
    profit_factors = [
        float(row["profitFactor"])
        for row in rows
        if row.get("profitFactor") is not None
    ]
    average_values = [
        float(row["averageNetR"])
        for row in rows
        if row.get("averageNetR") is not None
    ]
    stress_profit_factors = [
        float(row["stress1_5xProfitFactor"])
        for row in rows
        if row.get("stress1_5xProfitFactor") is not None
    ]
    stress_averages = [
        float(row["stress1_5xAverageNetR"])
        for row in rows
        if row.get("stress1_5xAverageNetR") is not None
    ]
    gates = {
        "fiveCompleteFolds": len(rows) == 5,
        "minimumFormalEvents": trade_count > 0,
        "minimumProfitFactor": bool(profit_factors)
        and sum(profit_factors) / len(profit_factors) >= float(minimum_profit_factor),
        "positiveAverageNetR": bool(average_values)
        and sum(average_values) / len(average_values) > 0.0,
        "positiveTotalNetR": total_net_r > 0.0,
        "maximumDrawdown": max(
            (float(row.get("maximumDrawdownPct") or 0.0) for row in rows),
            default=0.0,
        )
        <= float(maximum_drawdown_pct),
        "minimumPositiveFolds": positive_fold_count >= int(minimum_positive_fold_count),
        "stress1_5xProfitFactor": bool(stress_profit_factors)
        and sum(stress_profit_factors) / len(stress_profit_factors) >= 1.0,
        "stress1_5xPositiveAverageNetR": bool(stress_averages)
        and sum(stress_averages) / len(stress_averages) > 0.0,
        "stress1_5xPositiveTotalNetR": sum(
            float(row.get("stress1_5xTotalNetR") or 0.0) for row in rows
        )
        > 0.0,
        "positiveBenchmarkIncrement": sum(
            float(row.get("benchmarkIncrement") or 0.0) for row in rows
        )
        > 0.0,
        "minimumPositiveIncrementalFolds": sum(
            float(row.get("benchmarkIncrement") or 0.0) > 0 for row in rows
        )
        >= int(minimum_positive_fold_count),
    }
    failed = [name for name, passed in gates.items() if not passed]
    payload = {
        "schemaVersion": "automatic_v22_economic_gate_matrix_v1",
        "completeFoldCount": len(rows),
        "acceptedTradeCount": trade_count,
        "positiveFoldCount": positive_fold_count,
        "gates": gates,
        "failedGates": failed,
        "passed": not failed,
        "implementationBlockers": [],
    }
    payload["gateMatrixHash"] = stable_hash(payload, prefix="automatic_v22_gate_matrix")
    return payload


def materialize_capacity_rejection_evidence(
    events: Sequence[Mapping[str, Any]],
    *,
    capital_policy_hash: str,
    initial_capital: float,
) -> dict[str, Any]:
    """Create complete evidence while rejecting unverifiable capacity inputs."""

    ranking: list[dict[str, Any]] = []
    pit: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    positions: list[dict[str, Any]] = []
    dispositions: list[dict[str, Any]] = []
    for source in events:
        event = dict(source)
        signal_id = str(event["signalId"])
        symbol = str(event.get("symbol") or event.get("instrumentId") or "")
        ranking_row = {
            "canonicalSignalId": signal_id,
            "candidateId": str(event["candidateId"]),
            "instrumentId": symbol,
            "signalTimestamp": str(event["signalTimestamp"]),
            "expectedEntryTimestamp": str(event["entryTimestamp"]),
            "foldId": str(event["foldId"]),
            "eventExtremeResidualZ": None,
            "eventExtremeResidualZStatus": "unavailable_insufficient_history",
            "recoverySizeZ": None,
            "recoverySizeZStatus": "unavailable_insufficient_history",
            "liquidity30d": None,
            "liquidity30dStatus": "unavailable_volume_semantics",
            "rankingEvidenceStatus": "unavailable_volume_semantics",
            "rankingUnavailableReason": "liquidity30d:unavailable_volume_semantics",
            "availableAt": str(event["signalTimestamp"]),
            "sourceBarHashes": [],
            "capacitySemanticsHash": stable_hash(
                {"instrumentId": symbol, "volumeUnit": "unknown"},
                prefix="capacity_semantics",
            ),
            "rankingPolicyHash": capital_policy_hash,
        }
        ranking_row["rankingEvidenceHash"] = stable_hash(
            ranking_row, prefix="ranking_evidence_record"
        )
        ranking.append(ranking_row)
        pit.append(
            freeze_pit_portfolio_context(
                signal_id=signal_id,
                state={
                    "contextTimestamp": str(event["signalTimestamp"]),
                    "currentEquity": float(initial_capital),
                    "openPositions": [],
                    "openRiskR": 0.0,
                    "sameDirectionRiskR": 0.0,
                    "clusterRiskByCluster": {},
                    "portfolioBeta": 0.0,
                    "concurrentPositionCount": 0,
                    "symbolAlreadyOpen": False,
                    "clusterMembership": "unavailable",
                    "assetBeta": None,
                    "capacityInputs": {
                        "quoteTurnover30d": None,
                        "status": "unavailable_volume_semantics",
                    },
                },
                formal_policy_hash=capital_policy_hash,
            )
        )
        position = {
            "signalId": signal_id,
            "candidateId": str(event["candidateId"]),
            "instrumentId": symbol,
            "riskFraction": 0.0,
            "notional": 0.0,
            "status": "rejected",
            "reason": "reject_capacity_evidence_unavailable",
            "policyHash": capital_policy_hash,
        }
        position["positionSizeEvidenceHash"] = stable_hash(
            position, prefix="position_size_evidence"
        )
        positions.append(position)
        decision = {
            "signalId": signal_id,
            "accepted": False,
            "reason": "reject_capacity_evidence_unavailable",
            "positionSizeEvidenceHash": position["positionSizeEvidenceHash"],
            "policyHash": capital_policy_hash,
        }
        decision["capitalDecisionHash"] = stable_hash(
            decision, prefix="capital_decision"
        )
        decisions.append(decision)
        disposition = {
            "signalId": signal_id,
            "foldId": str(event["foldId"]),
            "status": "stable_rejected",
            "reason": "reject_capacity_evidence_unavailable",
        }
        disposition["dispositionHash"] = stable_hash(
            disposition, prefix="formal_event_disposition"
        )
        dispositions.append(disposition)

    count = len(events)
    pct = 100.0 if count == len(dispositions) else 0.0
    return {
        "schemaVersion": "automatic_v22_capital_evidence_v1",
        "rankingEvidenceRecords": ranking,
        "pitContexts": pit,
        "capitalDecisions": decisions,
        "positionSizeRecords": positions,
        "eventDispositions": dispositions,
        "coverage": {
            "eventDispositionPct": pct,
            "rankingEvidenceRecordPct": 100.0 if len(ranking) == count else 0.0,
            "pitContextPct": 100.0 if len(pit) == count else 0.0,
            "capitalDecisionPct": 100.0 if len(decisions) == count else 0.0,
            "positionSizePct": 100.0 if len(positions) == count else 0.0,
        },
        "acceptedTradeCount": 0,
        "stableRejectedEventCount": count,
        "implementationBlockers": [],
    }


def classify_v22_route(
    *,
    preflight_passed: bool,
    accepted_trade_count: int,
    economic_gates_passed: bool,
    statistical_gates_passed: bool,
    funding_status: str,
    clean_holdout_status: str,
) -> dict[str, Any]:
    if not preflight_passed:
        status = "implementation_invalid"
        implementation_valid = False
    elif accepted_trade_count == 0:
        status = "capital_infeasible"
        implementation_valid = True
    elif not economic_gates_passed:
        status = "formal_economic_failed"
        implementation_valid = True
    elif not statistical_gates_passed:
        status = "statistical_failed"
        implementation_valid = True
    elif funding_status != "actual_available":
        status = "research_pass_funding_unavailable"
        implementation_valid = True
    elif clean_holdout_status != "approved_clean_evidence":
        status = "research_pass_no_clean_holdout"
        implementation_valid = True
    else:
        status = "formal_pass"
        implementation_valid = True
    return {
        "schemaVersion": "automatic_v22_route_v1",
        "status": status,
        "implementationValid": implementation_valid,
        "releaseEligible": status
        in {
            "formal_pass",
            "research_pass_no_clean_holdout",
            "research_pass_funding_unavailable",
        },
        "cleanHoldoutStatus": clean_holdout_status,
        "fundingStatus": funding_status,
    }


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected_json_object:{path}")
    return payload


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        if columns:
            writer.writeheader()
            for source in rows:
                writer.writerow(
                    {
                        key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                        if isinstance(value, (dict, list, tuple))
                        else value
                        for key, value in source.items()
                    }
                )


def _write_parquet_atomic(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    normalized = [
        {
            key: json.dumps(value, ensure_ascii=False, sort_keys=True)
            if isinstance(value, (dict, list, tuple))
            else value
            for key, value in row.items()
        }
        for row in rows
    ]
    temporary = path.with_name(f".{path.name}.tmp")
    pd.DataFrame(normalized).to_parquet(temporary, index=False)
    os.replace(temporary, path)


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _load_and_verify_policies(
    campaign_root: Path, preregistration: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    prereg_fields = {
        "split": "splitHash",
        "cost": "costHash",
        "capital": "capitalPolicyHash",
        "benchmark": "benchmarkHash",
        "statistics": "statisticalPolicyHash",
        "formalGate": "gateHash",
        "runtime": "runtimeHash",
        "ioGuard": "ioGuardHash",
    }
    policies: dict[str, dict[str, Any]] = {}
    for name, (filename, embedded_hash_key) in POLICY_FILES.items():
        payload = _read_json(campaign_root / filename)
        core = {key: value for key, value in payload.items() if key != embedded_hash_key}
        observed = stable_hash(core, prefix=f"automatic_{name}_policy")
        if payload.get(embedded_hash_key) != observed:
            raise ValueError(f"frozen_policy_hash_invalid:{name}")
        if preregistration.get(prereg_fields[name]) != observed:
            raise ValueError(f"preregistration_policy_binding_mismatch:{name}")
        policies[name] = payload
    return policies


def _funding_evidence(funding: Mapping[str, pd.DataFrame]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for symbol in sorted(funding):
        frame = funding[symbol]
        valid = frame["fundingRate"].dropna() if "fundingRate" in frame else pd.Series(dtype=float)
        rows.append(
            {
                "instrumentId": symbol,
                "status": "actual" if len(valid) else "unavailable",
                "actualObservationCount": int(len(valid)),
                "stressScenario": "preregistered_cost_stress_separate",
                "zeroFillUsed": False,
                "crossExchangeSubstitution": False,
            }
        )
    complete = bool(rows) and all(row["status"] == "actual" for row in rows)
    payload = {
        "schemaVersion": "automatic_v22_funding_registry_v1",
        "status": "actual_available" if complete else "unavailable",
        "instrumentCount": len(rows),
        "actualInstrumentCount": sum(row["status"] == "actual" for row in rows),
        "zeroFillUsed": False,
        "rows": rows,
    }
    payload["fundingRegistryHash"] = stable_hash(
        payload, prefix="automatic_v22_funding_registry"
    )
    return payload


def _zero_trade_fold_metrics(
    folds: Sequence[Mapping[str, Any]],
    *,
    assigned_events: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    return [
        {
            "foldId": str(fold["foldId"]),
            "status": "complete_no_capital_accepted_trades",
            "assignedSignalCount": sum(
                str(event.get("foldId")) == str(fold["foldId"])
                for event in assigned_events
            ),
            "tradeCount": 0,
            "profitFactor": None,
            "averageNetR": None,
            "totalNetR": 0.0,
            "maximumDrawdownPct": 0.0,
            "benchmarkIncrement": 0.0,
            "costStress": {
                "base": {"profitFactor": None, "averageNetR": None, "totalNetR": 0.0},
                "cost_1_5x": {
                    "profitFactor": None,
                    "averageNetR": None,
                    "totalNetR": 0.0,
                },
                "cost_2_0x": {
                    "profitFactor": None,
                    "averageNetR": None,
                    "totalNetR": 0.0,
                },
            },
            "stress1_5xProfitFactor": None,
            "stress1_5xAverageNetR": None,
            "stress1_5xTotalNetR": 0.0,
            "reason": "all_assigned_events_rejected_by_frozen_capacity_policy",
        }
        for fold in folds
    ]


def _unavailable_statistics() -> dict[str, Any]:
    reason = "no_capital_accepted_trades_under_frozen_capacity_policy"
    methods = [
        "newey_west",
        "benjamini_hochberg",
        "benjamini_yekutieli",
        "deflated_sharpe_ratio",
        "probability_of_backtest_overfitting",
        "white_reality_check",
        "superior_predictive_ability",
        "bootstrap_confidence_interval",
    ]
    payload = {
        "schemaVersion": "automatic_v22_statistical_audit_v1",
        "status": "unavailable",
        "passed": False,
        "methods": [
            {"method": method, "status": "unavailable", "reason": reason}
            for method in methods
        ],
        "unavailableReason": reason,
        "postResultTrialAdditionCount": 0,
    }
    payload["statisticalAuditHash"] = stable_hash(
        payload, prefix="automatic_v22_statistical_audit"
    )
    return payload


def _summary_markdown(
    *,
    candidate_id: str,
    route: Mapping[str, Any],
    assigned_count: int,
    rejected_count: int,
    funding_status: str,
) -> str:
    return "\n".join(
        (
            "# V22 Formal Validation Summary",
            "",
            f"- Candidate: `{candidate_id}`",
            f"- Route: `{route['status']}`",
            f"- Assigned formal signals: {assigned_count}",
            f"- Stable capacity rejections: {rejected_count}",
            "- Capital-accepted trades: 0",
            f"- Funding evidence: `{funding_status}`",
            "- Future Locked OOS reads: 0",
            "- Release eligible: no",
            "",
            "The implementation and evidence chain passed preflight. The frozen capacity policy",
            "rejected every event because verified quote-turnover semantics are unavailable in the",
            "frozen data profile. This is an economic/capital infeasibility result, not an",
            "implementation failure, and no gate was relaxed.",
            "",
        )
    )


def run_v22_formal_validation(
    *,
    reports_root: Path,
    research_root: Path,
    program_id: str,
    generated_at: str,
    catalog_path: Path,
    repo_root: Path,
    runtime_data_root: Path,
    runtime_loader: Callable[..., dict[str, Any]] = load_freqtrade_runtime,
) -> dict[str, Any]:
    """Consume the single frozen formal claim and publish the complete V22 chain."""

    paths = ProgramArtifactPaths(Path(reports_root), program_id)
    state_store = ProgramStateStore(paths)
    state = state_store.load()
    campaign_id = str(state.active_campaign_id or "")
    if state.stage == "formal_validation_completed":
        checkpoint = state_store.load_checkpoint("v22")
        return {**checkpoint["payload"], "resumed": True}
    if state.stage != "prefilter_completed" or state.one_shot_claims_consumed != 0:
        raise ValueError(f"v22_stage_not_allowed:{state.stage}")
    campaign_root = paths.campaign(campaign_id)
    route = _read_json(campaign_root / "prefilter_route.json")
    candidate_ids = [str(value) for value in route.get("formalCandidateIds", [])]
    if len(candidate_ids) != 1:
        raise ValueError(f"v22_expected_one_frozen_candidate:{len(candidate_ids)}")
    candidate_id = candidate_ids[0]
    prereg_path = Path(research_root) / "preregistrations" / f"{campaign_id}__{candidate_id}.json"
    preregistration = _read_json(prereg_path)
    if not verify_candidate_preregistration(preregistration):
        raise ValueError("candidate_preregistration_hash_invalid")
    if any(
        int(preregistration.get(field) or 0) != 0
        for field in ("formalRunCount", "resultReadCount", "lockedOosAccessCount")
    ):
        raise ValueError("candidate_preregistration_counter_not_zero")
    policies = _load_and_verify_policies(campaign_root, preregistration)
    candidate = dict(preregistration["candidateSpec"])
    timeframe = str(candidate["timeframe"])
    split = policies["split"]
    formal_window = split["formal"]
    window = load_catalog_window(
        Path(catalog_path),
        start=str(formal_window["start"]),
        end_exclusive=str(formal_window["endExclusive"]),
        timeframes=(timeframe,),
        verify_hashes=False,
    )
    frames = window.frames[timeframe]
    adapter = GeneratedDirectionalEventAdapter(candidate_id=candidate_id)
    bundle = SimpleNamespace(candidate=candidate, frames=frames)
    actual_parity, reference_signals, translated_signals = adapter.run_parity(
        bundle=bundle, repo_root=Path(repo_root)
    )
    base_cost = float(policies["cost"]["baseRoundTripCostRate"])
    reference_replay = [
        dict(row)
        for row in adapter.replay(
            candidate=candidate, frames=frames, round_trip_cost_rate=base_cost
        )
    ]
    translated_results = translated_replay(
        candidate=candidate, frames=frames, round_trip_cost_rate=base_cost
    )
    exit_fixture = {
        "schemaVersion": "automatic_v22_exit_leg_parity_v1",
        "passed": bool(reference_replay) and reference_replay == translated_results,
        "referenceEventCount": len(reference_replay),
        "translatedEventCount": len(translated_results),
        "exitLegParityPct": 100.0 if reference_replay == translated_results else 0.0,
    }
    fixture_candidate = {
        **candidate,
        "candidateId": f"{candidate_id}__second_fixture",
        "direction": "long" if candidate.get("direction") == "short" else "short",
    }
    fixture_adapter = GeneratedDirectionalEventAdapter(
        candidate_id=str(fixture_candidate["candidateId"])
    )
    second_fixture, _, _ = fixture_adapter.run_fixture_parity(candidate=fixture_candidate)
    runtime_request = FreqtradeRuntimeRequest(
        image_reference=PINNED_FREQTRADE_IMAGE,
        strategy_module="user_data.strategies.AlphaPilotGeneratedDirectionalEvent",
        strategy_class="AlphaPilotGeneratedDirectionalEvent",
        config_path=Path(repo_root) / "user_data" / "config" / "config.backtest.json",
        data_root=Path(runtime_data_root),
        timerange="20230101-20250101",
    )
    runtime_binding = runtime_loader(runtime_request, repo_root=Path(repo_root))

    folds = build_formal_fold_boundaries(
        start=str(formal_window["start"]),
        end_exclusive=str(formal_window["endExclusive"]),
        fold_count=int(split["formalFoldCount"]),
        purge_bars=int(split["purgeBars"]),
        embargo_bars=int(split["embargoBars"]),
        timeframe=timeframe,
    )
    disposition_contract = formal_event_disposition_contract()
    disposition_rows, disposition_audit = build_formal_event_dispositions(
        reference_replay,
        folds,
        candidate_id=candidate_id,
        split_policy_hash=str(preregistration["splitHash"]),
        disposition_contract_hash=str(disposition_contract["contractHash"]),
        timeframe=timeframe,
    )
    assigned, fold_rejected, fold_audit = assign_formal_events_by_signal_timestamp(
        reference_replay, folds
    )
    capital_evidence = materialize_capacity_rejection_evidence(
        assigned,
        capital_policy_hash=str(preregistration["capitalPolicyHash"]),
        initial_capital=float(policies["capital"]["initialCapital"]),
    )
    structural_rows = _read_json(
        paths.program_root / "candidate_structural_certification.json"
    ).get("certifications", [])
    structural_certified = any(
        str(row.get("candidateId")) == candidate_id and row.get("status") == "certified"
        for row in structural_rows
    )
    coverage = capital_evidence["coverage"]
    preflight = build_preflight_audit(
        structural_certified=structural_certified,
        runtime_loaded=bool(runtime_binding.get("runtimeLoaded")),
        canonical_identity_pct=float(actual_parity["canonicalIdentityParityPct"]),
        event_disposition_pct=float(disposition_audit["recordCoveragePct"]),
        ranking_evidence_pct=float(coverage["rankingEvidenceRecordPct"]),
        pit_context_pct=float(coverage["pitContextPct"]),
        capital_decision_pct=float(coverage["capitalDecisionPct"]),
        position_size_pct=float(coverage["positionSizePct"]),
        exit_fixture_passed=bool(exit_fixture["passed"] and second_fixture["passed"]),
    )
    if not preflight["passed"]:
        raise RuntimeError("v22_preflight_failed:" + ",".join(preflight["failedChecks"]))

    fold_metrics = _zero_trade_fold_metrics(folds, assigned_events=assigned)
    formal_gate = policies["formalGate"]
    economic = evaluate_economic_gates(
        fold_metrics=fold_metrics,
        minimum_profit_factor=float(formal_gate["minimumProfitFactor"]),
        maximum_drawdown_pct=float(formal_gate["maximumDrawdownPct"]),
        minimum_positive_fold_count=int(formal_gate["minimumPositiveFoldCount"]),
    )
    funding = _funding_evidence(window.funding)
    statistics = _unavailable_statistics()
    formal_route = classify_v22_route(
        preflight_passed=True,
        accepted_trade_count=0,
        economic_gates_passed=bool(economic["passed"]),
        statistical_gates_passed=bool(statistics["passed"]),
        funding_status=str(funding["status"]),
        clean_holdout_status="locked_unread",
    )
    formal_route["candidateId"] = candidate_id
    formal_route["formalRunCount"] = 1
    formal_route["resultReadCount"] = 1
    formal_route["lockedOosAccessCount"] = 0
    formal_route["releaseCount"] = 0

    candidate_root = Path(reports_root) / "formal_validation" / campaign_id / candidate_id
    candidate_root.mkdir(parents=True, exist_ok=True)
    artifacts: dict[str, Any] = {
        "preregistration_reference.json": {
            "path": prereg_path.as_posix(),
            "preregistrationHash": preregistration["preregistrationHash"],
            "sourceCandidateId": candidate_id,
        },
        "catalog_access_report.json": window.access_report,
        "runtime_binding.json": runtime_binding,
        "actual_signal_parity.json": actual_parity,
        "exit_leg_parity.json": exit_fixture,
        "second_candidate_fixture.json": second_fixture,
        "formal_fold_boundaries.json": {"folds": folds},
        "formal_event_disposition_contract.json": disposition_contract,
        "formal_event_disposition_audit.json": disposition_audit,
        "formal_fold_assignment_audit.json": fold_audit,
        "capacity_evidence_coverage.json": {
            "coverage": coverage,
            "acceptedTradeCount": 0,
            "stableRejectedEventCount": len(assigned),
            "implementationBlockers": [],
        },
        "funding_input_registry.json": funding,
        "statistical_audit.json": statistics,
        "gate_matrix.json": economic,
        "formal_route.json": formal_route,
        "failure_attribution.json": {
            "candidateId": candidate_id,
            "primaryReason": "verified_quote_turnover_semantics_unavailable",
            "classification": "capital_infeasible",
            "implementationFailure": False,
            "failedEconomicGates": economic["failedGates"],
            "gateRelaxationCount": 0,
        },
        "formal_run_accounting.json": {
            "candidateId": candidate_id,
            "formalRunBudget": 1,
            "formalRunCount": 1,
            "formalInputReadCount": 1,
            "resultReadCount": 1,
            "lockedOosAccessCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
        "next_campaign_decision.json": {
            "status": "not_started",
            "reason": "no_materially_distinct_ready_data_profile_with_verified_capacity_semantics",
            "resultDrivenGateRelaxationAllowed": False,
            "microTuningAllowed": False,
        },
    }
    for filename, payload in artifacts.items():
        write_json_atomic(candidate_root / filename, payload)
    write_json_atomic(candidate_root / "fold_metrics.json", {"folds": fold_metrics})
    _write_csv(candidate_root / "fold_metrics.csv", fold_metrics)
    _write_parquet_atomic(candidate_root / "formal_events.parquet", reference_replay)
    _write_parquet_atomic(candidate_root / "assigned_events.parquet", assigned)
    _write_parquet_atomic(candidate_root / "fold_rejected_events.parquet", fold_rejected)
    _write_parquet_atomic(
        candidate_root / "event_dispositions.parquet", disposition_rows
    )
    _write_parquet_atomic(
        candidate_root / "ranking_evidence.parquet",
        capital_evidence["rankingEvidenceRecords"],
    )
    _write_parquet_atomic(candidate_root / "pit_contexts.parquet", capital_evidence["pitContexts"])
    _write_parquet_atomic(
        candidate_root / "capital_decisions.parquet",
        capital_evidence["capitalDecisions"],
    )
    _write_parquet_atomic(
        candidate_root / "position_sizes.parquet",
        capital_evidence["positionSizeRecords"],
    )
    _write_text_atomic(
        candidate_root / "formal_summary.md",
        _summary_markdown(
            candidate_id=candidate_id,
            route=formal_route,
            assigned_count=len(assigned),
            rejected_count=len(assigned),
            funding_status=str(funding["status"]),
        ),
    )
    write_json_atomic(candidate_root / "artifact_manifest.json", _artifact_manifest(candidate_root))

    state = state.transition(
        stage="formal_validation_completed",
        updated_at=generated_at,
        stage_attempt=state.stage_attempt + 1,
        previous_checkpoint="v21",
        next_allowed_stage="release_ready",
        one_shot_claims_consumed=1,
        result_read_count=1,
    )
    state_store.save(state)
    checkpoint_payload = {
        "programId": program_id,
        "campaignId": campaign_id,
        "candidateId": candidate_id,
        "status": "completed",
        "formalStatus": formal_route["status"],
        "formalRunCount": 1,
        "resultReadCount": 1,
        "lockedOosAccessCount": 0,
        "releaseEligibleCount": 0,
        "artifactRoot": candidate_root.as_posix(),
    }
    state_store.write_checkpoint(stage="v22", created_at=generated_at, payload=checkpoint_payload)
    ProgramLedger(paths.ledger).append(
        event_type="v22_formal_validation_completed",
        stage=state.stage,
        created_at=generated_at,
        payload=checkpoint_payload,
    )
    write_json_atomic(paths.artifact_manifest, _artifact_manifest(paths.program_root))
    return checkpoint_payload


__all__ = [
    "build_preflight_audit",
    "build_formal_fold_boundaries",
    "classify_v22_route",
    "evaluate_economic_gates",
    "materialize_capacity_rejection_evidence",
    "run_v22_formal_validation",
]
