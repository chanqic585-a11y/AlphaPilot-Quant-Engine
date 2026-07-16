"""Run the single bounded V13.27.1.16 implementation-correction prefilter."""

from __future__ import annotations

import argparse
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .benchmarks import build_benchmark_comparison, simple_benchmark_report
from .candidates import build_candidate_inventory
from .conformance import build_candidate_conformance
from .event_evidence import (
    build_event_evidence,
    event_schema_report,
    verify_event_parity,
)
from .novelty import build_novelty_audit
from .prefilter import (
    evaluate_candidate,
    evaluate_portfolio_candidate,
    route_prefilter_survivors,
)
from .reporting import (
    ROUND_TRIP_COST_RATE,
    _frames_for_timeframe,
    _read_json,
    _reference_map,
    _write_csv,
    _write_parquet,
)
from .signals import replay_candidate, weak_signal_components, weak_signal_correlation_audit


ORIGINAL_CAMPAIGN_ID = "advisory_r_v15_502e810045e366353db4dbcfa7d08fdf3"
REQUIRED_REPORT_NAMES = {
    "benchmark_comparison.json",
    "campaign_summary.json",
    "campaign_summary.md",
    "candidate_events.parquet",
    "conformance_matrix.csv",
    "conformance_matrix.json",
    "corrected_vs_v15_comparison.json",
    "correction_manifest.json",
    "event_schema.json",
    "exit_leg_parity.json",
    "exit_policy_attribution.json",
    "failure_attribution.json",
    "implementation_parity.json",
    "novelty_audit.json",
    "prefilter_gate_matrix.json",
    "prefilter_results.json",
    "route_decision.json",
    "simple_benchmarks.json",
    "strategy_inventory.json",
    "trial_ledger.csv",
    "trial_ledger.json",
}


def _relative_key(path: Path) -> str:
    return path.resolve().as_posix()


def verify_immutable_artifacts(
    paths: Sequence[Path],
    *,
    baseline: Mapping[str, str] | None = None,
) -> dict[str, str]:
    observed = {
        _relative_key(path): sha256_file(path)
        for path in sorted((Path(value) for value in paths), key=lambda value: value.as_posix())
    }
    if baseline is not None and observed != dict(baseline):
        changed = sorted(
            key
            for key in set(observed) | set(baseline)
            if observed.get(key) != baseline.get(key)
        )
        raise RuntimeError(
            "immutable V15 artifact hash mismatch: " + ", ".join(changed)
        )
    return observed


