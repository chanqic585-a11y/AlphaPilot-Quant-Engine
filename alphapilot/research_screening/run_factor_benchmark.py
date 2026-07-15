"""Run the preregistered Phase 3B factor benchmark from an immutable offline snapshot."""

from __future__ import annotations

import argparse
import json
import math
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.evaluation.multiple_testing import benjamini_hochberg
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.factor_lab.expression_parser import parse_expression
from alphapilot.factor_lab.expression_runtime import evaluate_expression
from alphapilot.factor_lab.panel_builder import build_factor_panel

from .controls import run_evaluator_controls
from .data_readiness import evaluate_data_readiness
from .factor_clustering import cluster_factors
from .factor_evaluation import evaluate_factor_trial
from .network_guard import result_run_offline
from .prepare_data import DEFAULT_DATA_ROOT, RESEARCH_INSTRUMENTS, RESEARCH_TIMEFRAMES, select_canonical_ohlcv


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return _json_safe(value.item())
    return value


def _read_latest_snapshot(repo: Path) -> dict[str, Any]:
    candidates = sorted((repo / "research" / "data_snapshots").glob("data_snapshot_*.json"))
    if not candidates:
        raise FileNotFoundError("Phase 3B data snapshot is missing")
    return json.loads(candidates[-1].read_text(encoding="utf-8"))


def _external_reference_hash(repo: Path) -> str:
    files = sorted((repo / "reports" / "external_research").glob("*_reference_manifest.json"))
    if not files:
        raise FileNotFoundError("external reference manifests are missing")
    return stable_hash([{"path": path.name, "sha256": sha256_file(path)} for path in files], prefix="external_references")


def _git_commit(repo: Path) -> str:
    return subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()


def _pit_splits() -> dict[str, list[str]]:
    result = {"split_1": [], "split_2": [], "split_3": []}
    keys = tuple(result)
    for instrument in RESEARCH_INSTRUMENTS:
        bucket = int(stable_hash(instrument)[-8:], 16) % 3
        result[keys[bucket]].append(instrument)
    return result


