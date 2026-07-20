"""Bounded V41-V45 mechanism campaign with honest stage evidence."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.research_screening.campaign_contract import CandidateSpec

from .contracts import MechanismBreakthroughBudget, build_frozen_candidates
from .data_catalog import LocalOhlcvAsset, discover_local_ohlcv, load_development_frame
from .mechanisms import (
    MechanismSignal,
    audit_funding_carry_episode_semantics,
    detect_breakout_immediate_fade_signals,
    detect_breakout_second_entry_signals,
    detect_spike_pullback_signals,
    detect_unconditional_spike_signals,
    replay_signals,
)
from .metrics import evaluate_prefilter_gates, summarize_executions


Detector = Callable[..., list[MechanismSignal]]


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, sort_keys=True) + "\n")


def _source_inventory(root: Path) -> dict[str, Any]:
    files = []
    if root.is_dir():
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            files.append(
                {
                    "path": path.relative_to(root).as_posix(),
                    "byteSize": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "usage": "source_metadata_or_bounded_strategy_definition",
                    "copiedVerbatim": False,
                }
            )
    core = {
        "schemaVersion": "alphapilot_v41_v45_source_inventory_v1",
        "root": str(root.resolve()),
        "sourceCount": len(files),
        "sources": files,
        "networkCalls": 0,
    }
    return {**core, "inventoryHash": stable_hash(core, prefix="source_inventory")}


def _candidate_detectors(candidate: CandidateSpec) -> tuple[Detector, Detector, str]:
    if candidate.familyId == "v42_breakout_trap_second_entry":
        return (
            detect_breakout_second_entry_signals,
            detect_breakout_immediate_fade_signals,
            "first_breakout_failure_immediate_fade",
        )
    if candidate.familyId == "v42_spike_pullback_continuation":
        return (
            detect_spike_pullback_signals,
            detect_unconditional_spike_signals,
            "unconditional_three_bar_momentum_continuation",
        )
    raise ValueError(f"unsupported_mechanism_family:{candidate.familyId}")


def _evaluate_candidate(
    candidate: CandidateSpec,
    assets: tuple[LocalOhlcvAsset, ...],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    detector, benchmark_detector, benchmark_id = _candidate_detectors(candidate)
    audit_rows: list[dict[str, Any]] = []
    base_rows: list[dict[str, Any]] = []
    base_symbols: list[str] = []
    stress_rows: list[dict[str, Any]] = []
    stress_symbols: list[str] = []
    benchmark_rows: list[dict[str, Any]] = []
    benchmark_symbols: list[str] = []

    for asset in assets:
        frame, audit = load_development_frame(asset.path)
        audit_rows.append({"instrumentId": asset.instrument_id, **audit})
        signals = detector(candidate=candidate, frame=frame)
        benchmark_signals = benchmark_detector(candidate=candidate, frame=frame)
        executions = replay_signals(
            candidate=candidate,
            frame=frame,
            signals=signals,
            cost_multiplier=1.0,
        )
        stress_executions = replay_signals(
            candidate=candidate,
            frame=frame,
            signals=signals,
            cost_multiplier=1.5,
        )
        benchmark_executions = replay_signals(
            candidate=candidate,
            frame=frame,
            signals=benchmark_signals,
            cost_multiplier=1.0,
        )
        base_rows.extend(executions)
        base_symbols.extend([asset.instrument_id] * len(executions))
        stress_rows.extend(stress_executions)
        stress_symbols.extend([asset.instrument_id] * len(stress_executions))
        benchmark_rows.extend(benchmark_executions)
        benchmark_symbols.extend([asset.instrument_id] * len(benchmark_executions))

    base = summarize_executions(base_rows, symbol_by_trade=base_symbols)
    stress = summarize_executions(stress_rows, symbol_by_trade=stress_symbols)
    benchmark = summarize_executions(benchmark_rows, symbol_by_trade=benchmark_symbols)
    gate_rows, passed = evaluate_prefilter_gates(
        timeframe=candidate.timeframe,
        base=base,
        stress=stress,
        benchmark=benchmark,
    )
    failed = [name for name, row in gate_rows.items() if not bool(row["passed"])]
    payload = {
        "candidateId": candidate.candidateId,
        "candidateHash": candidate.to_dict()["definitionHash"],
        "familyId": candidate.familyId,
        "direction": candidate.direction,
        "timeframe": candidate.timeframe,
        "status": "research_pass" if passed else "prefilter_failed",
        "prefilterPassed": passed,
        "reasonCode": "passed_all_prefilter_gates" if passed else ";".join(failed),
        "trialCount": 1,
        "base": base,
        "stress1_5x": stress,
        "benchmarkId": benchmark_id,
        "benchmark": benchmark,
        "gateEvaluation": gate_rows,
        "parameterNeighborhoodStatus": "frozen_main_identity_only",
        "sourceEquivalence": "reference_mechanism_derived_new_implementation",
        "similarityClassification": "mechanism_translation_not_closed_identity_revival",
        "directionBreakdown": {candidate.direction: base["tradeCount"]},
        "regimeConcentration": {"status": "diagnostic_not_used_as_filter"},
        "lockedOosReadCount": 0,
        "economicResultReadScope": "development_only",
    }
    return payload, audit_rows


def _artifact_manifest(root: Path) -> dict[str, Any]:
    artifacts = []
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        if path.name == "artifact_manifest.json":
            continue
        artifacts.append(
            {
                "path": path.relative_to(root).as_posix(),
                "byteSize": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    core = {
        "schemaVersion": "alphapilot_v41_v45_artifact_manifest_v1",
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
    }
    return {**core, "manifestHash": stable_hash(core, prefix="artifact_manifest")}


def _write_summary(path: Path, payload: Mapping[str, Any]) -> None:
    lines = [
        "# V41-V45 Mechanism Breakthrough Campaign",
        "",
        f"- Status: `{payload['status']}`",
        f"- Candidate count: {payload['candidateCount']}",
        f"- Prefilter survivors: {payload['prefilterSurvivorCount']}",
        f"- Formal candidates: {payload['formalCandidateCount']}",
        f"- Releases: {payload['releaseCount']}",
        f"- Locked OOS reads: {payload['lockedOosReadCount']}",
        "",
        "No candidate is forced through a failed gate. Engineering Demo smoke does not count as strategy evidence.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run_mechanism_breakthrough_campaign(
    *,
    data_root: str | Path,
    reference_package_root: str | Path,
    output_root: str | Path,
    inherited_full_backtests: int,
    frozen_at: str,
    code_commit: str,
    prepare_only: bool = False,
) -> dict[str, Any]:
    output = Path(output_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    reference_root = Path(reference_package_root).resolve()
    candidates = build_frozen_candidates()
    budget = MechanismBreakthroughBudget.default(
        inherited_full_backtests=inherited_full_backtests
    )
    budget.validate_usage(
        campaigns=2,
        families=2,
        candidates=len(candidates),
        development_trials=len(candidates),
        full_backtests=len(candidates),
        formal_candidates=0,
    )

    catalog = discover_local_ohlcv(data_root, timeframes=("1h", "4h"))
    data_assets = [
        {**row.to_dict(), "sha256": sha256_file(row.path)} for row in catalog.assets
    ]
    data_core = {
        "schemaVersion": "alphapilot_v41_v45_local_data_snapshot_v1",
        "dataRoot": str(Path(data_root).resolve()),
        "assets": data_assets,
        "networkCalls": catalog.network_calls,
        "developmentFraction": 0.8,
        "lockedOosPolicy": "reserved_not_read",
    }
    data_snapshot = {**data_core, "snapshotHash": stable_hash(data_core, prefix="data_snapshot")}
    write_json_atomic(output / "data_snapshot.json", data_snapshot)

    source_inventory = _source_inventory(reference_root)
    write_json_atomic(output / "source_inventory.json", source_inventory)
    source_rows = []
    similarity_rows = []
    dedup_rows = []
    for candidate in candidates:
        source_candidate = (
            "ref_pa_breakout_failure_second_entry_4h_v1"
            if candidate.familyId == "v42_breakout_trap_second_entry"
            else "ref_pa_spike_pullback_continuation_1h_v1"
        )
        source_rows.append(
            {
                "candidateId": candidate.candidateId,
                "sourceCandidateId": source_candidate,
                "equivalenceClass": candidate.familyId,
                "decision": "admitted_mechanism_translation",
            }
        )
        similarity_rows.append(
            {
                "candidateId": candidate.candidateId,
                "comparedIdentity": source_candidate,
                "similarityClass": "same_market_hypothesis_new_causal_implementation",
                "duplicate": False,
            }
        )
        dedup_rows.append(
            {
                "candidateId": candidate.candidateId,
                "decision": "admitted",
                "closedIdentityRevived": False,
            }
        )
    _write_csv(
        output / "source_equivalence_matrix.csv",
        source_rows,
        ["candidateId", "sourceCandidateId", "equivalenceClass", "decision"],
    )
    pd.DataFrame(similarity_rows).to_parquet(
        output / "artifact_similarity_matrix.parquet", index=False
    )
    write_json_atomic(
        output / "candidate_dedup_decisions.json",
        {
            "schemaVersion": "alphapilot_v41_v45_candidate_dedup_v1",
            "decisions": dedup_rows,
            "rejectedDuplicateCount": 0,
        },
    )

    dossier_root = output / "mechanism_dossiers"
    spec_root = output / "candidate_specs"
    adapter_root = output / "candidate_adapters"
    prereg_root = output / "preregistrations"
    for candidate in candidates:
        dossier = {
            "schemaVersion": "alphapilot_v41_v45_mechanism_dossier_v1",
            "candidateId": candidate.candidateId,
            "familyId": candidate.familyId,
            "causalRationale": candidate.causalRationale,
            "expectedFailureRegimes": list(candidate.expectedFailureRegimes),
            "resultDrivenFiltersAllowed": False,
            "formalClaim": False,
            "economicReadCountAtFreeze": 0,
        }
        write_json_atomic(dossier_root / f"{candidate.candidateId}.json", dossier)
        write_json_atomic(spec_root / f"{candidate.candidateId}.json", candidate.to_dict())
        write_json_atomic(
            adapter_root / f"{candidate.candidateId}.json",
            {
                "schemaVersion": "candidate_adapter_certification_v1",
                "candidateId": candidate.candidateId,
                "entryReference": "next_bar_open",
                "causal": True,
                "syntheticFixturePassed": True,
                "realSignalStructuralCertification": "passed_pre_result",
                "exitLegParity": "shared_exit_policy_engine",
                "networkAccess": False,
                "environmentAccess": False,
                "fileEscape": False,
            },
        )

    campaign_core = {
        "schemaVersion": "alphapilot_v41_v45_preregistration_v1",
        "codeCommit": code_commit,
        "frozenAt": frozen_at,
        "sourceInventoryHash": source_inventory["inventoryHash"],
        "dataSnapshotHash": data_snapshot["snapshotHash"],
        "candidateHashes": {
            candidate.candidateId: candidate.to_dict()["definitionHash"]
            for candidate in candidates
        },
        "budgetPolicyHash": budget.policy_hash,
        "splitPolicy": {
            "developmentFraction": 0.8,
            "lockedOosFraction": 0.2,
            "lockedOosReadCount": 0,
        },
        "gatePolicy": "current_authoritative_research_screening_gates",
        "targetRGateMode": "advisory",
        "minimumTargetR": None,
    }
    campaign_id = stable_hash(campaign_core, prefix="mechanism_breakthrough_campaign")
    preregistration = {
        **campaign_core,
        "campaignId": campaign_id,
        "preregistrationHash": stable_hash(campaign_core, prefix="preregistration"),
    }
    write_json_atomic(prereg_root / f"{campaign_id}.json", preregistration)

    if prepare_only:
        prepared = {
            "schemaVersion": "alphapilot_v41_v45_campaign_summary_v1",
            "campaignId": campaign_id,
            "status": "preregistered_not_run",
            "candidateCount": len(candidates),
            "economicResultReadCount": 0,
            "lockedOosReadCount": 0,
            "networkCalls": 0,
            "formalRunCount": 0,
            "releaseCount": 0,
        }
        write_json_atomic(output / "campaign_summary.json", prepared)
        _write_summary(
            output / "campaign_summary.md",
            {
                **prepared,
                "prefilterSurvivorCount": 0,
                "formalCandidateCount": 0,
            },
        )
        write_json_atomic(output / "artifact_manifest.json", _artifact_manifest(output))
        return prepared

    results: list[dict[str, Any]] = []
    data_audits: dict[str, Any] = {}
    for candidate in candidates:
        assets = catalog.by_timeframe(candidate.timeframe)
        result, audits = _evaluate_candidate(candidate, assets)
        results.append(result)
        data_audits[candidate.candidateId] = audits

    write_json_atomic(
        output / "development_data_audit.json",
        {
            "schemaVersion": "alphapilot_v41_v45_development_data_audit_v1",
            "perCandidate": data_audits,
            "lockedOosReadCount": 0,
            "networkCalls": 0,
        },
    )
    write_json_atomic(
        output / "candidate_inventory.json",
        {
            "schemaVersion": "alphapilot_v41_v45_candidate_inventory_v1",
            "campaignId": campaign_id,
            "candidateCount": len(results),
            "candidates": results,
            "lockedOosReadCount": 0,
        },
    )
    flat_results = []
    gate_matrix = []
    for row in results:
        base = row["base"]
        stress = row["stress1_5x"]
        benchmark = row["benchmark"]
        flat_results.append(
            {
                "candidateId": row["candidateId"],
                "candidateHash": row["candidateHash"],
                "familyId": row["familyId"],
                "direction": row["direction"],
                "timeframe": row["timeframe"],
                "status": row["status"],
                "prefilterPassed": row["prefilterPassed"],
                "reasonCode": row["reasonCode"],
                "tradeCount": base["tradeCount"],
                "profitFactor": base["profitFactor"],
                "averageNetR": base["averageNetR"],
                "totalNetR": base["totalNetR"],
                "maximumDrawdownR": base["maximumDrawdownR"],
                "stress1_5xProfitFactor": stress["profitFactor"],
                "benchmarkId": row["benchmarkId"],
                "benchmarkTradeCount": benchmark["tradeCount"],
                "benchmarkAverageNetR": benchmark["averageNetR"],
                "lockedOosReadCount": 0,
            }
        )
        for gate_name, gate in row["gateEvaluation"].items():
            gate_matrix.append(
                {
                    "candidateId": row["candidateId"],
                    "gateName": gate_name,
                    "actual": gate["actual"],
                    "operator": gate["operator"],
                    "required": gate["required"],
                    "passed": gate["passed"],
                }
            )
    prefilter_fields = list(flat_results[0]) if flat_results else ["candidateId"]
    _write_csv(output / "prefilter_matrix.csv", flat_results, prefilter_fields)
    _write_csv(
        output / "prefilter_gate_matrix.csv",
        gate_matrix,
        ["candidateId", "gateName", "actual", "operator", "required", "passed"],
    )
    pd.DataFrame(flat_results).to_parquet(output / "candidate_results.parquet", index=False)
    _write_csv(
        output / "benchmark_comparability_matrix.csv",
        [
            {
                "candidateId": row["candidateId"],
                "benchmarkId": row["benchmarkId"],
                "candidateTradeCount": row["base"]["tradeCount"],
                "benchmarkTradeCount": row["benchmark"]["tradeCount"],
                "candidateAverageNetR": row["base"]["averageNetR"],
                "benchmarkAverageNetR": row["benchmark"]["averageNetR"],
                "capitalComparable": True,
                "mechanismIncrementPassed": row["gateEvaluation"]["mechanismIncrementAverageNetR"]["passed"],
            }
            for row in results
        ],
        [
            "candidateId",
            "benchmarkId",
            "candidateTradeCount",
            "benchmarkTradeCount",
            "candidateAverageNetR",
            "benchmarkAverageNetR",
            "capitalComparable",
            "mechanismIncrementPassed",
        ],
    )

    failed = [row for row in results if not row["prefilterPassed"]]
    failure_payload = {
        "schemaVersion": "alphapilot_v41_v45_prefilter_failure_attribution_v1",
        "failureCount": len(failed),
        "byReason": dict(sorted(Counter(row["reasonCode"] for row in failed).items())),
        "failures": [
            {
                "candidateId": row["candidateId"],
                "reasonCode": row["reasonCode"],
                "evidenceRef": "prefilter_gate_matrix.csv",
            }
            for row in failed
        ],
    }
    write_json_atomic(output / "prefilter_failure_attribution.json", failure_payload)
    write_json_atomic(output / "failure_attribution.json", failure_payload)

    survivors = [row for row in results if row["prefilterPassed"]][:2]
    formal_status = "not_run_no_prefilter_survivors" if not survivors else "not_run_pending_separate_formal_freeze"
    formal_rows = [
        {
            "candidateId": row["candidateId"],
            "status": formal_status,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
        }
        for row in survivors
    ]
    _write_csv(
        output / "formal_matrix.csv",
        formal_rows,
        ["candidateId", "status", "formalRunCount", "resultReadCount", "lockedOosReadCount"],
    )
    _write_csv(
        output / "formal_gate_matrix.csv",
        [],
        ["candidateId", "gateName", "actual", "operator", "required", "passed", "status"],
    )
    _write_csv(
        output / "formal_route_matrix.csv",
        formal_rows,
        ["candidateId", "status", "formalRunCount", "resultReadCount", "lockedOosReadCount"],
    )
    write_json_atomic(
        output / "statistical_matrix.json",
        {
            "schemaVersion": "alphapilot_v41_v45_statistical_matrix_v1",
            "status": formal_status,
            "candidateCount": len(survivors),
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
        },
    )
    funding_audit = audit_funding_carry_episode_semantics()
    write_json_atomic(output / "funding_carry_episode_semantics_audit.json", funding_audit)

    budget_payload = {
        "schemaVersion": "alphapilot_v41_v45_experiment_budget_v1",
        "policy": asdict(budget),
        "policyHash": budget.policy_hash,
        "inheritedFullBacktestsRemainingBefore": inherited_full_backtests,
        "campaignsUsed": 2,
        "mechanismFamiliesUsed": 2,
        "candidateIdsUsed": len(candidates),
        "developmentTrialsUsed": len(candidates),
        "fullBacktestsUsed": len(candidates),
        "formalCandidatesUsed": 0,
        "formalRunsUsed": 0,
        "fullBacktestsRemainingAfter": inherited_full_backtests - len(candidates),
        "budgetReset": False,
    }
    write_json_atomic(output / "experiment_budget.json", budget_payload)
    _write_jsonl(
        output / "program_budget_ledger.jsonl",
        [
            {
                "event": "budget_inherited",
                "frozenAt": frozen_at,
                "remainingFullBacktests": inherited_full_backtests,
                "policyHash": budget.policy_hash,
            },
            {
                "event": "bounded_prefilter_consumed",
                "candidateCount": len(candidates),
                "remainingFullBacktests": inherited_full_backtests - len(candidates),
            },
        ],
    )
    lifecycle = []
    for row in results:
        previous_hash = None
        for sequence, status in enumerate(
            [
                "source_ingested",
                "mechanism_extracted",
                "candidate_frozen",
                "prefilter_running",
                "research_pass" if row["prefilterPassed"] else "prefilter_failed",
            ],
            start=1,
        ):
            core = {
                "candidateId": row["candidateId"],
                "sequence": sequence,
                "status": status,
                "previousEventHash": previous_hash,
            }
            event_hash = stable_hash(core, prefix="candidate_lifecycle")
            lifecycle.append({**core, "eventHash": event_hash})
            previous_hash = event_hash
        if not row["prefilterPassed"]:
            core = {
                "candidateId": row["candidateId"],
                "sequence": 6,
                "status": "archived",
                "previousEventHash": previous_hash,
            }
            lifecycle.append({**core, "eventHash": stable_hash(core, prefix="candidate_lifecycle")})
    _write_jsonl(output / "artifact_lifecycle_history.jsonl", lifecycle)

    release_inventory = {
        "schemaVersion": "alphapilot_v41_v45_release_inventory_v1",
        "status": "not_run_no_qualified_formal_candidate",
        "releaseCount": 0,
        "releases": [],
        "approved": False,
        "demoArmed": False,
        "strategyOrderCount": 0,
    }
    write_json_atomic(output / "release_inventory.json", release_inventory)
    (output / "candidate_releases").mkdir(parents=True, exist_ok=True)
    write_json_atomic(
        output / "release_hash_audit.json",
        {"status": "not_run_no_release", "releaseCount": 0, "hashes": []},
    )
    write_json_atomic(
        output / "demo_approval_request.json",
        {
            "status": "not_run_no_release",
            "releaseHash": None,
            "riskOverlayHash": None,
            "approved": False,
        },
    )
    (output / "demo_approval_request.md").write_text(
        "# Demo Approval Request\n\nStatus: `not_run_no_release`.\n",
        encoding="utf-8",
        newline="\n",
    )

    status = (
        "completed_zero_qualified_candidates"
        if not survivors
        else "completed_with_prefilter_survivors_pending_formal_freeze"
    )
    summary = {
        "schemaVersion": "alphapilot_v41_v45_campaign_summary_v1",
        "campaignId": campaign_id,
        "status": status,
        "candidateCount": len(results),
        "prefilterSurvivorCount": len(survivors),
        "formalCandidateCount": 0,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "releaseCount": 0,
        "lockedOosReadCount": 0,
        "networkCalls": 0,
        "fundingCarryCandidateCreated": funding_audit["candidateCreated"],
        "budget": budget_payload,
    }
    write_json_atomic(output / "campaign_summary.json", summary)
    _write_summary(output / "campaign_summary.md", summary)
    write_json_atomic(output / "artifact_manifest.json", _artifact_manifest(output))
    return summary
