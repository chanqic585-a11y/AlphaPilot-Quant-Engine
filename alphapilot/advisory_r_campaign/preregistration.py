"""V15 preregistration frozen before any prefilter result is read."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash

from .candidates import build_candidate_inventory
from .trial_ledger import build_trial_ledger


REPRESENTATIVE_INSTRUMENTS = (
    "ADA-USDT-SWAP",
    "ALGO-USDT-SWAP",
    "AVAX-USDT-SWAP",
    "BCH-USDT-SWAP",
    "BTC-USDT-SWAP",
    "DOGE-USDT-SWAP",
    "ETH-USDT-SWAP",
    "FIL-USDT-SWAP",
    "LTC-USDT-SWAP",
    "XRP-USDT-SWAP",
)


def _candidate_contract(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidateId": row["candidateId"],
        "familyId": row["familyId"],
        "variantId": row["variantId"],
        "timeframe": row["timeframe"],
        "strategyType": row["strategyType"],
        "diagnosticOnly": row["diagnosticOnly"],
        "semanticFingerprint": row["semanticFingerprint"],
        "strategyDefinitionHash": row["strategyDefinitionHash"],
        "exitPolicy": row["exitPolicy"],
        "exitPolicyHash": row["exitPolicyHash"],
    }


def build_prefilter_preregistration(
    *,
    candidates: Sequence[Mapping[str, Any]],
    snapshot_id: str,
    snapshot_hash: str,
    exit_policy_bounds_hash: str,
) -> dict[str, Any]:
    contracts = [_candidate_contract(row) for row in candidates]
    trial_ledger = build_trial_ledger(candidates)
    campaign_identity = {
        "snapshotHash": snapshot_hash,
        "candidateHashes": [row["strategyDefinitionHash"] for row in contracts],
        "exitPolicyBoundsHash": exit_policy_bounds_hash,
    }
    campaign_id = stable_hash(campaign_identity, prefix="advisory_r_v15")[:48]
    core = {
        "schemaVersion": "advisory_r_prefilter_preregistration_v2",
        "campaignId": campaign_id,
        "stage": "representative_universe_economic_prefilter",
        "snapshotId": snapshot_id,
        "snapshotHash": snapshot_hash,
        "targetRGateMode": "advisory",
        "minimumTargetR": None,
        "exitPolicyRequired": True,
        "exitPolicyBoundsHash": exit_policy_bounds_hash,
        "candidateCount": len(contracts),
        "familyCount": len({str(row["familyId"]) for row in contracts}),
        "candidates": contracts,
        "trialLedgerHash": trial_ledger["trialLedgerHash"],
        "representativeUniverse": {
            "instrumentIds": list(REPRESENTATIVE_INSTRUMENTS),
            "selectedBeforeResults": True,
            "selectionRule": "frozen_v13_27_1_13_representative_universe",
        },
        "prefilterGates": {
            "minimumEvents": 30,
            "minimumHistoryMonths": 24,
            "minimumProfitFactor": 1.03,
            "minimumAverageRealizedNetR": 0.0,
            "minimumTotalRealizedNetR": 0.0,
            "minimumPositiveMonthRatio": 0.5,
            "maximumDrawdownPct": 35.0,
        },
        "portfolioPrefilterGates": {
            "minimumHistoryMonths": 24,
            "minimumNetReturn": 0.0,
            "minimumPositiveMonthRatio": 0.5,
            "maximumDrawdownPct": 35.0,
        },
        "routing": {
            "maximumSurvivors": 6,
            "maximumPerFamily": 1,
            "tieBreakOrder": [
                "complexityScore_ascending",
                "turnover_ascending",
                "maximumDrawdownPct_ascending",
                "simpleBenchmarkIncrement_descending",
                "candidateId_ascending",
            ],
        },
        "experimentBudget": {
            "candidateMaximum": 12,
            "familyMaximum": 8,
            "variantsPerFamilyMaximum": 2,
            "postResultExitPolicyChanges": 0,
            "prefilterRuns": 1,
        },
        "safetyBoundary": {
            "holdoutAccessCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    }
    return {
        **core,
        "preregistrationHash": stable_hash(core, prefix="advisory_r_prefilter_preregistration"),
    }


def _read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def freeze_prefilter_preregistration(
    *,
    repo_root: Path,
    snapshot_path: Path,
    bounds_path: Path,
) -> Path:
    snapshot = _read_object(snapshot_path)
    bounds = _read_object(bounds_path)
    bounds_hash = stable_hash(bounds, prefix="exit_policy_bounds")
    payload = build_prefilter_preregistration(
        candidates=build_candidate_inventory(),
        snapshot_id=str(snapshot["snapshotId"]),
        snapshot_hash=str(snapshot["snapshotHash"]),
        exit_policy_bounds_hash=bounds_hash,
    )
    output = (
        repo_root
        / "research"
        / "preregistrations"
        / f"{payload['campaignId']}_prefilter_v2.json"
    )
    if output.exists():
        existing = _read_object(output)
        if existing != payload:
            raise RuntimeError(f"frozen preregistration differs: {output}")
        return output
    _write_json_atomic(output, payload)
    return output

