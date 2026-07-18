"""Freeze a code-only correction campaign before corrected results are read."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash


ORIGINAL_CAMPAIGN_ID = "advisory_r_v15_502e810045e366353db4dbcfa7d08fdf3"


def _candidate_contract(row: Mapping[str, Any]) -> dict[str, Any]:
    keys = (
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
    return {key: row[key] for key in keys}


def build_correction_preregistration(
    *,
    original: Mapping[str, Any],
    candidates: Sequence[Mapping[str, Any]],
    code_commit: str,
    implementation_conformance_hash: str,
    exit_policy_engine_hash: str,
    structure_rule_compiler_hash: str,
    benchmark_compiler_hash: str,
) -> dict[str, Any]:
    contracts = [_candidate_contract(row) for row in candidates]
    if contracts != [dict(row) for row in original["candidates"]]:
        raise RuntimeError("candidate contracts differ from immutable V15 preregistration")
    identity = {
        "correctionOfCampaignId": original["campaignId"],
        "originalPreregistrationHash": original["preregistrationHash"],
        "codeCommit": code_commit,
        "implementationConformanceHash": implementation_conformance_hash,
        "exitPolicyEngineHash": exit_policy_engine_hash,
        "structureRuleCompilerHash": structure_rule_compiler_hash,
        "benchmarkCompilerHash": benchmark_compiler_hash,
    }
    campaign_id = stable_hash(identity, prefix="advisory_r_v16_correction")[:56]
    core = {
        "schemaVersion": "advisory_r_correction_preregistration_v1",
        "campaignId": campaign_id,
        "correctionOfCampaignId": original["campaignId"],
        "correctionReason": "implementation_nonconformance",
        "originalPreregistrationHash": original["preregistrationHash"],
        "codeCommit": code_commit,
        "implementationConformanceHash": implementation_conformance_hash,
        "exitPolicyEngineHash": exit_policy_engine_hash,
        "structureRuleCompilerHash": structure_rule_compiler_hash,
        "benchmarkCompilerHash": benchmark_compiler_hash,
        "parameterChanges": 0,
        "candidateChanges": 0,
        "gateChanges": 0,
        "universeChanges": 0,
        "costChanges": 0,
        "snapshotId": original["snapshotId"],
        "snapshotHash": original["snapshotHash"],
        "exitPolicyBoundsHash": original["exitPolicyBoundsHash"],
        "targetRGateMode": "advisory",
        "minimumTargetR": None,
        "candidates": contracts,
        "representativeUniverse": original["representativeUniverse"],
        "prefilterGates": original["prefilterGates"],
        "portfolioPrefilterGates": original["portfolioPrefilterGates"],
        "routing": original["routing"],
        "experimentBudget": {
            **dict(original["experimentBudget"]),
            "implementationCorrectionAttempts": 1,
            "correctedPrefilterRuns": 1,
        },
        "safetyBoundary": {
            "lockedOosAccessCount": 0,
            "formalEvidenceCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    }
    return {
        **core,
        "preregistrationHash": stable_hash(
            core, prefix="advisory_r_correction_preregistration"
        ),
    }


def freeze_correction_preregistration(
    *,
    repo_root: Path,
    original_path: Path,
    candidates: Sequence[Mapping[str, Any]],
    code_commit: str,
    implementation_conformance_hash: str,
    exit_policy_engine_hash: str,
    structure_rule_compiler_hash: str,
    benchmark_compiler_hash: str,
) -> Path:
    original = json.loads(original_path.read_text(encoding="utf-8"))
    payload = build_correction_preregistration(
        original=original,
        candidates=candidates,
        code_commit=code_commit,
        implementation_conformance_hash=implementation_conformance_hash,
        exit_policy_engine_hash=exit_policy_engine_hash,
        structure_rule_compiler_hash=structure_rule_compiler_hash,
        benchmark_compiler_hash=benchmark_compiler_hash,
    )
    path = repo_root / "research" / "preregistrations" / f"{payload['campaignId']}.json"
    if path.exists():
        if json.loads(path.read_text(encoding="utf-8")) != payload:
            raise RuntimeError(f"frozen correction preregistration differs: {path}")
        return path
    write_json_atomic(path, payload)
    return path


def main() -> int:
    from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--original", type=Path, required=True)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--implementation-conformance-hash", required=True)
    parser.add_argument("--exit-policy-engine-hash", required=True)
    parser.add_argument("--structure-rule-compiler-hash", required=True)
    parser.add_argument("--benchmark-compiler-hash", required=True)
    args = parser.parse_args()
    path = freeze_correction_preregistration(
        repo_root=args.repo_root.resolve(),
        original_path=args.original.resolve(),
        candidates=build_candidate_inventory(),
        code_commit=args.code_commit,
        implementation_conformance_hash=args.implementation_conformance_hash,
        exit_policy_engine_hash=args.exit_policy_engine_hash,
        structure_rule_compiler_hash=args.structure_rule_compiler_hash,
        benchmark_compiler_hash=args.benchmark_compiler_hash,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
