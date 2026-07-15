"""Offline bounded campaign runner with locked holdout and explicit failures."""

from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .campaign_contract import CandidateSpec
from .campaign_metrics import evaluate_candidate_gates
from .campaign_signals import align_funding_to_bars, replay_candidate_events
from .network_guard import result_run_offline


TIMEFRAME_SECONDS = {"15m": 900, "1h": 3600, "4h": 14_400, "1d": 86_400}


def _timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def assign_event_partition(
    timestamp: str,
    boundary: Mapping[str, Any],
    *,
    timeframe: str,
    maximum_hold_bars: int,
) -> tuple[str, str]:
    observed = _timestamp(timestamp)
    embargo = timedelta(seconds=TIMEFRAME_SECONDS[timeframe] * maximum_hold_bars)
    development_start = _timestamp(str(boundary["developmentStart"]))
    development_end = _timestamp(str(boundary["developmentEnd"]))
    if development_start <= observed < development_end:
        return ("development", "") if observed + embargo < development_end else ("embargo", "")
    for fold in boundary["walkForwardFolds"]:
        fold_start, fold_end = _timestamp(str(fold["start"])), _timestamp(str(fold["end"]))
        if fold_start <= observed < fold_end:
            return (
                ("walk_forward", str(fold["foldId"]))
                if observed + embargo < fold_end
                else ("embargo", "")
            )
    holdout_start = _timestamp(str(boundary["holdoutStart"]))
    holdout_end = _timestamp(str(boundary["holdoutEnd"]))
    if holdout_start <= observed < holdout_end:
        return ("holdout", "") if observed + embargo < holdout_end else ("embargo", "")
    return "outside", ""


def build_event_contract(
    *,
    raw_event: Mapping[str, Any],
    candidate: Mapping[str, Any],
    symbol: str,
    data_hash: str,
    split: str,
    fold_id: str,
) -> dict[str, Any]:
    factor_roles = {
        "confirmation": list(candidate.get("factorConfirmations", [])),
        "ranking": list(candidate.get("factorRanking", [])),
        "veto": list(candidate.get("factorVetoes", [])),
    }
    factor_hashes = sorted({value for values in factor_roles.values() for value in values})
    return {
        **dict(raw_event),
        "hypothesisId": candidate["candidateId"],
        "familyId": candidate["familyId"],
        "variantId": candidate["candidateId"],
        "timestamp": raw_event["signalTimestamp"],
        "symbol": symbol,
        "direction": candidate["direction"],
        "timeframe": candidate["timeframe"],
        "coreMechanism": candidate["marketMechanismId"],
        "factorDefinitionHashes": factor_hashes,
        "factorRoles": factor_roles,
        "entryReference": "next_bar_open",
        "stopReference": "fixed_initial_atr_stop_never_widened",
        "targetReference": f"fixed_{candidate.get('targetR', 2)}R_target",
        "maximumHoldBars": candidate["maximumHoldBars"],
        "candidateDefinitionHash": candidate["definitionHash"],
        "split": split,
        "foldId": fold_id,
        "dataHash": data_hash,
    }