def _cluster_lookup(clusters: dict[str, Any]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for cluster in clusters["clusters"]:
        for factor_id in cluster["factorIds"]:
            lookup[factor_id] = cluster["clusterId"]
    return lookup


def run_factor_benchmark(*, repo_root: Path | str, data_root: Path | str) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    data = Path(data_root).resolve()
    seed = json.loads((repo / "research" / "factor_preregistrations" / "alpha191_seed_v1.json").read_text(encoding="utf-8"))
    source_registry = repo / "reports" / "factor_lab" / "alpha191_registry.json"
    expected_registry = repo / "reports" / "factor_lab" / "alpha191_formula_registry.json"
    if not expected_registry.exists():
        shutil.copyfile(source_registry, expected_registry)
    snapshot = _read_latest_snapshot(repo)
    manifest = json.loads((data / "manifests" / "phase3b_dataset_catalog.json").read_text(encoding="utf-8"))
    if not manifest.get("verified"):
        raise RuntimeError("data manifest verification failed")
    if snapshot["dataManifestHash"] != manifest["dataManifestHash"]:
        raise RuntimeError("data snapshot and manifest hashes differ")

    paths = {
        instrument: select_canonical_ohlcv(data / "_alphapilot" / "canonical", instrument, "1d")
        for instrument in RESEARCH_INSTRUMENTS
    }
    with result_run_offline():
        panel = build_factor_panel(paths)
        context = {
            "open": panel.open,
            "high": panel.high,
            "low": panel.low,
            "close": panel.close,
            "volume": panel.volume,
            "amount": panel.amount,
            "vwap": panel.vwap,
            "returns": panel.returns,
        }
        factor_values: dict[str, pd.DataFrame] = {}
        trials: list[dict[str, Any]] = []
        for factor in seed["seedFactors"]:
            parsed = parse_expression(factor["canonicalFormula"])
            value = evaluate_expression(parsed, context)
            if not isinstance(value, pd.DataFrame):
                raise TypeError(f"factor {factor['factorId']} did not produce a panel")
            factor_values[factor["factorId"]] = value
            for horizon in (1, 5):
                forward = panel.close.shift(-horizon).div(panel.close).sub(1)
                for direction in (1, -1):
                    trial_id = f"{factor['factorId']}_1d_h{horizon}_{'original' if direction == 1 else 'inverse'}"
                    metrics = evaluate_factor_trial(
                        trial_id=trial_id,
                        factor=value,
                        forward_returns=forward,
                        direction=direction,
                        base_cost_bps=10.0,
                        folds=5,
                        embargo_rows=horizon,
                    )
                    trials.append(
                        {
                            "factorId": factor["factorId"],
                            "implementationHash": factor["implementationHash"],
                            "timeframe": "1d",
                            "forwardHorizon": horizon,
                            "direction": "original" if direction == 1 else "inverse",
                            **metrics,
                        }
                    )
        controls = run_evaluator_controls(seed=31)

    fdr = benjamini_hochberg({trial["trialId"]: float(trial["pValue"]) for trial in trials}, q=0.1)
    decisions = {item.itemId: item for item in fdr.decisions}
    clusters = cluster_factors(factor_values)
    cluster_lookup = _cluster_lookup(clusters)
    eligible_trials: list[dict[str, Any]] = []
    for trial in trials:
        decision = decisions[trial["trialId"]]
        trial["fdrAdjustedPValue"] = decision.adjustedPValue
        trial["fdrSignificant"] = decision.significant
        trial["clusterId"] = cluster_lookup[trial["factorId"]]
        gates = {
            "coverage": trial["coverage"] >= 0.7,
            "foldConsistency": trial["positiveFoldCount"] >= 3,
            "fdr": decision.significant,
            "baseCostPositive": trial["baseCostSpread"] > 0,
            "stress1_5xNonNegative": trial["stress1_5xSpread"] >= 0,
            "instrumentConcentration": trial["singleInstrumentPositiveContribution"] <= 0.35,
            "monthConcentration": trial["singleMonthPositiveContribution"] <= 0.35,
        }
        trial["qualificationGates"] = gates
        trial["eligibleResearchFeature"] = all(gates.values())
        if trial["eligibleResearchFeature"]:
            eligible_trials.append(trial)

    by_cluster: dict[str, list[dict[str, Any]]] = {}
    for trial in eligible_trials:
        by_cluster.setdefault(trial["clusterId"], []).append(trial)
    selected = [
        sorted(items, key=lambda item: (item["fdrAdjustedPValue"], -item["stress1_5xSpread"], item["trialId"]))[0]
        for items in by_cluster.values()
    ]
    selected.sort(key=lambda item: item["trialId"])
    rejected = sorted({trial["factorId"] for trial in trials if not trial["eligibleResearchFeature"]})

    factor_report_dir = repo / "reports" / "factor_lab"
    factor_report_dir.mkdir(parents=True, exist_ok=True)
    trial_ledger = {
        "schemaVersion": "factor_trial_ledger_v1",
        "preregistrationHash": seed["preregistrationHash"],
        "maximumFormalTrials": 192,
        "formalTrialCount": len(trials),
        "fdrQ": 0.1,
        "fdrCompleted": True,
        "trials": trials,
    }
    trial_ledger["factorTrialLedgerHash"] = stable_hash(_json_safe(trial_ledger), prefix="factor_trial_ledger")
    write_json_atomic(factor_report_dir / "factor_trial_ledger.json", _json_safe(trial_ledger))
    write_json_atomic(factor_report_dir / "factor_clusters.json", _json_safe(clusters))
    write_json_atomic(factor_report_dir / "factor_evaluator_controls.json", _json_safe(controls))

    shortlist_core = {
        "schemaVersion": "factor_shortlist_v1",
        "dataManifestHash": manifest["dataManifestHash"],
        "dataSnapshotHash": snapshot["snapshotId"],
        "externalReferenceManifestHash": _external_reference_hash(repo),
        "factorRegistryHash": sha256_file(expected_registry),
        "factorImplementationHashes": sorted(item["implementationHash"] for item in seed["seedFactors"]),
        "factorTrialLedgerHash": trial_ledger["factorTrialLedgerHash"],
        "factorClusterHash": stable_hash(_json_safe(clusters), prefix="factor_clusters"),
        "eligibleFactors": [item["trialId"] for item in selected],
        "rejectedFactors": rejected,
        "selectionUsedHoldout": False,
        "controlsExcluded": True,
        "gitCommit": _git_commit(repo),
    }
    shortlist_id = stable_hash(shortlist_core, prefix="factor_shortlist")
    shortlist = {**shortlist_core, "factorShortlistId": shortlist_id}
    write_json_atomic(factor_report_dir / "factor_shortlist.json", _json_safe(shortlist))
    frozen_shortlist = repo / "research" / "factor_shortlists" / f"{shortlist_id}.json"
    write_json_atomic(frozen_shortlist, _json_safe(shortlist))

    funding_datasets = [item for item in manifest["datasets"] if item["dataType"] == "funding"]
    ohlcv_datasets = [item for item in manifest["datasets"] if item["dataType"] == "ohlcv"]
    funding_years = min(
        (pd.Timestamp(item["endTime"]) - pd.Timestamp(item["startTime"])).days / 365.25
        for item in funding_datasets
    ) if funding_datasets else 0
    mechanisms = [
        {"mechanismId": "volatility_compression_breakout", "ready": len(ohlcv_datasets) == len(RESEARCH_INSTRUMENTS) * len(RESEARCH_TIMEFRAMES), "usesNonOhlcv": False, "formalUse": "time_series"},
        {"mechanismId": "idiosyncratic_shock_reversion", "ready": {"BTC-USDT-SWAP", "ETH-USDT-SWAP"}.issubset({item["symbols"][0] for item in ohlcv_datasets}), "usesNonOhlcv": False, "formalUse": "time_series"},
        {"mechanismId": "funding_crowding_reversal", "ready": len(funding_datasets) == len(RESEARCH_INSTRUMENTS) and funding_years >= 2, "usesNonOhlcv": True, "formalUse": "time_series_cross_exchange_proxy", "minimumFundingYears": funding_years},
        {"mechanismId": "high_liquidity_cross_sectional_momentum", "ready": False, "usesNonOhlcv": False, "formalUse": "diagnostic_only", "reason": "historical PIT listing and liquidity snapshots incomplete"},
    ]
    mechanism_matrix = {
        "schemaVersion": "factor_market_mechanism_matrix_v1",
        "pitStatus": snapshot["pitStatus"],
        "universeSplits": _pit_splits(),
        "mechanisms": mechanisms,
        "factorRoleLimit": 2,
        "allowedFactorRoles": ["confirmation", "ranking", "veto", "risk_context"],
    }
    write_json_atomic(factor_report_dir / "factor_market_mechanism_matrix.json", mechanism_matrix)
    controls_verified = bool(controls["positiveControl"]["passed"]) and all(not item["passed"] for item in controls["negativeControls"])
    readiness = evaluate_data_readiness(
        mechanisms,
        manifest_verified=bool(manifest["verified"]),
        controls_verified=controls_verified,
        trial_ledger_complete=len(trials) <= 192,
        fdr_complete=True,
        clusters_complete=bool(clusters["clusters"]),
        shortlist_frozen=frozen_shortlist.is_file(),
        pit_status=snapshot["pitStatus"],
    )
    readiness.update(
        {
            "dataSnapshotId": snapshot["snapshotId"],
            "factorShortlistId": shortlist_id,
            "eligibleFactorCount": len(selected),
            "formalTrialCount": len(trials),
            "controlsVerified": controls_verified,
        }
    )
    readiness_dir = repo / "reports" / "backtest_screening" / "data_readiness"
    write_json_atomic(readiness_dir / "phase3b_exit_gate.json", readiness)
    benchmark = {
        "schemaVersion": "factor_benchmark_report_v1",
        "status": "completed" if readiness["passed"] else "blocked",
        "dataSnapshotId": snapshot["snapshotId"],
        "factorShortlistId": shortlist_id,
        "seedFactorCount": len(seed["seedFactors"]),
        "formalTrialCount": len(trials),
        "eligibleFactorCount": len(selected),
        "fdrDiscoveryCount": len(fdr.discoveries),
        "controlStatus": "passed" if controls_verified else "failed",
        "pitStatus": snapshot["pitStatus"],
        "resultRunNetworkPolicy": "offline_enforced",
        "readinessPassed": readiness["passed"],
        "readinessBlockers": readiness["blockers"],
    }
    write_json_atomic(factor_report_dir / "factor_benchmark_report.json", benchmark)
    return {"benchmark": benchmark, "shortlist": shortlist, "readiness": readiness}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    args = parser.parse_args()
    result = run_factor_benchmark(repo_root=args.repo_root, data_root=args.data_root)
    print(json.dumps(result["benchmark"], ensure_ascii=False))
    return 0 if result["readiness"]["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
