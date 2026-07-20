"""Run and persist the two bounded V37I acquisition campaigns."""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .catalog import build_candidate_catalog
from .contracts import V37IBudget
from .formal_route import build_v37j_route
from .prefilter import evaluate_candidate, load_development_panels


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"json_object_required:{path}")
    return value


def run_bounded_acquisition(
    *,
    panel_manifest_path: Path,
    inherited_budget_path: Path,
    output_root: Path,
    frozen_at: str,
) -> dict[str, Any]:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    catalog = build_candidate_catalog()
    budget = V37IBudget.default()
    variants: dict[str, int] = Counter(candidate.family_id for candidate in catalog)
    budget.validate(
        campaigns=len({candidate.campaign_id for candidate in catalog}),
        families=len({candidate.family_id for candidate in catalog}),
        candidates=len(catalog),
        variants_by_family=variants,
        structural_revisions_by_family={},
    )
    inherited_budget = _load_json(Path(inherited_budget_path))
    remaining = int(
        inherited_budget.get("remainingByAuthoritativePolicy", {})
        .get("fullBacktests", {})
        .get("value")
        or 0
    )
    executable_count = sum(1 for candidate in catalog if not candidate.prefilter_blocker)
    if executable_count > remaining:
        raise ValueError("inherited_full_backtest_budget_exceeded")

    panel_manifest = _load_json(Path(panel_manifest_path))
    panels, data_audit = load_development_panels(panel_manifest)
    candidate_results = [evaluate_candidate(candidate, panels) for candidate in catalog]
    result_lookup = {row["candidateId"]: row for row in candidate_results}

    candidate_inventory = {
        "schemaVersion": "alphapilot_v37i_candidate_inventory_v1",
        "frozenAt": frozen_at,
        "candidateCount": len(catalog),
        "candidates": [
            {
                **candidate.to_dict(),
                "result": result_lookup[candidate.candidate_id],
            }
            for candidate in catalog
        ],
        "lockedOosReadCount": 0,
    }
    write_json_atomic(output_root / "candidate_inventory.json", candidate_inventory)

    by_campaign: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for result in candidate_results:
        by_campaign[str(result["campaignId"])].append(result)
    campaign_rows = []
    for campaign_id, rows in sorted(by_campaign.items()):
        campaign_rows.append(
            {
                "campaignId": campaign_id,
                "candidateCount": len(rows),
                "prefilterSurvivorCount": sum(bool(row["prefilterPassed"]) for row in rows),
                "status": (
                    "completed_with_prefilter_survivors"
                    if any(bool(row["prefilterPassed"]) for row in rows)
                    else "completed_zero_qualified_candidates"
                ),
            }
        )
    campaign_inventory = {
        "schemaVersion": "alphapilot_v37i_campaign_inventory_v1",
        "frozenAt": frozen_at,
        "policy": asdict(budget),
        "policyHash": budget.policy_hash,
        "campaignCount": len(campaign_rows),
        "campaigns": campaign_rows,
    }
    write_json_atomic(output_root / "campaign_inventory.json", campaign_inventory)
    write_json_atomic(output_root / "development_data_audit.json", data_audit)

    prefilter_rows = [
        {
            "campaignId": row["campaignId"],
            "candidateId": row["candidateId"],
            "familyId": row["familyId"],
            "candidateHash": row["candidateHash"],
            "status": row["status"],
            "prefilterPassed": row["prefilterPassed"],
            "reasonCode": row["reasonCode"],
            "trialCount": row["trialCount"],
            "passedTrialCount": row["passedTrialCount"],
            "bestTradeCount": row.get("bestTradeCount"),
            "bestNetReturn": row.get("bestNetReturn"),
            "bestProfitFactor": row.get("bestProfitFactor"),
            "bestMaximumDrawdown": row.get("bestMaximumDrawdown"),
            "lockedOosReadCount": 0,
        }
        for row in candidate_results
    ]
    prefilter_fields = [
        "campaignId",
        "candidateId",
        "familyId",
        "candidateHash",
        "status",
        "prefilterPassed",
        "reasonCode",
        "trialCount",
        "passedTrialCount",
        "bestTradeCount",
        "bestNetReturn",
        "bestProfitFactor",
        "bestMaximumDrawdown",
        "lockedOosReadCount",
    ]
    _write_csv(output_root / "prefilter_matrix.csv", prefilter_rows, prefilter_fields)
    pd.DataFrame(prefilter_rows).to_parquet(
        output_root / "candidate_results.parquet", index=False
    )

    equivalence_rows = [
        {
            "candidateId": candidate.candidate_id,
            "sourceEquivalenceClass": candidate.source_equivalence_class,
            "similarityClassification": candidate.similarity_classification,
            "decision": (
                "blocked_duplicate"
                if candidate.prefilter_blocker
                else "admitted_to_bounded_prefilter"
            ),
            "sourcePath": candidate.source_path,
        }
        for candidate in catalog
    ]
    _write_csv(
        output_root / "source_equivalence_matrix.csv",
        equivalence_rows,
        [
            "candidateId",
            "sourceEquivalenceClass",
            "similarityClassification",
            "decision",
            "sourcePath",
        ],
    )

    failures = [row for row in candidate_results if not row["prefilterPassed"]]
    failure_attribution = {
        "schemaVersion": "alphapilot_v37i_failure_attribution_v1",
        "failureCount": len(failures),
        "byReason": dict(sorted(Counter(row["reasonCode"] for row in failures).items())),
        "failures": [
            {
                "candidateId": row["candidateId"],
                "candidateHash": row["candidateHash"],
                "reasonCode": row["reasonCode"],
                "evidenceRef": "prefilter_matrix.csv",
            }
            for row in failures
        ],
    }
    write_json_atomic(output_root / "failure_attribution.json", failure_attribution)

    formal_route = build_v37j_route(candidate_rows=candidate_results)
    write_json_atomic(output_root / "formal_route.json", formal_route)
    _write_csv(
        output_root / "formal_matrix.csv",
        [
            {
                "candidateId": candidate_id,
                "status": "awaiting_candidate_panel_and_preregistration_freeze",
                "formalRunCount": 0,
                "resultReadCount": 0,
                "releaseCount": 0,
            }
            for candidate_id in formal_route["formalCandidateIds"]
        ],
        ["candidateId", "status", "formalRunCount", "resultReadCount", "releaseCount"],
    )
    write_json_atomic(
        output_root / "statistical_matrix.json",
        {
            "schemaVersion": "alphapilot_v37j_statistical_matrix_v1",
            "status": "not_run_no_prefilter_survivors" if not formal_route["formalCandidateIds"] else "not_run_pending_freeze",
            "candidateCount": len(formal_route["formalCandidateIds"]),
            "formalRunCount": 0,
            "resultReadCount": 0,
        },
    )

    budget_evidence = {
        "schemaVersion": "alphapilot_v37i_experiment_budget_v1",
        "policy": asdict(budget),
        "policyHash": budget.policy_hash,
        "inheritedBudgetPath": str(inherited_budget_path),
        "inheritedFullBacktestsRemainingBefore": remaining,
        "campaignsUsed": len(campaign_rows),
        "familiesUsed": len(variants),
        "candidatesRegistered": len(catalog),
        "fullBacktestsUsed": executable_count,
        "developmentTrialsUsed": sum(row["trialCount"] for row in candidate_results),
        "structuralRevisionsUsed": 0,
        "fullBacktestsRemainingAfter": remaining - executable_count,
        "budgetReset": False,
    }
    write_json_atomic(output_root / "experiment_budget.json", budget_evidence)

    lifecycle_path = output_root / "artifact_lifecycle_history.jsonl"
    with lifecycle_path.open("w", encoding="utf-8", newline="\n") as handle:
        for candidate in catalog:
            result = result_lookup[candidate.candidate_id]
            statuses = ["source_ingested", "mechanism_extracted", "candidate_draft", "candidate_frozen"]
            if candidate.prefilter_blocker:
                statuses.extend(["prefilter_running", "prefilter_failed", "archived"])
            else:
                statuses.extend(
                    [
                        "prefilter_running",
                        "research_pass" if result["prefilterPassed"] else "prefilter_failed",
                    ]
                )
                if not result["prefilterPassed"]:
                    statuses.append("archived")
            previous = None
            previous_hash = None
            for status in statuses:
                event = {
                    "candidateId": candidate.candidate_id,
                    "candidateHash": candidate.candidate_hash,
                    "previousStatus": previous,
                    "nextStatus": status,
                    "reasonCode": result["reasonCode"] if status in {"prefilter_failed", "archived"} else "bounded_campaign_progress",
                    "previousEventHash": previous_hash,
                    "createdAt": frozen_at,
                }
                event["eventHash"] = stable_hash(event, prefix="v37i_lifecycle")
                handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
                previous = status
                previous_hash = event["eventHash"]

    summary = {
        "schemaVersion": "alphapilot_v37i_v37j_campaign_summary_v1",
        "status": formal_route["status"],
        "frozenAt": frozen_at,
        "campaignCount": len(campaign_rows),
        "familyCount": len(variants),
        "candidateCount": len(catalog),
        "prefilterSurvivorCount": len(formal_route["formalCandidateIds"]),
        "formalCandidateCount": len(formal_route["formalCandidateIds"]),
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosReadCount": 0,
        "releaseCount": 0,
        "approved": False,
        "demoArm": False,
        "orderCount": 0,
        "tradeApiUsed": False,
        "withdrawApiUsed": False,
        "privateAccountReadUsed": False,
    }
    summary["summaryHash"] = stable_hash(summary, prefix="v37i_v37j_summary")
    write_json_atomic(output_root / "campaign_summary.json", summary)
    (output_root / "campaign_summary.md").write_text(
        "\n".join(
            [
                "# V37I / V37J Bounded Acquisition Closeout",
                "",
                f"- Status: `{summary['status']}`",
                f"- Campaigns: {summary['campaignCount']} / 2",
                f"- Families: {summary['familyCount']} / 6",
                f"- Candidates: {summary['candidateCount']} / 12",
                f"- Prefilter survivors: {summary['prefilterSurvivorCount']}",
                "- Locked OOS reads: 0",
                "- Formal runs: 0",
                "- Immutable releases: 0",
                "- Demo ARM: false",
                "- Orders: 0",
                "",
                "Zero qualified candidates is a valid terminal result. Gates were not relaxed.",
                "Turtle was rejected before evaluation because it duplicated archived TSMOM identity.",
                "Funding Carry remains ineligible for Demo until independent forward spot/perpetual order-book evidence exists.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )

    artifact_paths = sorted(
        path
        for path in output_root.iterdir()
        if path.is_file() and path.name != "artifact_manifest.json"
    )
    manifest = {
        "schemaVersion": "alphapilot_v37i_v37j_artifact_manifest_v1",
        "campaignSummaryHash": summary["summaryHash"],
        "artifacts": [
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "sizeBytes": path.stat().st_size,
            }
            for path in artifact_paths
        ],
    }
    manifest["manifestHash"] = stable_hash(manifest, prefix="v37i_v37j_manifest")
    write_json_atomic(output_root / "artifact_manifest.json", manifest)
    return summary
