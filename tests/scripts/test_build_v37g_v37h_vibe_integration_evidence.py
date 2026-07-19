from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alphapilot.scripts.build_v37g_v37h_vibe_integration_evidence import (
    PINNED_VIBE_COMMIT,
    build_evidence,
)


def test_build_evidence_pins_vibe_and_writes_complete_audit(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[2]
    output_root = tmp_path / "v37g_v37h"

    written = build_evidence(repo_root, output_root)

    required = {
        "vibe_trading_source_manifest.json",
        "vibe_component_adoption_map.json",
        "vibe_license_notice.md",
        "strategy_artifact_store_schema.json",
        "source_inventory.json",
        "mechanism_inventory.json",
        "source_equivalence_matrix.csv",
        "artifact_lifecycle_history.jsonl",
        "generated_candidate_sandbox_audit.json",
        "factor_registry.json",
        "factor_bench_matrix.csv",
        "artifact_similarity_matrix.parquet",
        "artifact_similarity_summary.csv",
        "candidate_dedup_decision.json",
        "artifact_manifest.json",
        "verification_summary.json",
        "v37g_v37h_closeout.md",
    }
    assert required == set(written)

    source = json.loads(
        (output_root / "vibe_trading_source_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert source["repository"] == "HKUDS/Vibe-Trading"
    assert source["commit"] == PINNED_VIBE_COMMIT
    assert source["license"] == "MIT"
    assert source["runtimeDependency"] is False
    assert source["copiedCode"] == []
    assert all(item["blobSha"] for item in source["paths"])

    sandbox = json.loads(
        (output_root / "generated_candidate_sandbox_audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert sandbox["safeCandidate"]["status"] == "passed"
    assert sandbox["unreachableNetworkHelper"]["status"] == "rejected"
    assert sandbox["unreachableNetworkHelper"]["audit"]["offline"] is True
    assert sandbox["boundaryClaim"] == "research_execution_guard_not_os_security_boundary"

    factors = json.loads(
        (output_root / "factor_registry.json").read_text(encoding="utf-8")
    )
    assert 1 <= len(factors) <= 36
    assert all(item["pointInTimeReady"] is True for item in factors)
    similarity = pd.read_parquet(output_root / "artifact_similarity_matrix.parquet")
    assert {
        "exact_duplicate",
        "near_duplicate",
        "same_family_variant",
        "mechanism_related",
        "independent",
    }.issubset(set(similarity["classification"]))

    verification = json.loads(
        (output_root / "verification_summary.json").read_text(encoding="utf-8")
    )
    assert verification["status"] == "passed"
    assert verification["sideEffects"] == {
        "formalRunCount": 0,
        "lockedOosReadCount": 0,
        "releaseCount": 0,
        "demoArmCount": 0,
        "orderCount": 0,
        "liveCount": 0,
    }

