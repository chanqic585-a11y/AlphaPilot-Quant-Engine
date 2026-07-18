"""Deterministic cross-stage closeout index for the V19-V24 program."""

from __future__ import annotations

import csv
import json
import shutil
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.program_types import ProgramBudget
from alphapilot.research_factory.program_v19 import _artifact_manifest


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected_json_object:{path}")
    return payload


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = list(rows[0]) if rows else []
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        if columns:
            writer.writeheader()
            writer.writerows(rows)


def _copy_required(source: Path, destination: Path) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)


def materialize_program_closeout(
    *,
    reports_root: Path,
    program_id: str,
    formal_result_root: Path,
    console_output_root: Path,
    prompt_path: Path,
    generated_at: str,
) -> dict[str, Any]:
    """Materialize reporting-only indexes without changing research outcomes."""

    paths = ProgramArtifactPaths(Path(reports_root), program_id)
    root = paths.program_root
    state = _read_json(root / "program_state.json")
    hypotheses = _read_json(root / "hypothesis_inventory.json").get("hypotheses", [])
    candidates = _read_json(root / "candidate_inventory.json").get("candidates", [])
    releases = _read_json(root / "release_inventory.json")
    campaign_id = str(state.get("activeCampaignId") or "")
    if not campaign_id:
        raise ValueError("active_campaign_id_missing")

    formal_root = Path(formal_result_root).resolve()
    console_root = Path(console_output_root).resolve()
    frozen_prompt = Path(prompt_path).resolve()
    accounting = _read_json(formal_root / "formal_run_accounting.json")
    route = _read_json(formal_root / "formal_route.json")
    gate = _read_json(formal_root / "gate_matrix.json")
    statistics = _read_json(formal_root / "statistical_audit.json")
    failure = _read_json(formal_root / "failure_attribution.json")

    prompt_sha256 = sha256_file(frozen_prompt)
    spec = {
        "schemaVersion": "automatic_strategy_demo_program_spec_reference_v1",
        "workflowVersion": "v13.27.1.19-24",
        "programId": program_id,
        "promptPath": frozen_prompt.as_posix(),
        "promptSha256": prompt_sha256,
        "programSpecHash": state.get("programSpecHash"),
        "advisoryR": True,
        "resultDrivenGateRelaxationForbidden": True,
        "lockedOosReadsAllowed": False,
    }
    write_json_atomic(root / "program_spec.json", spec)

    budget = ProgramBudget().to_dict()
    full_backtests = int(accounting.get("formalRunCount") or 0)
    budget_payload = {
        "schemaVersion": "automatic_strategy_demo_program_budget_v1",
        "programId": program_id,
        **budget,
    }
    budget_payload["budgetHash"] = stable_hash(budget_payload, prefix="program_budget")
    write_json_atomic(root / "program_budget.json", budget_payload)
    consumption = {
        "schemaVersion": "automatic_strategy_demo_budget_consumption_v1",
        "programId": program_id,
        "campaignsUsed": int(state.get("activeCampaignIndex") or 1),
        "familiesUsed": len({str(item.get("familyId")) for item in hypotheses}),
        "initialCandidatesUsed": len(candidates),
        "formalCandidatesUsed": 1,
        "fullBacktestsUsed": full_backtests,
        "fullBacktestsRemaining": max(0, budget["maximumFullBacktestsAcrossProgram"] - full_backtests),
        "demoReleasesUsed": int(releases.get("releaseCount") or 0),
        "terminalRoute": state.get("terminalRoute"),
        "generatedAt": generated_at,
    }
    consumption["consumptionHash"] = stable_hash(consumption, prefix="program_budget_consumption")
    write_json_atomic(root / "budget_consumption_summary.json", consumption)
    ledger_entry = {
        "eventType": "closeout_budget_snapshot",
        "createdAt": generated_at,
        "payload": consumption,
    }
    ledger_entry["eventHash"] = stable_hash(ledger_entry, prefix="program_budget_ledger_event")
    (root / "program_budget_ledger.jsonl").write_text(
        json.dumps(ledger_entry, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    candidate_id = str(accounting.get("candidateId") or route.get("candidateId") or "")
    campaign_inventory = {
        "schemaVersion": "automatic_strategy_demo_formal_campaign_inventory_v1",
        "campaigns": [
            {
                "campaignId": campaign_id,
                "candidateId": candidate_id,
                "formalRunCount": full_backtests,
                "resultReadCount": int(accounting.get("resultReadCount") or 0),
                "lockedOosAccessCount": int(accounting.get("lockedOosAccessCount") or 0),
                "route": route.get("status"),
                "releaseEligible": bool(route.get("releaseEligible")),
            }
        ],
    }
    write_json_atomic(root / "formal_campaign_inventory.json", campaign_inventory)
    _write_csv(
        root / "formal_metric_matrix.csv",
        [
            {
                "campaignId": campaign_id,
                "candidateId": candidate_id,
                "route": route.get("status"),
                "releaseEligible": str(bool(route.get("releaseEligible"))).lower(),
                "acceptedTradeCount": int(gate.get("acceptedTradeCount") or 0),
                "completeFoldCount": int(gate.get("completeFoldCount") or 0),
                "formalRunCount": full_backtests,
                "resultReadCount": int(accounting.get("resultReadCount") or 0),
                "lockedOosAccessCount": int(accounting.get("lockedOosAccessCount") or 0),
                "failureClass": failure.get("classification"),
            }
        ],
    )
    _write_csv(
        root / "formal_gate_matrix.csv",
        [
            {
                "campaignId": campaign_id,
                "candidateId": candidate_id,
                "gate": gate_name,
                "passed": str(bool(passed)).lower(),
            }
            for gate_name, passed in sorted(dict(gate.get("gates") or {}).items())
        ],
    )
    write_json_atomic(
        root / "statistical_availability_matrix.json",
        {
            "schemaVersion": "automatic_strategy_demo_statistical_availability_v1",
            "campaignId": campaign_id,
            "candidateId": candidate_id,
            "status": statistics.get("status"),
            "methods": statistics.get("methods", []),
            "unavailableReason": statistics.get("unavailableReason"),
        },
    )
    write_json_atomic(
        root / "trial_lineage.json",
        {
            "schemaVersion": "automatic_strategy_demo_trial_lineage_v1",
            "programId": program_id,
            "campaignId": campaign_id,
            "candidateId": candidate_id,
            "formalRunCount": full_backtests,
            "resultReadCount": int(accounting.get("resultReadCount") or 0),
            "lockedOosAccessCount": int(accounting.get("lockedOosAccessCount") or 0),
            "postResultTrialAdditionCount": int(statistics.get("postResultTrialAdditionCount") or 0),
            "formalArtifactRoot": formal_root.as_posix(),
        },
    )

    campaign_root = paths.campaign(campaign_id)
    for name in (
        "prefilter_metric_matrix.csv",
        "prefilter_gate_matrix.csv",
        "prefilter_failure_attribution.json",
    ):
        _copy_required(campaign_root / name, root / name)
    _copy_required(root / "release_inventory.json", root / "candidate_releases" / "release_inventory.json")

    for name in (
        "release_import_audit.json",
        "release_store_record.json",
        "engineering_smoke_isolation_audit.json",
        "demo_universe_audit.json",
        "demo_arm_audit.json",
        "demo_approval_request.json",
        "demo_approval_request.md",
        "demo_approval_overlay.json",
        "final_route_decision.json",
        "final_self_check.md",
    ):
        _copy_required(console_root / name, root / name)

    write_json_atomic(paths.artifact_manifest, _artifact_manifest(root))
    return {
        "programId": program_id,
        "terminalRoute": state.get("terminalRoute"),
        "fullBacktestsUsed": full_backtests,
        "releaseCount": int(releases.get("releaseCount") or 0),
        "artifactRoot": root.as_posix(),
    }


__all__ = ["materialize_program_closeout"]
