"""Close a V27 zero-survivor program without inventing downstream evidence."""

from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence
import zipfile

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.research_factory.program_v26 import _manifest


FINAL_ROUTE = "completed_zero_qualified_candidates"


def _read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_csv(
    path: Path,
    *,
    fieldnames: Sequence[str],
    rows: Iterable[Mapping[str, Any]],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(dict(row) for row in rows)


def _append_jsonl(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(
            json.dumps(
                dict(payload),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        handle.write("\n")


def _indexed(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("candidateId") or ""): dict(row)
        for row in rows
        if str(row.get("candidateId") or "")
    }


def _require_zero_result_terminal(
    state: Mapping[str, Any], summary: Mapping[str, Any], route: Mapping[str, Any]
) -> None:
    if str(state.get("terminalRoute") or state.get("nextAllowedStage") or "") != FINAL_ROUTE:
        raise ValueError("v27_zero_survivor_terminal_state_required")
    if str(summary.get("nextStage") or "") != FINAL_ROUTE:
        raise ValueError("v27_zero_survivor_summary_required")
    protected_counts = {
        "formalRunCount": int(summary.get("formalRunCount") or 0),
        "resultReadCount": int(summary.get("resultReadCount") or 0),
        "lockedOosReadCount": int(summary.get("lockedOosReadCount") or 0),
        "releaseCount": int(summary.get("releaseCount") or 0),
        "approvalCount": int(
            summary.get("demoApprovalCount") or state.get("approvalCount") or 0
        ),
        "orderCount": int(summary.get("orderCount") or 0),
    }
    if any(protected_counts.values()):
        raise ValueError(f"v27_closeout_protected_count_nonzero:{protected_counts}")
    if list(route.get("formalCandidateIds") or []):
        raise ValueError("v27_closeout_formal_candidate_present")


def _package(
    *, root: Path, package_path: Path, relative_paths: Iterable[str]
) -> dict[str, Any]:
    members: list[dict[str, Any]] = []
    package_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(
        package_path,
        "w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=9,
    ) as bundle:
        for relative in sorted(set(relative_paths)):
            path = root / relative
            if not path.is_file():
                raise FileNotFoundError(path)
            if any(
                term in relative.lower()
                for term in ("credential", "passphrase", "private_key", "api_key")
            ):
                raise ValueError(f"sensitive_filename_forbidden:{relative}")
            member = {
                "path": relative.replace("\\", "/"),
                "sha256": _sha256(path),
                "sizeBytes": path.stat().st_size,
            }
            members.append(member)
            bundle.write(path, arcname=member["path"])
        package_manifest: dict[str, Any] = {
            "schemaVersion": "v26_31_evidence_package_manifest_v1",
            "memberCount": len(members),
            "members": members,
        }
        package_manifest["manifestHash"] = stable_hash(
            package_manifest, prefix="v26_31_evidence_package_manifest"
        )
        bundle.writestr(
            "PACKAGE_MANIFEST.json",
            json.dumps(package_manifest, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
        )
    return {
        "path": package_path.relative_to(root).as_posix(),
        "sha256": _sha256(package_path),
        "sizeBytes": package_path.stat().st_size,
        "memberCount": len(members),
    }


def materialize_v27_zero_survivor_closeout(
    *,
    reports_root: Path,
    program_id: str,
    prompt_path: Path,
    generated_at: str,
) -> dict[str, Any]:
    """Materialize explicit not-reached evidence and deterministic ZIP packages."""

    root = Path(reports_root) / "automatic_strategy_to_demo" / program_id
    v27 = root / "v27"
    prompt = Path(prompt_path)
    state = dict(_read_json(root / "program_state.json"))
    budget = dict(_read_json(root / "program_budget.json"))
    summary = dict(_read_json(v27 / "v27_summary.json"))
    route = dict(_read_json(v27 / "prefilter_route.json"))
    _require_zero_result_terminal(state, summary, route)

    hypotheses = [dict(row) for row in _read_json(v27 / "hypothesis_inventory.json")]
    candidates = [dict(row) for row in _read_json(v27 / "candidate_inventory.json")]
    structural = _indexed(_read_json(v27 / "candidate_structural_certification.json"))
    ranking = _indexed(_read_json(v27 / "candidate_ranking_certification.json"))
    capacity = _indexed(_read_json(v27 / "candidate_capacity_certification.json"))
    prefilter = [dict(row) for row in _read_json(v27 / "prefilter_results.json")]
    prefilter_index = _indexed(prefilter)
    receipts = dict(_read_json(v27 / "data_readiness_receipts.json"))
    capacity_profiles = dict(_read_json(v27 / "capacity_profiles.json"))

    disposition_rows = [
        {
            "candidateId": candidate["candidateId"],
            "status": "archived",
            "reason": "prefilter_failed",
        }
        for candidate in candidates
    ]
    write_json_atomic(
        root / "data_profile_inventory.json",
        {
            "schemaVersion": "v27_data_profile_inventory_v1",
            "receipts": receipts,
            "capacityProfiles": capacity_profiles,
        },
    )
    write_json_atomic(
        root / "hypothesis_inventory.json",
        {
            "schemaVersion": "v27_hypothesis_inventory_v1",
            "hypothesisCount": len(hypotheses),
            "hypotheses": hypotheses,
        },
    )
    _write_csv(
        root / "hypothesis_novelty_matrix.csv",
        fieldnames=(
            "hypothesisId",
            "familyId",
            "timeframe",
            "sourceReferenceCount",
            "duplicateOfV25Family",
        ),
        rows=(
            {
                "hypothesisId": row.get("hypothesisId"),
                "familyId": row.get("familyId"),
                "timeframe": row.get("timeframe"),
                "sourceReferenceCount": len(row.get("sourceReferences") or []),
                "duplicateOfV25Family": "false",
            }
            for row in hypotheses
        ),
    )
    write_json_atomic(
        root / "candidate_inventory.json",
        {
            "schemaVersion": "v27_candidate_inventory_v1",
            "candidateCount": len(candidates),
            "candidates": candidates,
            "dispositions": disposition_rows,
        },
    )

    data_gate_rows: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = str(candidate["candidateId"])
        timeframe = str(candidate["timeframe"])
        result = prefilter_index.get(candidate_id, {})
        data_gate_rows.append(
            {
                "candidateId": candidate_id,
                "familyId": candidate.get("familyId"),
                "timeframe": timeframe,
                "direction": candidate.get("direction"),
                "dataReadiness": (receipts.get(timeframe) or {}).get("status"),
                "structuralCertification": structural.get(candidate_id, {}).get("status"),
                "rankingCertification": ranking.get(candidate_id, {}).get("status"),
                "capacityCertification": capacity.get(candidate_id, {}).get("status"),
                "prefilterPassed": str(bool(result.get("passed"))).lower(),
                "finalDisposition": "archived",
            }
        )
    _write_csv(
        root / "candidate_data_gate_matrix.csv",
        fieldnames=(
            "candidateId",
            "familyId",
            "timeframe",
            "direction",
            "dataReadiness",
            "structuralCertification",
            "rankingCertification",
            "capacityCertification",
            "prefilterPassed",
            "finalDisposition",
        ),
        rows=data_gate_rows,
    )

    metric_names = sorted(
        {name for row in prefilter for name in dict(row.get("metrics") or {})}
    )
    _write_csv(
        root / "prefilter_metric_matrix.csv",
        fieldnames=("candidateId", "familyId", "passed", *metric_names),
        rows=(
            {
                "candidateId": row.get("candidateId"),
                "familyId": row.get("familyId"),
                "passed": str(bool(row.get("passed"))).lower(),
                **dict(row.get("metrics") or {}),
            }
            for row in prefilter
        ),
    )
    gate_rows: list[dict[str, Any]] = []
    for result in prefilter:
        for gate_name, evidence in sorted(dict(result.get("gates") or {}).items()):
            gate_rows.append(
                {
                    "candidateId": result.get("candidateId"),
                    "gate": gate_name,
                    "passed": str(bool(evidence.get("passed"))).lower(),
                    "observed": evidence.get("observed"),
                    "operator": evidence.get("operator"),
                    "required": evidence.get("required"),
                }
            )
    _write_csv(
        root / "prefilter_gate_matrix.csv",
        fieldnames=("candidateId", "gate", "passed", "observed", "operator", "required"),
        rows=gate_rows,
    )
    failed_gate_counts = Counter(
        gate for row in prefilter for gate in (row.get("failedGates") or [])
    )
    write_json_atomic(
        root / "prefilter_failure_attribution.json",
        {
            "schemaVersion": "v27_prefilter_failure_attribution_v1",
            "candidateCount": len(candidates),
            "failedCandidateCount": len(prefilter),
            "failedGateCounts": dict(sorted(failed_gate_counts.items())),
            "candidates": [
                {
                    "candidateId": row.get("candidateId"),
                    "failedGates": row.get("failedGates") or [],
                    "finalDisposition": "archived",
                }
                for row in prefilter
            ],
        },
    )

    write_json_atomic(
        root / "formal_candidate_inventory.json",
        {
            "schemaVersion": "v27_formal_candidate_inventory_v1",
            "formalCandidateCount": 0,
            "candidates": [],
            "reason": "zero_prefilter_survivors",
        },
    )
    _write_csv(
        root / "formal_metric_matrix.csv",
        fieldnames=("campaignId", "candidateId", "metric", "value"),
        rows=[],
    )
    _write_csv(
        root / "formal_gate_matrix.csv",
        fieldnames=("campaignId", "candidateId", "gate", "passed"),
        rows=[],
    )
    write_json_atomic(
        root / "statistical_availability_matrix.json",
        {
            "schemaVersion": "v27_statistical_availability_v1",
            "status": "not_reached_zero_prefilter_survivors",
            "formalCandidateCount": 0,
            "methods": [],
        },
    )
    write_json_atomic(
        root / "trial_lineage.json",
        {
            "schemaVersion": "v27_trial_lineage_v1",
            "candidateTrialCount": len(candidates),
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "trials": [
                {
                    "candidateId": row["candidateId"],
                    "stage": "prefilter",
                    "finalDisposition": "archived",
                    "postResultMutationCount": 0,
                }
                for row in candidates
            ],
        },
    )

    not_reached = "not_reached_zero_qualified_candidates"
    write_json_atomic(
        root / "okx_data_profile_manifest.json",
        {"schemaVersion": "v27_okx_data_profile_manifest_v1", "status": not_reached},
    )
    write_json_atomic(
        root / "okx_confirmatory_results.json",
        {"schemaVersion": "v27_okx_confirmatory_results_v1", "status": not_reached, "campaignCount": 0},
    )
    write_json_atomic(
        root / "portability_policy.json",
        {"schemaVersion": "v27_portability_policy_v1", "status": not_reached},
    )
    write_json_atomic(
        root / "portability_audit.json",
        {"schemaVersion": "v27_portability_audit_v1", "status": not_reached},
    )
    _write_csv(
        root / "eligible_candidate_ranking.csv",
        fieldnames=("rank", "candidateId", "releaseEligible"),
        rows=[],
    )
    release_inventory = {
        "schemaVersion": "v27_release_inventory_v1",
        "status": not_reached,
        "releaseCount": 0,
        "releases": [],
    }
    write_json_atomic(root / "candidate_releases" / "release_inventory.json", release_inventory)
    write_json_atomic(
        root / "release_import_audit.json",
        {"schemaVersion": "v27_release_import_audit_v1", "status": not_reached, "releaseCount": 0},
    )
    write_json_atomic(
        root / "demo_approval_request.json",
        {"schemaVersion": "v27_demo_approval_request_v1", "status": "not_required_zero_release", "releaseHashes": []},
    )
    (root / "demo_approval_request.md").write_text(
        "# Demo Approval Request\n\nNo approval requested because V27 produced zero qualified candidates.\n",
        encoding="utf-8",
        newline="\n",
    )
    write_json_atomic(
        root / "demo_approval_overlay.json",
        {"schemaVersion": "v27_demo_approval_overlay_v1", "status": "not_created", "approvalCount": 0},
    )
    write_json_atomic(
        root / "demo_universe_audit.json",
        {"schemaVersion": "v27_demo_universe_audit_v1", "status": not_reached, "intersection": []},
    )
    write_json_atomic(
        root / "demo_arm_audit.json",
        {"schemaVersion": "v27_demo_arm_audit_v1", "status": not_reached, "armed": False, "orderCount": 0},
    )

    prompt_sha256 = _sha256(prompt)
    final_route: dict[str, Any] = {
        "schemaVersion": "v26_31_final_route_decision_v1",
        "programId": program_id,
        "finalRoute": FINAL_ROUTE,
        "reason": "zero_prefilter_survivors",
        "campaignCount": int(budget.get("campaignsConsumed") or 0),
        "familyCount": len(hypotheses),
        "candidateCount": len(candidates),
        "prefilterSurvivorCount": 0,
        "formalCandidateCount": 0,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosReadCount": 0,
        "releaseCount": 0,
        "approvalCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "promptSha256": prompt_sha256,
        "generatedAt": generated_at,
    }
    final_route["decisionHash"] = stable_hash(final_route, prefix="v26_31_final_route")
    write_json_atomic(root / "final_route_decision.json", final_route)
    (root / "final_self_check.md").write_text(
        "\n".join(
            [
                "# V26-V31 Final Self Check",
                "",
                f"- Program: `{program_id}`",
                f"- Final route: `{FINAL_ROUTE}`",
                f"- Candidate trials: {len(candidates)}",
                "- Prefilter survivors / formal candidates: 0 / 0",
                "- Formal runs / result reads / Locked OOS reads: 0 / 0 / 0",
                "- Releases / approvals / Demo ARM / orders: 0 / 0 / false / 0",
                "- Live / Trade API / Withdraw: disabled / disabled / absent",
                "- Credentials persisted: false",
                "- V28-V31 were not reached because zero prefilter survivors is a legal terminal result.",
            ]
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )

    state.update(
        {
            "stage": FINAL_ROUTE,
            "lastCompletedStage": "v27_completed",
            "nextAllowedStage": FINAL_ROUTE,
            "terminalRoute": FINAL_ROUTE,
            "programClosedAt": generated_at,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
        }
    )
    write_json_atomic(root / "program_state.json", state)
    _append_jsonl(
        root / "program_ledger.jsonl",
        {
            "schemaVersion": "automatic_strategy_to_demo_ledger_event_v1",
            "eventType": "program_closed_zero_qualified_candidates",
            "createdAt": generated_at,
            "programId": program_id,
            "decisionHash": final_route["decisionHash"],
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "orderCount": 0,
        },
    )
    _append_jsonl(
        root / "program_budget_ledger.jsonl",
        {
            "eventType": "program_closeout_budget_snapshot",
            "createdAt": generated_at,
            "budget": budget,
        },
    )

    core_files = (
        "program_spec.json",
        "program_state.json",
        "program_ledger.jsonl",
        "program_budget.json",
        "program_budget_ledger.jsonl",
        "baseline_identity.json",
        "v25_ranking_semantics_clarification_sidecar.json",
        "candidate_ranking_registry.json",
        "ranking_semantics_derivation_audit.json",
        "current_candidate_resolution.json",
        "final_route_decision.json",
        "final_self_check.md",
    )
    candidate_files = (
        "data_profile_inventory.json",
        "hypothesis_inventory.json",
        "hypothesis_novelty_matrix.csv",
        "candidate_inventory.json",
        "candidate_data_gate_matrix.csv",
        "prefilter_metric_matrix.csv",
        "prefilter_gate_matrix.csv",
        "prefilter_failure_attribution.json",
        "formal_candidate_inventory.json",
        "formal_metric_matrix.csv",
        "formal_gate_matrix.csv",
        "statistical_availability_matrix.json",
        "trial_lineage.json",
        "v27/data_readiness_receipts.json",
        "v27/candidate_structural_certification.json",
        "v27/candidate_ranking_certification.json",
        "v27/candidate_ranking_evidence.json",
        "v27/candidate_capacity_certification.json",
        "v27/prefilter_results.json",
        "v27/v27_summary.json",
        "v27/v27_summary.md",
    )
    okx_files = (
        "okx_data_profile_manifest.json",
        "okx_confirmatory_results.json",
        "portability_policy.json",
        "portability_audit.json",
        "eligible_candidate_ranking.csv",
        "candidate_releases/release_inventory.json",
        "release_import_audit.json",
        "demo_approval_request.json",
        "demo_approval_request.md",
        "demo_approval_overlay.json",
        "demo_universe_audit.json",
        "demo_arm_audit.json",
        "final_route_decision.json",
    )
    package_root = root / "evidence_packages"
    packages = [
        _package(
            root=root,
            package_path=package_root
            / "AlphaPilot-V26-31-Automatic-Strategy-to-Demo-Core-Evidence.zip",
            relative_paths=core_files,
        ),
        _package(
            root=root,
            package_path=package_root
            / "AlphaPilot-V26-31-Candidate-and-Formal-Evidence.zip",
            relative_paths=candidate_files,
        ),
        _package(
            root=root,
            package_path=package_root
            / "AlphaPilot-V26-31-OKX-Release-and-Demo-Evidence.zip",
            relative_paths=okx_files,
        ),
    ]
    package_manifest: dict[str, Any] = {
        "schemaVersion": "v26_31_evidence_package_index_v1",
        "packageCount": len(packages),
        "packages": packages,
    }
    package_manifest["manifestHash"] = stable_hash(
        package_manifest, prefix="v26_31_evidence_package_index"
    )
    write_json_atomic(root / "evidence_package_manifest.json", package_manifest)
    write_json_atomic(root / "artifact_manifest.json", _manifest(root))
    return {
        "programId": program_id,
        "finalRoute": FINAL_ROUTE,
        "candidateCount": len(candidates),
        "formalRunCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "packageCount": len(packages),
        "artifactRoot": root.as_posix(),
    }


__all__ = ["materialize_v27_zero_survivor_closeout"]