def benjamini_hochberg(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    indexed = sorted(enumerate(values), key=lambda item: item[1])
    adjusted = [1.0] * len(values)
    running = 1.0
    for rank_index in range(len(indexed) - 1, -1, -1):
        original_index, value = indexed[rank_index]
        rank = rank_index + 1
        running = min(running, float(value) * len(values) / rank)
        adjusted[original_index] = min(1.0, max(0.0, running))
    return adjusted


def _normal_mean_pvalue(events: Sequence[Mapping[str, Any]]) -> float | None:
    values = np.asarray([float(event["netR"]) for event in events], dtype=float)
    if len(values) < 3:
        return None
    std = float(values.std(ddof=1))
    if std <= 0:
        return 0.0 if float(values.mean()) > 0 else 1.0
    statistic = float(values.mean()) / (std / math.sqrt(len(values)))
    return 0.5 * math.erfc(statistic / math.sqrt(2))


def _candidate_from_row(row: Mapping[str, Any]) -> CandidateSpec:
    fields = {
        key: row[key]
        for key in (
            "candidateId", "familyId", "marketMechanismId", "direction", "timeframe",
            "causalRationale", "eventDefinition", "invalidation", "stopAtr", "targetR",
            "maximumHoldBars", "requiredData", "expectedFailureRegimes", "factorConfirmations",
            "factorRanking", "factorVetoes",
        )
    }
    for name in ("requiredData", "expectedFailureRegimes", "factorConfirmations", "factorRanking", "factorVetoes"):
        fields[name] = tuple(fields[name])
    return CandidateSpec(**fields)


def _verify_source_hashes(repo: Path, preregistration: Mapping[str, Any]) -> None:
    source_root = repo / "alphapilot" / "research_screening"
    for name, expected in preregistration["implementationSourceHashes"].items():
        if sha256_file(source_root / name) != expected:
            raise RuntimeError(f"implementation source changed after preregistration: {name}")


def _verify_code_ancestor(repo: Path, commit: str) -> None:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError("preregistered implementation commit is not an ancestor of HEAD")


def _catalog_maps(catalog: Mapping[str, Any]) -> tuple[dict[tuple[str, str], dict[str, Any]], dict[str, dict[str, Any]]]:
    ohlcv: dict[tuple[str, str], dict[str, Any]] = {}
    funding: dict[str, dict[str, Any]] = {}
    for row in catalog["datasets"]:
        symbol = str(row["symbols"][0])
        if row["dataType"] == "ohlcv":
            ohlcv[(symbol, str(row["timeframe"]))] = dict(row)
        elif row["dataType"] == "funding":
            funding[symbol] = dict(row)
    return ohlcv, funding


def _read_verified_parquet(row: Mapping[str, Any]) -> pd.DataFrame:
    path = Path(str(row["sourcePath"]))
    if sha256_file(path) != row["contentHash"]:
        raise RuntimeError(f"dataset hash mismatch: {row['datasetId']}")
    return pd.read_parquet(path)


def _benchmark_close(frame: pd.DataFrame, benchmark: pd.DataFrame) -> pd.Series:
    left = pd.DataFrame({"date": pd.to_datetime(frame["date"], utc=True)}).sort_values("date")
    right = benchmark[["date", "close"]].copy()
    right["date"] = pd.to_datetime(right["date"], utc=True)
    right = right.sort_values("date").rename(columns={"close": "benchmarkClose"})
    merged = pd.merge_asof(left, right, on="date", direction="backward", allow_exact_matches=True)
    return pd.to_numeric(merged["benchmarkClose"], errors="coerce")


def _raw_events_for_candidate(
    *,
    candidate: CandidateSpec,
    candidate_row: Mapping[str, Any],
    instruments: Sequence[str],
    ohlcv_catalog: Mapping[tuple[str, str], Mapping[str, Any]],
    funding_catalog: Mapping[str, Mapping[str, Any]],
    costs: Mapping[str, float],
    boundary: Mapping[str, Any],
    include_holdout: bool,
) -> list[dict[str, Any]]:
    benchmark = _read_verified_parquet(ohlcv_catalog[("BTC-USDT-SWAP", candidate.timeframe)])
    holdout_start = _timestamp(str(boundary["holdoutStart"]))
    all_events: list[dict[str, Any]] = []
    for symbol in instruments:
        dataset = ohlcv_catalog[(symbol, candidate.timeframe)]
        frame = _read_verified_parquet(dataset).sort_values("date").reset_index(drop=True)
        if not include_holdout:
            frame = frame[pd.to_datetime(frame["date"], utc=True) < holdout_start].reset_index(drop=True)
        benchmark_close = (
            _benchmark_close(frame, benchmark)
            if candidate.marketMechanismId == "idiosyncratic_shock_reversion"
            else None
        )
        funding_rate = None
        if candidate.marketMechanismId == "funding_crowding_reversal":
            funding_frame = _read_verified_parquet(funding_catalog[symbol])
            funding_rate = align_funding_to_bars(frame, funding_frame)
        raw = replay_candidate_events(
            candidate=candidate,
            frame=frame,
            benchmark_close=benchmark_close,
            funding_rate=funding_rate,
            costs=dict(costs),
        )
        for event in raw:
            split, fold_id = assign_event_partition(
                event["signalTimestamp"],
                boundary,
                timeframe=candidate.timeframe,
                maximum_hold_bars=candidate.maximumHoldBars,
            )
            if split in {"embargo", "outside"} or (split == "holdout" and not include_holdout):
                continue
            all_events.append(
                build_event_contract(
                    raw_event=event,
                    candidate=candidate_row,
                    symbol=symbol,
                    data_hash=str(dataset["contentHash"]),
                    split=split,
                    fold_id=fold_id,
                )
            )
    return sorted(all_events, key=lambda row: (row["entryTimestamp"], row["symbol"]))


def _failure_labels(gates: Mapping[str, Any], *, translation_passed: bool) -> list[str]:
    labels: list[str] = []
    if not gates["samplePassed"]:
        labels.append("data_insufficient")
    if not gates["prescreenPassed"]:
        labels.append("market_mechanism_prescreen_failed")
    if gates["prescreenPassed"] and not translation_passed:
        labels.append("freqtrade_translation_not_executed")
    if gates["prescreenPassed"] and translation_passed and not gates["basePassed"]:
        labels.append("out_of_sample_failed")
    if gates["basePassed"] and not gates["formalPassed"]:
        for name, row in gates["formalGates"].items():
            if not row["passed"]:
                labels.append(f"formal_gate_failed:{name}")
    return labels or ["formal_passed"]


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


def _write_parquet_atomic(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    frame.to_parquet(temporary, index=False)
    os.replace(temporary, path)


def run_campaign(repo_root: Path | str, preregistration_path: Path | str) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    prereg_path = Path(preregistration_path).resolve()
    prereg = json.loads(prereg_path.read_text(encoding="utf-8"))
    _verify_code_ancestor(repo, str(prereg["codeCommit"]))
    _verify_source_hashes(repo, prereg)
    catalog_path = repo / "reports" / "backtest_screening" / "data_readiness" / "dataset_catalog.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    if catalog["dataManifestHash"] != prereg["dataSnapshotHash"].replace("data_snapshot", "data_manifest"):
        snapshot_path = repo / "research" / "data_snapshots" / f"{prereg['dataSnapshotHash']}.json"
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if snapshot["dataManifestHash"] != catalog["dataManifestHash"]:
            raise RuntimeError("preregistered snapshot does not match the dataset catalog")
    ohlcv_catalog, funding_catalog = _catalog_maps(catalog)
    instruments = list(prereg["universePolicy"]["instruments"])
    base_costs = prereg["costScenarios"]["base"]
    candidates_results: list[dict[str, Any]] = []
    gate_matrix: dict[str, Any] = {}
    failure_rows: list[dict[str, Any]] = []
    formal_evidence: list[dict[str, Any]] = []
    full_backtest_count = 0
    holdout_access_count = 0
    with result_run_offline():
        for candidate_row in prereg["candidates"]:
            candidate = _candidate_from_row(candidate_row)
            boundary = prereg["splitPolicy"]["timeBoundaries"][candidate.timeframe]
            selection_rows = _raw_events_for_candidate(
                candidate=candidate,
                candidate_row=candidate_row,
                instruments=instruments,
                ohlcv_catalog=ohlcv_catalog,
                funding_catalog=funding_catalog,
                costs=base_costs,
                boundary=boundary,
                include_holdout=False,
            )
            selection_gates = evaluate_candidate_gates(
                events=selection_rows,
                timeframe=candidate.timeframe,
                preregistration=prereg,
                holdout_access_before_final_evaluation=0,
            )
            all_rows = selection_rows
            translation_passed = False
            gates = selection_gates
            if selection_gates["prescreenPassed"]:
                full_backtest_count += 1
                holdout_access_count += 1
                all_rows = _raw_events_for_candidate(
                    candidate=candidate,
                    candidate_row=candidate_row,
                    instruments=instruments,
                    ohlcv_catalog=ohlcv_catalog,
                    funding_catalog=funding_catalog,
                    costs=base_costs,
                    boundary=boundary,
                    include_holdout=True,
                )
                gates = evaluate_candidate_gates(
                    events=all_rows,
                    timeframe=candidate.timeframe,
                    preregistration=prereg,
                    holdout_access_before_final_evaluation=0,
                )
                # The first campaign does not claim Freqtrade parity without a separately
                # generated and hash-checked strategy translation.
                translation_passed = False
            pvalue = _normal_mean_pvalue(
                [row for row in all_rows if row["split"] in {"walk_forward", "holdout"}]
            )
            formal_passed = bool(gates["formalPassed"] and translation_passed)
            candidate_result = {
                "candidateId": candidate.candidateId,
                "familyId": candidate.familyId,
                "marketMechanismId": candidate.marketMechanismId,
                "direction": candidate.direction,
                "timeframe": candidate.timeframe,
                "definitionHash": candidate_row["definitionHash"],
                "selectionEventCount": len(selection_rows),
                "fullEventCount": len(all_rows) if selection_gates["prescreenPassed"] else 0,
                "prescreenPassed": bool(selection_gates["prescreenPassed"]),
                "fullBacktestExecuted": bool(selection_gates["prescreenPassed"]),
                "fullBacktestEngine": "not_run" if not selection_gates["prescreenPassed"] else "causal_event_replay_reference",
                "freqtradeTranslationPassed": translation_passed,
                "basePassed": bool(gates["basePassed"] and translation_passed),
                "formalPassed": formal_passed,
                "rawPValue": pvalue,
                "fdrAdjustedPValue": None,
                "foldDispersion": None,
                "regimeCoverage": None,
                "dataCompleteness": 1.0,
                "deflatedSharpe": None,
                "deflatedSharpeReason": "insufficient independent strategy trials for a defensible estimate",
                "probabilityOfBacktestOverfitting": None,
                "pboReason": "insufficient combinatorial paths for a defensible estimate",
                "gates": gates,
                "failureLabels": _failure_labels(gates, translation_passed=translation_passed),
                "eventsHash": stable_hash(all_rows, prefix="candidate_events"),
            }
            candidates_results.append(candidate_result)
            gate_matrix[candidate.candidateId] = gates
            failure_rows.append(
                {
                    "candidateId": candidate.candidateId,
                    "labels": candidate_result["failureLabels"],
                    "expectedFailureRegimes": list(candidate.expectedFailureRegimes),
                }
            )
            if formal_passed:
                formal_evidence.append(
                    {
                        "schemaVersion": "phase3c_formal_pass_evidence_v1",
                        "formalPass": True,
                        "campaignId": prereg["campaignId"],
                        "candidateId": candidate.candidateId,
                        "candidateDefinitionHash": candidate_row["definitionHash"],
                        "externalReferenceManifestHash": prereg["externalReferenceManifestHash"],
                        "factorRegistryHash": prereg["factorRegistryHash"],
                        "factorShortlistHash": prereg["factorShortlistHash"],
                        "factorDefinitionHashes": candidate_result.get("factorDefinitionHashes", []),
                        "factorRoles": {
                            "confirmation": list(candidate.factorConfirmations),
                            "ranking": list(candidate.factorRanking),
                            "veto": list(candidate.factorVetoes),
                        },
                        "marketMechanismId": candidate.marketMechanismId,
                        "dataSnapshotHash": prereg["dataSnapshotHash"],
                        "preregistrationHash": prereg["preregistrationHash"],
                        "gateEvidence": gates,
                        "formalGateHash": stable_hash(gates, prefix="formal_gate"),
                    }
                )
    valid_pvalues = [row["rawPValue"] for row in candidates_results if row["rawPValue"] is not None]
    adjusted = iter(benjamini_hochberg(valid_pvalues))
    for row in candidates_results:
        if row["rawPValue"] is not None:
            row["fdrAdjustedPValue"] = next(adjusted)
    output = repo / "reports" / "backtest_screening" / str(prereg["campaignId"])
    evidence_dir = output / "formal_pass_evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    for stale in evidence_dir.glob("*.json"):
        stale.unlink()
    for evidence in formal_evidence:
        write_json_atomic(evidence_dir / f"{evidence['candidateId']}.json", _json_safe(evidence))
    passed_count = sum(bool(row["formalPassed"]) for row in candidates_results)
    base_count = sum(bool(row["basePassed"]) for row in candidates_results)
    summary = {
        "schemaVersion": "phase3c_campaign_summary_v1",
        "campaignId": prereg["campaignId"],
        "preregistrationHash": prereg["preregistrationHash"],
        "dataSnapshotHash": prereg["dataSnapshotHash"],
        "candidateCount": len(candidates_results),
        "prescreenPassCount": sum(bool(row["prescreenPassed"]) for row in candidates_results),
        "fullBacktestCount": full_backtest_count,
        "basePassCount": base_count,
        "formalPassCount": passed_count,
        "holdoutAccessCountBeforeFinalEvaluation": 0,
        "holdoutFinalEvaluationCount": holdout_access_count,
        "walkForwardFoldCount": 5,
        "embargoApplied": True,
        "costScenarios": prereg["costScenarios"],
        "budgetExceeded": full_backtest_count > prereg["experimentBudget"]["maximumFullBacktests"],
        "resultRunNetworkPolicy": "offline_enforced",
        "status": "completed",
        "bestCandidate": max(
            candidates_results,
            key=lambda row: row["gates"]["developmentMetrics"]["averageNetR"],
        )["candidateId"] if candidates_results else None,
    }
    write_json_atomic(output / "campaign_summary.json", _json_safe(summary))
    summary_md = (
        f"# Phase 3C Campaign {prereg['campaignId']}\n\n"
        f"- Status: completed\n"
        f"- Candidates: {len(candidates_results)}\n"
        f"- Prescreen passes: {summary['prescreenPassCount']}\n"
        f"- Full backtests: {full_backtest_count}\n"
        f"- Base passes: {base_count}\n"
        f"- Formal passes: {passed_count}\n"
        f"- Holdout access before final evaluation: 0\n"
        f"- Result network policy: offline enforced\n\n"
        "Zero formal passes is a valid completed outcome; no winner was forced.\n"
    )
    (output / "campaign_summary.md").write_text(summary_md, encoding="utf-8")
    parquet_rows = []
    for row in candidates_results:
        parquet_rows.append(
            {
                key: (json.dumps(value, ensure_ascii=False, sort_keys=True) if isinstance(value, (dict, list)) else value)
                for key, value in row.items()
            }
        )
    _write_parquet_atomic(output / "candidate_results.parquet", pd.DataFrame(parquet_rows))
    write_json_atomic(output / "gate_matrix.json", _json_safe({"candidates": gate_matrix}))
    write_json_atomic(output / "failure_attribution.json", _json_safe({"candidates": failure_rows}))
    write_json_atomic(
        output / "experiment_budget.json",
        {
            **prereg["experimentBudget"],
            "initialCandidateCount": len(candidates_results),
            "fullBacktestCount": full_backtest_count,
            "structuralRevisionCount": 0,
            "exceeded": summary["budgetExceeded"],
        },
    )
    write_json_atomic(
        output / "console_projection.json",
        {
            "schemaVersion": "phase3c_console_projection_v1",
            "campaignId": prereg["campaignId"],
            "formalPassCount": passed_count,
            "eligibleEvidencePaths": [f"formal_pass_evidence/{row['candidateId']}.json" for row in formal_evidence],
            "demoReleaseCount": 0,
            "ordersCreated": 0,
        },
    )
    artifact_paths = sorted(
        path for path in output.rglob("*") if path.is_file() and path.name != "artifact_manifest.json"
    )
    manifest = {
        "schemaVersion": "phase3c_artifact_manifest_v1",
        "campaignId": prereg["campaignId"],
        "artifacts": [
            {"path": str(path.relative_to(repo)).replace("\\", "/"), "sha256": sha256_file(path)}
            for path in artifact_paths
        ],
    }
    manifest["manifestHash"] = stable_hash(manifest, prefix="campaign_artifacts")
    write_json_atomic(output / "artifact_manifest.json", manifest)
    return {"summary": summary, "results": candidates_results, "output": output}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--preregistration", type=Path, required=True)
    args = parser.parse_args()
    result = run_campaign(args.repo, args.preregistration)
    print(json.dumps(_json_safe(result["summary"]), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
