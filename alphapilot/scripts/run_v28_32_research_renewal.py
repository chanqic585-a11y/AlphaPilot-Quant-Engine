"""Run the bounded V28-V32 research-renewal workflow."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.research_factory.artifact_paths import ProgramArtifactPaths
from alphapilot.research_factory.program_v28_32 import (
    build_research_renewal_program_id,
    refresh_artifact_manifest,
    run_research_renewal_program,
)


DEFAULT_PARENT_PROGRAM = "automatic_strategy_to_demo_v26_2aff44adf84d039c"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--reports-root", type=Path)
    parser.add_argument("--prompt-hash", required=True)
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--campaign-spec", type=Path)
    parser.add_argument(
        "--generated-at",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    )
    return parser.parse_args()


def build_catalog_readiness_audit(catalog: dict[str, Any]) -> dict[str, Any]:
    datasets = [dict(row) for row in catalog.get("datasets", [])]
    ohlcv = [row for row in datasets if row.get("dataType") == "ohlcv"]
    formal_ohlcv = [
        row
        for row in ohlcv
        if row.get("isPointInTime") is True
        and not str(row.get("exchange") or "").startswith("unverified")
        and str(row.get("provider") or "") != "user_confirmed_local_history"
        and str(row.get("contentHash") or "")
        and int(row.get("rowCount") or 0) > 0
    ]
    funding = [row for row in datasets if row.get("dataType") == "funding"]
    formal_funding = [
        row
        for row in funding
        if row.get("isPointInTime") is True
        and not str(row.get("exchange") or "").startswith("unverified")
        and str(row.get("contentHash") or "")
    ]
    formal_ready = bool(formal_ohlcv)
    blockers: list[str] = []
    if not ohlcv:
        blockers.append("ohlcv_missing")
    elif not formal_ohlcv:
        blockers.append("ohlcv_provenance_or_pit_semantics_unverified")
    payload: dict[str, Any] = {
        "schemaVersion": "v28_catalog_readiness_audit_v1",
        "catalogManifestHash": catalog.get("dataManifestHash"),
        "datasetCount": len(datasets),
        "ohlcvDatasetCount": len(ohlcv),
        "formalOhlcvDatasetCount": len(formal_ohlcv),
        "fundingDatasetCount": len(funding),
        "formalFundingDatasetCount": len(formal_funding),
        "formalReady": formal_ready,
        "releaseReady": False,
        "demoReady": False,
        "blockers": blockers,
        "candidateIdentityCreated": False,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "lockedOosReadCount": 0,
    }
    payload["auditHash"] = stable_hash(payload, prefix="v28_catalog_readiness")
    return payload


def _load_campaigns(path: Path | None) -> list[dict[str, Any]] | None:
    if path is None:
        return None
    value = json.loads(path.read_text(encoding="utf-8"))
    rows = value.get("campaigns") if isinstance(value, dict) else value
    if not isinstance(rows, list):
        raise ValueError("campaign_spec_must_contain_list")
    return [dict(row) for row in rows]


def main() -> int:
    args = _parse_args()
    repo_root = args.repo_root.resolve()
    reports_root = (args.reports_root or repo_root / "reports").resolve()
    catalog_path = (
        reports_root / "backtest_screening" / "data_readiness" / "dataset_catalog.json"
    )
    if not catalog_path.is_file():
        raise FileNotFoundError(catalog_path)
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    data_audit = build_catalog_readiness_audit(catalog)
    campaigns = _load_campaigns(args.campaign_spec)
    if campaigns is None:
        campaigns = [
            {
                "campaignId": "v28-causal-data-readiness-audit",
                "status": "ready" if data_audit["formalReady"] else "formal_data_blocked",
                "candidates": [],
            }
        ]

    eligibility_policy = {
        "schemaVersion": "causal_eligibility_window_v1",
        "eligibleEventCapacityCoveragePct": 100.0,
        "unclassifiedEventCount": 0,
        "postEntryReadCount": 0,
        "candidateWindowChosenAfterResults": False,
    }
    benchmark_policy = {
        "schemaVersion": "benchmark_comparability_contract_v1",
        "capitalComparableRequired": True,
        "eventComparableRequired": True,
        "diagnosticOnlyCannotAdvance": True,
    }
    baseline_commits = {
        "quant": "375c6429658e880060e0f3f914d551b7447b4140",
        "docs": "f8f529f2b9e31131782d2f09336c732f17f2b698",
    }
    summary = run_research_renewal_program(
        reports_root=reports_root,
        prompt_hash=args.prompt_hash,
        implementation_commit=args.implementation_commit,
        generated_at=args.generated_at,
        campaigns=campaigns,
        baseline_merge_commits=baseline_commits,
        eligibility_window_policy_hash=stable_hash(
            eligibility_policy, prefix="causal_eligibility_window_policy"
        ),
        benchmark_comparability_policy_hash=stable_hash(
            benchmark_policy, prefix="benchmark_comparability_policy"
        ),
    )
    paths = ProgramArtifactPaths(reports_root, str(summary["programId"]))
    write_json_atomic(paths.program_root / "v28_data_readiness_audit.json", data_audit)
    write_json_atomic(paths.program_root / "eligibility_window_policy.json", eligibility_policy)
    write_json_atomic(paths.program_root / "benchmark_comparability_policy.json", benchmark_policy)
    v27_audit: dict[str, Any] = {
        "schemaVersion": "v27_benchmark_read_only_audit_v1",
        "sourceProgramId": DEFAULT_PARENT_PROGRAM,
        "candidateId": "v27-range_expansion_close_followthrough-4h-long-v1",
        "candidateTotalNetR": 64.9102666,
        "benchmarkTotalNetR": 874.6873120,
        "incrementalNetR": -809.7770454,
        "status": "archived_benchmark_dominated",
        "candidateRerun": False,
        "candidateRevived": False,
        "historicalMutationCount": 0,
    }
    v27_audit["auditHash"] = stable_hash(v27_audit, prefix="v27_read_only_benchmark")
    write_json_atomic(paths.program_root / "v27_benchmark_read_only_audit.json", v27_audit)
    refresh_artifact_manifest(reports_root=reports_root, program_id=str(summary["programId"]))
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