def build_correction_manifest(
    *,
    correction_campaign_id: str,
    original_campaign_id: str,
    original_preregistration_hash: str,
    original_artifact_hashes: Mapping[str, str],
    implementation_conformance_hash: str,
    code_commit: str,
) -> dict[str, Any]:
    return {
        "schemaVersion": "advisory_r_correction_manifest_v1",
        "correctionCampaignId": correction_campaign_id,
        "correctionOfCampaignId": original_campaign_id,
        "correctionReason": "implementation_nonconformance",
        "originalPreregistrationHash": original_preregistration_hash,
        "codeCommit": code_commit,
        "implementationConformanceHash": implementation_conformance_hash,
        "parameterChanges": 0,
        "candidateChanges": 0,
        "gateChanges": 0,
        "universeChanges": 0,
        "costChanges": 0,
        "correctedPrefilterRuns": 1,
        "originalArtifactHashes": dict(original_artifact_hashes),
        "originalArtifactHashMismatchCount": 0,
        "originalFilesModified": [],
        "safetyBoundary": {
            "lockedOosAccessCount": 0,
            "formalEvidenceCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    }


def build_corrected_trial_ledger(
    original: Mapping[str, Any],
    *,
    correction_campaign_id: str,
) -> dict[str, Any]:
    original_rows = [dict(row) for row in original.get("trials") or []]
    corrected_rows = []
    for row in original_rows:
        identity = {
            "parentTrialId": row["trialId"],
            "candidateId": row["candidateId"],
            "correctionCampaignId": correction_campaign_id,
        }
        corrected_rows.append(
            {
                **row,
                "trialId": stable_hash(identity, prefix="advisory_r_correction_trial"),
                "parentTrialId": row["trialId"],
                "attemptType": "implementation_correction",
                "correctionCampaignId": correction_campaign_id,
                "resultsRead": True,
            }
        )
    core = {
        "schemaVersion": "advisory_r_trial_ledger_v2",
        "originalTrialLedgerHash": original.get("trialLedgerHash"),
        "originalAttemptCount": len(original_rows),
        "implementationCorrectionAttemptCount": len(corrected_rows),
        "actualReadResultTrialCount": len(original_rows) + len(corrected_rows),
        "trialCount": len(original_rows) + len(corrected_rows),
        "trials": original_rows + corrected_rows,
    }
    return {
        **core,
        "trialLedgerHash": stable_hash(core, prefix="advisory_r_trial_ledger"),
    }


def _hash_paths(paths: Sequence[Path], *, prefix: str) -> str:
    values = {
        path.as_posix(): sha256_file(path)
        for path in sorted(paths, key=lambda value: value.as_posix())
    }
    return stable_hash(values, prefix=prefix)


def implementation_hash_bundle(
    repo_root: Path,
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    conformance = [build_candidate_conformance(row) for row in candidates]
    exit_paths = [
        repo_root / "alphapilot" / "exit_policy" / name
        for name in ("engine.py", "exit_legs.py", "reporting.py", "validation.py")
    ]
    implementation_paths = [
        repo_root / "alphapilot" / "advisory_r_campaign" / name
        for name in (
            "benchmarks.py",
            "conformance.py",
            "corrected_reporting.py",
            "event_evidence.py",
            "pair_replay.py",
            "portfolio_replay.py",
            "signals.py",
            "structure_rules.py",
        )
    ]
    code_hashes = {
        path.relative_to(repo_root).as_posix(): sha256_file(path)
        for path in implementation_paths
    }
    implementation_hash = stable_hash(
        {"conformance": conformance, "codeHashes": code_hashes},
        prefix="advisory_r_implementation_conformance_bundle",
    )
    return {
        "implementationConformanceHash": implementation_hash,
        "exitPolicyEngineHash": _hash_paths(
            exit_paths, prefix="advisory_r_formal_exit_policy_engine"
        ),
        "structureRuleCompilerHash": sha256_file(
            repo_root / "alphapilot" / "advisory_r_campaign" / "structure_rules.py"
        ),
        "benchmarkCompilerHash": sha256_file(
            repo_root / "alphapilot" / "advisory_r_campaign" / "benchmarks.py"
        ),
        "conformanceRecords": conformance,
        "codeHashes": code_hashes,
    }


def _v15_paths(
    repo_root: Path,
    original_preregistration_path: Path,
    original: Mapping[str, Any],
) -> list[Path]:
    campaign_root = repo_root / "reports" / "advisory_r_campaign" / str(
        original["campaignId"]
    )
    snapshot_path = (
        repo_root
        / "research"
        / "data_snapshots"
        / f"{original['snapshotId']}.json"
    )
    paths = [original_preregistration_path, snapshot_path]
    paths.extend(path for path in campaign_root.rglob("*") if path.is_file())
    if not all(path.is_file() for path in paths):
        missing = [str(path) for path in paths if not path.is_file()]
        raise FileNotFoundError("missing immutable V15 artifact: " + ", ".join(missing))
    return paths


def _candidate_contract(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        key: row[key]
        for key in (
            "candidateId",
            "familyId",
            "variantId",
            "timeframe",
            "strategyType",
            "diagnosticOnly",
            "semanticFingerprint",
            "strategyDefinitionHash",
            "exitPolicy",
            "exitPolicyHash",
        )
    }


def _validate_frozen_identity(
    preregistration: Mapping[str, Any],
    original: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    hashes: Mapping[str, Any],
) -> None:
    if str(preregistration["correctionOfCampaignId"]) != ORIGINAL_CAMPAIGN_ID:
        raise RuntimeError("correction preregistration points at the wrong campaign")
    if str(original["campaignId"]) != ORIGINAL_CAMPAIGN_ID:
        raise RuntimeError("unexpected immutable V15 campaign")
    expected_contracts = [_candidate_contract(row) for row in candidates]
    if expected_contracts != [dict(row) for row in original["candidates"]]:
        raise RuntimeError("current candidate inventory differs from V15")
    if expected_contracts != [dict(row) for row in preregistration["candidates"]]:
        raise RuntimeError("correction candidate inventory differs from V15")
    unchanged = (
        "representativeUniverse",
        "prefilterGates",
        "portfolioPrefilterGates",
        "routing",
        "snapshotId",
        "snapshotHash",
        "exitPolicyBoundsHash",
    )
    for key in unchanged:
        if preregistration[key] != original[key]:
            raise RuntimeError(f"frozen campaign field changed: {key}")
    for key in (
        "parameterChanges",
        "candidateChanges",
        "gateChanges",
        "universeChanges",
        "costChanges",
    ):
        if int(preregistration[key]) != 0:
            raise RuntimeError(f"correction preregistration has non-zero {key}")
    expected_hashes = {
        "implementationConformanceHash": hashes["implementationConformanceHash"],
        "exitPolicyEngineHash": hashes["exitPolicyEngineHash"],
        "structureRuleCompilerHash": hashes["structureRuleCompilerHash"],
        "benchmarkCompilerHash": hashes["benchmarkCompilerHash"],
    }
    for key, value in expected_hashes.items():
        if str(preregistration[key]) != str(value):
            raise RuntimeError(f"frozen code hash mismatch: {key}")


def _regime_maps(
    frames: Mapping[str, Mapping[str, pd.DataFrame]],
) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for timeframe, timeframe_frames in frames.items():
        btc = timeframe_frames["BTC-USDT-SWAP"].copy()
        ema = btc["close"].ewm(span=200, adjust=False, min_periods=200).mean()
        labels = pd.Series("insufficient_history", index=btc.index, dtype="object")
        labels.loc[ema.notna() & (btc["close"] >= ema)] = "btc_above_ema_200"
        labels.loc[ema.notna() & (btc["close"] < ema)] = "btc_below_ema_200"
        result[timeframe] = {
            str(timestamp): str(label)
            for timestamp, label in zip(btc["date"], labels)
        }
    return result


def _event_regime(event: Mapping[str, Any], regime_map: Mapping[str, str]) -> str:
    timestamp = str(pd.Timestamp(str(event["entryTimestamp"])))
    return str(regime_map.get(timestamp) or "not_labeled_in_frozen_snapshot")


def _event_source_hash(
    event: Mapping[str, Any],
    *,
    timeframe: str,
    references: Mapping[tuple[str, str], Mapping[str, Any]],
    universe: Sequence[str],
) -> str:
    if str(event["symbol"]) == "PORTFOLIO":
        symbols = list(universe)
    elif event.get("marketLegs"):
        symbols = [str(row["symbol"]) for row in event["marketLegs"]]
    else:
        symbols = [str(event["symbol"])]
    source_rows = []
    for symbol in sorted(set(symbols)):
        reference = references.get((symbol, timeframe))
        if reference is None:
            raise RuntimeError(f"event references unavailable source data: {symbol} {timeframe}")
        source_rows.append(
            {
                "instrumentId": symbol,
                "timeframe": timeframe,
                "sha256": reference["sha256"],
            }
        )
    return stable_hash(source_rows, prefix="advisory_r_event_source_data")


def _exit_leg_parity(events: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    failures = []
    for event in events:
        legs = list(event["exitLegs"])
        checks = {
            "fraction": (sum(float(row["fraction"]) for row in legs), 1.0),
            "grossR": (sum(float(row["grossR"]) for row in legs), float(event["grossR"])),
            "feesR": (sum(float(row["feesR"]) for row in legs), float(event["feesR"])),
            "slippageR": (
                sum(float(row["slippageR"]) for row in legs),
                float(event["slippageR"]),
            ),
            "spreadR": (
                sum(float(row["spreadR"]) for row in legs),
                float(event["spreadR"]),
            ),
            "netR": (sum(float(row["netR"]) for row in legs), float(event["netR"])),
        }
        failed = [
            name
            for name, (observed, expected) in checks.items()
            if not math.isclose(observed, expected, rel_tol=0.0, abs_tol=1e-9)
        ]
        if failed:
            failures.append({"signalId": event["signalId"], "failedFields": failed})
        if event["fundingR"] is not None or any(
            row["fundingR"] is not None for row in legs
        ):
            failures.append(
                {"signalId": event["signalId"], "failedFields": ["fundingR"]}
            )
    if failures:
        raise RuntimeError("exit-leg accounting parity failed")
    return {
        "schemaVersion": "advisory_r_exit_leg_parity_v1",
        "eventCount": len(events),
        "exitLegCount": sum(int(row["exitLegCount"]) for row in events),
        "fundingUnavailableCount": len(events),
        "failedEventCount": 0,
        "passed": True,
    }


def _s10_correlation_audit(
    candidates: Sequence[Mapping[str, Any]],
    frames: Mapping[str, Mapping[str, pd.DataFrame]],
) -> dict[str, Any]:
    candidate = next(row for row in candidates if str(row["variantId"]) == "S10")
    timeframe_frames = frames[str(candidate["timeframe"])]
    market_close = pd.concat(
        [frame.set_index("date")["close"].rename(symbol) for symbol, frame in timeframe_frames.items()],
        axis=1,
    ).mean(axis=1)
    audits = []
    for symbol, frame in sorted(timeframe_frames.items()):
        components = weak_signal_components(candidate, frame, market_close=market_close)
        audits.append({"instrumentId": symbol, **weak_signal_correlation_audit(components)})
    return {
        "candidateId": candidate["candidateId"],
        "orthogonalityClaimed": False,
        "instrumentAudits": audits,
    }


def _corrected_route(
    results: Sequence[Mapping[str, Any]],
    *,
    maximum_survivors: int,
) -> dict[str, Any]:
    base = route_prefilter_survivors(results, maximum_survivors=maximum_survivors)
    survivors = list(base["formalCandidateIds"])
    return {
        **base,
        "prefilterSurvivorIds": survivors,
        "formalCandidateIds": [],
        "nextVersionFormalCandidateIds": survivors,
        "formalStageAllowed": False,
        "formalStageDeferred": bool(survivors),
        "hardStopReason": (
            "formal_stage_deferred_to_future_version"
            if survivors
            else "corrected_prefilter_zero_survivors"
        ),
        "lockedOosAccessCount": 0,
        "formalEvidenceCount": 0,
        "demoReleaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def _failure_attribution(
    results: Sequence[Mapping[str, Any]],
    conformance_records: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    failed_gates = Counter(
        gate for result in results for gate in result.get("failedGates") or []
    )
    return {
        "schemaVersion": "advisory_r_failure_attribution_v1",
        "candidateCount": len(results),
        "implementationBlockedCount": sum(
            not bool(row["implementationConformancePassed"])
            for row in conformance_records
        ),
        "economicPrefilterFailureCount": sum(not bool(row["passed"]) for row in results),
        "failedGateCounts": dict(sorted(failed_gates.items())),
        "postResultParameterChanges": 0,
        "nextAction": "stop_frozen_campaign_if_zero_survivors",
    }


def _comparison(
    old_results: Sequence[Mapping[str, Any]],
    new_results: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    old_by_id = {str(row["candidateId"]): row for row in old_results}
    rows = []
    for result in new_results:
        old = old_by_id[str(result["candidateId"])]
        rows.append(
            {
                "candidateId": result["candidateId"],
                "v15EventCount": old["eventCount"],
                "correctedEventCount": result["eventCount"],
                "eventCountDelta": int(result["eventCount"]) - int(old["eventCount"]),
                "v15Passed": old["passed"],
                "correctedPassed": result["passed"],
                "v15FailedGates": old["failedGates"],
                "correctedFailedGates": result["failedGates"],
                "v15TotalNetR": old["metrics"]["totalNetR"],
                "correctedTotalNetR": result["metrics"]["totalNetR"],
            }
        )
    return {
        "schemaVersion": "advisory_r_corrected_vs_v15_v1",
        "interpretation": "Implementation correction only; parameters and gates are unchanged.",
        "candidates": rows,
    }


def _summary_payload(
    preregistration: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    events: Sequence[Mapping[str, Any]],
    route: Mapping[str, Any],
    conformance: Mapping[str, Any],
) -> dict[str, Any]:
    archived = set(route["archivedCandidateIds"])
    diagnostics = set(route["diagnosticCandidateIds"])
    return {
        "schemaVersion": "advisory_r_corrected_campaign_summary_v1",
        "correctionCampaignId": preregistration["campaignId"],
        "correctionOfCampaignId": preregistration["correctionOfCampaignId"],
        "candidateCount": len(candidates),
        "familyCount": len({str(row["familyId"]) for row in candidates}),
        "parameterChangeCount": 0,
        "gateChangeCount": 0,
        "universeChangeCount": 0,
        "costChangeCount": 0,
        "eventCount": len(events),
        "prefilterSurvivorCount": len(route["prefilterSurvivorIds"]),
        "archivedCount": len(archived),
        "diagnosticCount": len(diagnostics),
        "implementationBlockedCount": int(conformance["implementationBlockedCount"]),
        "targetRGateMode": "advisory",
        "minimumTargetR": None,
        "route": route["hardStopReason"],
        "lockedOosAccessCount": 0,
        "formalEvidenceCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    return "\n".join(
        [
            f"# Advisory-R corrected prefilter {summary['correctionCampaignId']}",
            "",
            "## Scope",
            "",
            f"- Correction of: `{summary['correctionOfCampaignId']}`",
            f"- Candidates / families: `{summary['candidateCount']}` / `{summary['familyCount']}`",
            "- Parameter / gate / universe / cost changes: `0 / 0 / 0 / 0`",
            "- Target R: advisory only; no hard 2R gate was added.",
            "",
            "## Result",
            "",
            f"- Events: `{summary['eventCount']}`",
            f"- Prefilter survivors: `{summary['prefilterSurvivorCount']}`",
            f"- Archived: `{summary['archivedCount']}`",
            f"- Diagnostic-only: `{summary['diagnosticCount']}`",
            f"- Implementation blockers: `{summary['implementationBlockedCount']}`",
            f"- Route: `{summary['route']}`",
            "",
            "## Safety",
            "",
            "- Locked OOS reads: `0`",
            "- Formal evidence: `0`",
            "- Releases: `0`",
            "- Demo ARM: `false`",
            "- Orders: `0`",
            "",
            "This run corrects implementation conformance only. It does not search for better parameters.",
            "",
        ]
    )


def _conformance_report(hashes: Mapping[str, Any]) -> dict[str, Any]:
    records = [dict(row) for row in hashes["conformanceRecords"]]
    return {
        "schemaVersion": "advisory_r_conformance_matrix_v1",
        "implementationConformanceHash": hashes["implementationConformanceHash"],
        "exitPolicyEngineHash": hashes["exitPolicyEngineHash"],
        "structureRuleCompilerHash": hashes["structureRuleCompilerHash"],
        "benchmarkCompilerHash": hashes["benchmarkCompilerHash"],
        "candidateCount": len(records),
        "implementationConformancePassCount": sum(
            bool(row["implementationConformancePassed"]) for row in records
        ),
        "implementationBlockedCount": sum(
            not bool(row["implementationConformancePassed"]) for row in records
        ),
        "unusedFrozenFieldCount": sum(len(row["unusedFrozenKeys"]) for row in records),
        "unsupportedFallbackCount": sum(
            len(row["unsupportedFrozenKeys"]) for row in records
        ),
        "records": records,
    }


def _conformance_csv_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "candidateId": row["candidateId"],
            "strategyDefinitionHash": row["strategyDefinitionHash"],
            "implementationConformanceHash": row["implementationConformanceHash"],
            "implementationConformancePassed": row["implementationConformancePassed"],
            "implementedFeatureKeys": "|".join(row["implementedFeatureKeys"]),
            "implementedEntryKeys": "|".join(row["implementedEntryKeys"]),
            "implementedStopKeys": "|".join(row["implementedStopKeys"]),
            "implementedExitRuleKeys": "|".join(row["implementedExitRuleKeys"]),
            "unusedFrozenKeys": "|".join(row["unusedFrozenKeys"]),
            "unsupportedFrozenKeys": "|".join(row["unsupportedFrozenKeys"]),
        }
        for row in records
    ]


def run_corrected_prefilter_campaign(
    *,
    repo_root: Path,
    data_root: Path,
    preregistration_path: Path,
) -> Path:
    preregistration = _read_json(preregistration_path)
    original_path = next(
        iter(
            sorted(
                (repo_root / "research" / "preregistrations").glob(
                    "advisory_r_v15_*_prefilter_v2.json"
                )
            )
        ),
        None,
    )
    if original_path is None:
        raise FileNotFoundError("immutable V15 preregistration not found")
    original = _read_json(original_path)
    candidates = build_candidate_inventory()
    hashes = implementation_hash_bundle(repo_root, candidates)
    _validate_frozen_identity(preregistration, original, candidates, hashes)

    final_root = (
        repo_root
        / "reports"
        / "advisory_r_campaign"
        / str(preregistration["campaignId"])
    )
    staging_root = final_root.with_name(f".{final_root.name}.running")
    if final_root.exists() or staging_root.exists():
        raise RuntimeError("corrected prefilter is single-run and already exists")
    staging_root.mkdir(parents=True, exist_ok=False)

    immutable_paths = _v15_paths(repo_root, original_path, original)
    original_hashes = verify_immutable_artifacts(immutable_paths)
    snapshot_path = (
        repo_root
        / "research"
        / "data_snapshots"
        / f"{preregistration['snapshotId']}.json"
    )
    snapshot = _read_json(snapshot_path)
    if str(snapshot["snapshotHash"]) != str(preregistration["snapshotHash"]):
        raise RuntimeError("frozen snapshot hash mismatch")
    universe = [
        str(value)
        for value in preregistration["representativeUniverse"]["instrumentIds"]
    ]
    frames: dict[str, dict[str, pd.DataFrame]] = {}
    availability = []
    for timeframe in ("1h", "4h"):
        frames[timeframe], rows = _frames_for_timeframe(
            data_root=data_root,
            snapshot=snapshot,
            universe=universe,
            timeframe=timeframe,
        )
        availability.extend(rows)
    if len(availability) != len(universe) * 2 or not all(
        bool(row["available"]) for row in availability
    ):
        raise RuntimeError("frozen representative data is incomplete")

    original_ledger_path = (
        repo_root
        / "reports"
        / "advisory_r_campaign"
        / ORIGINAL_CAMPAIGN_ID
        / "prefilter"
        / "trial_ledger.json"
    )
    corrected_ledger = build_corrected_trial_ledger(
        _read_json(original_ledger_path),
        correction_campaign_id=str(preregistration["campaignId"]),
    )
    correction_trials = {
        str(row["candidateId"]): str(row["trialId"])
        for row in corrected_ledger["trials"]
        if row.get("attemptType") == "implementation_correction"
    }
    references = _reference_map(snapshot)
    regimes = _regime_maps(frames)
    raw_events_by_candidate: dict[str, list[dict[str, Any]]] = {}
    evidence_events_by_candidate: dict[str, list[dict[str, Any]]] = {}
    results = []
    parity_rows = []
    all_evidence_events = []
    for candidate in candidates:
        candidate_id = str(candidate["candidateId"])
        timeframe = str(candidate["timeframe"])
        raw_events = replay_candidate(
            candidate,
            frames[timeframe],
            round_trip_cost_rate=ROUND_TRIP_COST_RATE,
        )
        evidence_events = [
            build_event_evidence(
                event,
                trial_id=correction_trials[candidate_id],
                correction_campaign_id=str(preregistration["campaignId"]),
                implementation_conformance_hash=str(
                    hashes["implementationConformanceHash"]
                ),
                source_data_hash=_event_source_hash(
                    event,
                    timeframe=timeframe,
                    references=references,
                    universe=universe,
                ),
                market_regime=_event_regime(event, regimes[timeframe]),
            )
            for event in raw_events
        ]
        parity_rows.append(
            {"candidateId": candidate_id, **verify_event_parity(raw_events, evidence_events)}
        )
        raw_events_by_candidate[candidate_id] = raw_events
        evidence_events_by_candidate[candidate_id] = evidence_events
        all_evidence_events.extend(evidence_events)
        if str(candidate["strategyType"]) == "portfolio":
            result = evaluate_portfolio_candidate(
                candidate,
                evidence_events,
                gates=preregistration["portfolioPrefilterGates"],
            )
        else:
            result = evaluate_candidate(
                candidate,
                evidence_events,
                gates=preregistration["prefilterGates"],
            )
        results.append(result)

    implementation_parity = {
        "schemaVersion": "advisory_r_implementation_parity_v1",
        "candidateCount": len(parity_rows),
        "rawEventCount": sum(row["rawEventCount"] for row in parity_rows),
        "evidenceEventCount": sum(row["evidenceEventCount"] for row in parity_rows),
        "missingEventCount": 0,
        "extraEventCount": 0,
        "changedEventCount": 0,
        "passed": all(bool(row["passed"]) for row in parity_rows),
        "candidates": parity_rows,
    }
    if not implementation_parity["passed"]:
        raise RuntimeError("campaign implementation parity failed")
    exit_leg_parity = _exit_leg_parity(all_evidence_events)
    benchmark_rows = build_benchmark_comparison(candidates, raw_events_by_candidate, frames)
    benchmark_report = simple_benchmark_report(benchmark_rows)
    benchmark_report["weakSignalCorrelationAudit"] = _s10_correlation_audit(
        candidates, frames
    )
    route = _corrected_route(
        results,
        maximum_survivors=int(preregistration["routing"]["maximumSurvivors"]),
    )
    conformance = _conformance_report(hashes)
    if conformance["implementationBlockedCount"]:
        raise RuntimeError("implementation conformance remains blocked")
    novelty = build_novelty_audit(
        candidates, repo_root / "reports" / "full_archived_strategy_inventory.json"
    )
    old_results_payload = _read_json(
        repo_root
        / "reports"
        / "advisory_r_campaign"
        / ORIGINAL_CAMPAIGN_ID
        / "prefilter"
        / "prefilter_results.json"
    )
    comparison = _comparison(old_results_payload["results"], results)
    summary = _summary_payload(
        preregistration, candidates, all_evidence_events, route, conformance
    )
    manifest = build_correction_manifest(
        correction_campaign_id=str(preregistration["campaignId"]),
        original_campaign_id=ORIGINAL_CAMPAIGN_ID,
        original_preregistration_hash=str(original["preregistrationHash"]),
        original_artifact_hashes=original_hashes,
        implementation_conformance_hash=str(hashes["implementationConformanceHash"]),
        code_commit=str(preregistration["codeCommit"]),
    )

    write_json_atomic(staging_root / "correction_manifest.json", manifest)
    write_json_atomic(staging_root / "conformance_matrix.json", conformance)
    _write_csv(
        staging_root / "conformance_matrix.csv",
        _conformance_csv_rows(conformance["records"]),
    )
    write_json_atomic(staging_root / "strategy_inventory.json", candidates)
    write_json_atomic(staging_root / "novelty_audit.json", novelty)
    write_json_atomic(staging_root / "trial_ledger.json", corrected_ledger)
    _write_csv(staging_root / "trial_ledger.csv", corrected_ledger["trials"])
    _write_parquet(staging_root / "candidate_events.parquet", all_evidence_events)
    write_json_atomic(staging_root / "event_schema.json", event_schema_report())
    write_json_atomic(staging_root / "exit_leg_parity.json", exit_leg_parity)
    write_json_atomic(staging_root / "implementation_parity.json", implementation_parity)
    write_json_atomic(staging_root / "simple_benchmarks.json", benchmark_report)
    write_json_atomic(
        staging_root / "benchmark_comparison.json",
        {"comparisons": benchmark_rows, "hardGateChanges": 0},
    )
    write_json_atomic(
        staging_root / "prefilter_results.json",
        {"results": results, "route": route},
    )
    write_json_atomic(
        staging_root / "exit_policy_attribution.json",
        {
            "postResultPolicyChanges": 0,
            "fundingSemantics": "null_when_source_series_unavailable",
            "candidates": [
                {
                    "candidateId": row["candidateId"],
                    "exitPolicyMode": row["exitPolicyMode"],
                    "exitPolicyHash": row["exitPolicyHash"],
                    "diagnostics": row["exitDiagnostics"],
                }
                for row in results
            ],
        },
    )
    write_json_atomic(
        staging_root / "prefilter_gate_matrix.json",
        {
            "targetRGateMode": "advisory",
            "minimumTargetR": None,
            "gateChanges": 0,
            "candidates": [
                {
                    "candidateId": row["candidateId"],
                    "passed": row["passed"],
                    "gates": row["gates"],
                }
                for row in results
            ],
        },
    )
    write_json_atomic(staging_root / "route_decision.json", route)
    write_json_atomic(
        staging_root / "failure_attribution.json",
        _failure_attribution(results, conformance["records"]),
    )
    write_json_atomic(staging_root / "corrected_vs_v15_comparison.json", comparison)
    write_json_atomic(staging_root / "campaign_summary.json", summary)
    (staging_root / "campaign_summary.md").write_text(
        _summary_markdown(summary), encoding="utf-8"
    )

    observed_names = {path.name for path in staging_root.iterdir() if path.is_file()}
    missing_reports = sorted(REQUIRED_REPORT_NAMES - observed_names)
    if missing_reports:
        raise RuntimeError("corrected campaign report contract incomplete: " + ", ".join(missing_reports))
    verify_immutable_artifacts(immutable_paths, baseline=original_hashes)
    staging_root.replace(final_root)
    return final_root


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    args = parser.parse_args()
    root = run_corrected_prefilter_campaign(
        repo_root=args.repo_root.resolve(),
        data_root=args.data_root.resolve(),
        preregistration_path=args.preregistration.resolve(),
    )
    print(root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
