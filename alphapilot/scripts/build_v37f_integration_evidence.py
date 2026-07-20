"""Build V37F integration, budget, and Formal gate parity evidence."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any, Sequence

from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.formal_validation.formal_gate_evaluation import (
    build_fold_assignment_gate,
    evaluate_formal_gates,
)
from alphapilot.integration.v37f_budget_reconciliation import reconcile_budget


QUANT_BRANCHES = (
    "feature/v13.27.1.33-34a-official-data-pilot",
    "feature/v13.27.1.34b-funding-pit-forward",
    "feature/v13.27.1.34c-public-data-scheduler",
    "feature/v13.27.1.35-standard-replication-playbook",
    "feature/v13.27.1.36-strategy-research",
    "feature/v13.27.1.36-tsmom-formal-handoff",
    "feature/v13.27.1.36.5-mechanism-renewal",
    "feature/v13.27.1.37a-funding-data-capability",
    "feature/v13.27.1.37b-reference-strategy-campaign",
    "feature/v13.27.1.37c-reference-strategy-parity-audit",
    "feature/v13.27.1.37d-source-faithful-reproduction",
    "feature/v13.27.1.37e-candidate-replay-tsmom-formal-closure",
)

DEVELOPMENT_SUMMARIES = (
    Path(
        "reports/candidate_research/v36/"
        "v36-development-replay-okx-v34c-20260719/campaign_summary.json"
    ),
    Path(
        "reports/candidate_research/v36_5/"
        "v36-5-intraday-session-development-okx-v34c-20260719/"
        "campaign_summary.json"
    ),
    Path(
        "reports/candidate_research/v36_6/"
        "v36-6-btc-downside-spillover-development-core20-20260719/"
        "campaign_summary.json"
    ),
    Path(
        "reports/candidate_research/v37e/"
        "v37e-bounded-replay-v36-eligible-20260719/campaign_summary.json"
    ),
)

INHERITED_BUDGET = Path(
    "reports/dual_track/alphapilot_dual_track_v33_6af4e494293f4167/"
    "inherited_budget.json"
)

FULL_BACKTEST_EVIDENCE = (
    Path(
        "reports/backtest_screening/reference_strategy_research/"
        "v37b-reference-c714273e3046-231c239eb744/closeout.json"
    ),
)

V37E_HISTORICAL_ROOT = Path(
    "reports/formal_validation/v37e2_tsmom_formal_results/"
    "v36_tsmom_formal_v37e_tsmom_daily_capacity_successor_70f71f31cd87914a/"
    "v37e_tsmom_daily_capacity_successor"
)


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout.strip()


def _branch_receipt(repo_root: Path, branch: str, head: str) -> dict[str, Any]:
    candidates = (f"origin/{branch}", branch)
    commit = None
    source_ref = None
    for ref in candidates:
        value = _git(repo_root, "rev-parse", "--verify", ref, check=False)
        if value:
            commit = value
            source_ref = ref
            break
    if commit is None or source_ref is None:
        return {
            "branch": branch,
            "status": "missing_ref",
            "commit": None,
            "sourceRef": None,
            "isAncestorOfIntegratedHead": False,
        }
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, head],
        cwd=repo_root,
        check=False,
        capture_output=True,
    ).returncode == 0
    return {
        "branch": branch,
        "status": "integrated" if ancestor else "not_integrated",
        "commit": commit,
        "sourceRef": source_ref,
        "isAncestorOfIntegratedHead": ancestor,
    }


def _gate(
    gate_id: str,
    *,
    passed: bool | None,
    gate_class: str = "admission",
    route_class: str = "economic",
) -> dict[str, Any]:
    return {
        "gateId": gate_id,
        "gateClass": gate_class,
        "routeClass": route_class,
        "status": "unavailable" if passed is None else "passed" if passed else "failed",
        "passed": passed,
        "actual": None if passed is None else int(not passed),
        "threshold": 0,
        "reasonCode": None if passed is True else f"{gate_id}_not_passed",
        "evidenceRefs": ["tests/formal_validation/test_formal_gate_evaluation.py"],
    }


def _parity_scenario(
    scenario_id: str,
    *,
    rows: Sequence[dict[str, Any]],
    implementation_blockers: Sequence[str] = (),
    funding_route_cap: bool = False,
) -> dict[str, Any]:
    evaluation = evaluate_formal_gates(
        gate_rows=rows,
        implementation_blockers=implementation_blockers,
        stopping_rules={
            "economicGateFailure": "archive_candidate",
            "implementationInvalid": "implementation_invalid",
            "statisticsUnavailable": "statistics_unavailable",
        },
        comparable_candidate_panel_status="available",
        funding_unavailable_is_route_cap=funding_route_cap,
    )
    matrix = evaluation.gate_matrix
    route = evaluation.route_payload(scenario_id)
    failure = evaluation.failure_attribution(scenario_id)
    summary = evaluation.summary_fields()
    blocker_views = {
        "gateMatrix": matrix["routeBlockers"],
        "routeDecision": route["blockers"],
        "failureAttribution": failure["blockers"],
        "campaignSummary": summary["blockers"],
    }
    return {
        "scenarioId": scenario_id,
        "route": evaluation.route,
        "blockerViews": blocker_views,
        "blockersConsistent": len({tuple(v) for v in blocker_views.values()}) == 1,
        "gateRows": matrix["gates"],
    }


def _build_parity_audit() -> dict[str, Any]:
    fold = build_fold_assignment_gate(
        {
            "explicitlyExcludedEventCount": 11,
            "unclassifiedEventCount": 0,
            "multiAssignedEventCount": 0,
            "unknownDispositionCount": 0,
            "crossBoundaryLeakageCount": 0,
        }
    )
    scenarios = [
        _parity_scenario(
            "economic_failure",
            rows=[_gate("minimum_profit_factor", passed=False)],
        ),
        _parity_scenario(
            "implementation_failure",
            rows=[
                _gate(
                    "translation_parity",
                    passed=False,
                    route_class="implementation",
                )
            ],
        ),
        _parity_scenario(
            "diagnostic_failure_only",
            rows=[
                _gate(
                    "diagnostic_sample_shape",
                    passed=False,
                    gate_class="diagnostic",
                )
            ],
        ),
        _parity_scenario("legal_fold_exclusion", rows=[fold]),
        _parity_scenario(
            "funding_unavailable_route_cap",
            rows=[_gate("conservative_funding_average_net_r", passed=None)],
            funding_route_cap=True,
        ),
    ]
    return {
        "schemaVersion": "alphapilot_v37f_formal_gate_parity_audit_v1",
        "status": (
            "passed" if all(row["blockersConsistent"] for row in scenarios) else "failed"
        ),
        "singleSource": "FormalGateEvaluation",
        "foldGateUsesForbiddenOutcomesOnly": fold["passed"] is True,
        "scenarios": scenarios,
    }


def _manifest(output_root: Path) -> dict[str, Any]:
    artifacts = []
    for path in sorted(output_root.glob("*.json")):
        if path.name == "artifact_manifest.json":
            continue
        artifacts.append(
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "sizeBytes": path.stat().st_size,
            }
        )
    return {
        "schemaVersion": "alphapilot_v37f_integration_artifact_manifest_v1",
        "artifacts": artifacts,
    }


def build_evidence(repo_root: Path, output_root: Path) -> dict[str, Path]:
    repo_root = repo_root.resolve()
    output_root = output_root.resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    formal_ledgers = sorted(
        path.relative_to(repo_root)
        for pattern in (
            "reports/formal_validation/v36_tsmom_formal_results/**/formal_run_ledger.json",
            "reports/formal_validation/v37e*_tsmom_formal_results/**/formal_run_ledger.json",
        )
        for path in repo_root.glob(pattern)
    )
    budget = reconcile_budget(
        root=repo_root,
        inherited_budget_path=INHERITED_BUDGET,
        development_summary_paths=DEVELOPMENT_SUMMARIES,
        full_backtest_evidence_paths=FULL_BACKTEST_EVIDENCE,
        formal_ledger_paths=formal_ledgers,
    )
    _write_json(output_root / "budget_reconciliation.json", budget)

    head = _git(repo_root, "rev-parse", "HEAD")
    branches = [_branch_receipt(repo_root, branch, head) for branch in QUANT_BRANCHES]
    integration = {
        "schemaVersion": "alphapilot_v37f_integration_merge_receipt_v1",
        "integratedHead": head,
        "branchReceipts": branches,
        "allRequiredBranchesIntegrated": all(
            row["isAncestorOfIntegratedHead"] for row in branches
        ),
        "historyPolicy": "merge_or_linear_ancestor_no_rebase_of_result_history",
        "historicalArtifactModificationCount": 0,
        "formalResultRerunCount": 0,
    }
    _write_json(output_root / "integration_merge_receipt.json", integration)

    parity = _build_parity_audit()
    _write_json(output_root / "formal_gate_parity_audit.json", parity)

    historical_refs = []
    for name in (
        "gate_matrix.json",
        "route_decision.json",
        "failure_attribution.json",
        "campaign_summary.json",
    ):
        relative = V37E_HISTORICAL_ROOT / name
        path = repo_root / relative
        historical_refs.append(
            {"path": relative.as_posix(), "sha256": sha256_file(path)}
        )
    sidecar = {
        "schemaVersion": "alphapilot_v37e_gate_semantics_clarification_sidecar_v1",
        "historicalRouteChanged": False,
        "historicalAdmissionChanged": False,
        "reportingConsistencyPatched": True,
        "clarification": {
            "foldAssignment": (
                "Legal exclusions do not fail fold_assignment_complete; only "
                "unclassified, multi-assigned, unknown-disposition, or "
                "cross-boundary-leakage events fail it."
            ),
            "blockerProjection": (
                "Prospective Formal reports derive gate_matrix, route_decision, "
                "failure_attribution, and campaign_summary from one evaluation."
            ),
        },
        "historicalArtifactRefs": historical_refs,
    }
    _write_json(
        output_root / "v37e_gate_semantics_clarification_sidecar.json", sidecar
    )
    _write_json(output_root / "artifact_manifest.json", _manifest(output_root))
    return {path.name: path for path in output_root.glob("*.json")}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("reports/integration/v37f"),
    )
    args = parser.parse_args()
    output = (
        args.output_root
        if args.output_root.is_absolute()
        else args.repo_root / args.output_root
    )
    written = build_evidence(args.repo_root, output)
    print(json.dumps({"written": sorted(written)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
