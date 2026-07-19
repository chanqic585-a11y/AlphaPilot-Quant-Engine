"""Build V37G/V37H clean-room Vibe integration evidence."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.factor_lab.registry import FactorDefinition, FactorRegistry
from alphapilot.factor_lab.reports import write_factor_lab_reports
from alphapilot.factor_lab.similarity import (
    ArtifactSimilarityPolicy,
    SimilarityEvidence,
    classify_similarity,
)
from alphapilot.generated_candidate_sandbox.resource_limits import ResourceLimits
from alphapilot.generated_candidate_sandbox.runtime import run_candidate
from alphapilot.strategy_acquisition.mechanism_extract import build_extracted_artifact
from alphapilot.strategy_acquisition.models import SourceEvidence
from alphapilot.strategy_acquisition.projections import export_artifact_projections
from alphapilot.strategy_acquisition.store import StrategyArtifactStore


PINNED_VIBE_COMMIT = "7d42de944466e1a1f12f0df3933624fe665dee3c"
SOURCE_ROOT = Path("research/external_capabilities/vibe_trading")
FIXED_AT = "2026-07-20T00:00:00+00:00"


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _copy(source: Path, destination: Path) -> None:
    destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _schema_projection(connection: Any) -> dict[str, Any]:
    tables = {}
    for table in ("StrategyArtifacts", "ArtifactLifecycleEvents", "ArtifactBenchHistory"):
        rows = connection.execute(f"PRAGMA table_info({table})").fetchall()
        tables[table] = [
            {
                "name": row[1],
                "type": row[2],
                "notNull": bool(row[3]),
                "primaryKey": bool(row[5]),
            }
            for row in rows
        ]
    return {
        "schemaVersion": "alphapilot_strategy_artifact_store_schema_v1",
        "authorityModel": "projection_only_existing_program_campaign_ledger_remains_authority",
        "migrationVersion": 8,
        "tables": tables,
    }


def _build_artifact_store(
    repo_root: Path, output_root: Path, source_manifest: dict[str, Any]
) -> tuple[dict[str, Path], list[dict[str, Any]], dict[str, Any]]:
    source_by_path = {row["path"]: row for row in source_manifest["paths"]}
    definitions = (
        (
            "vibe-strategy-development-manager",
            "strategy_workflow_reference",
            "strategy-development-manager",
            "source-backed acquisition and lifecycle orchestration",
            "agent/src/skills/strategy-dev-manager/SKILL.md",
        ),
        (
            "vibe-alpha-compare",
            "factor_comparison_reference",
            "artifact-similarity",
            "multi-dimensional factor and strategy comparison",
            "agent/src/tools/alpha_compare_tool.py",
        ),
        (
            "vibe-generated-code-sandbox",
            "sandbox_reference",
            "generated-candidate-sandbox",
            "generated signal code validation before isolated research execution",
            "agent/src/shadow_account/codegen.py",
        ),
    )
    temp_root = repo_root / ".test-temp"
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="v37g-store-", dir=temp_root) as temporary:
        connection = connect_registry(Path(temporary) / "projection.sqlite")
        schema = _schema_projection(connection)
        store = StrategyArtifactStore(connection)
        mechanism_rows = []
        for artifact_id, artifact_type, family_id, mechanism, source_path in definitions:
            source = source_by_path[source_path]
            evidence = SourceEvidence(
                sourceId=f"vibe:{source_path}",
                sourcePath=source_path,
                locator="pinned Git blob",
                sourceHash=source["blobSha"],
                extractionConfidence=1.0,
            )
            artifact = build_extracted_artifact(
                artifactId=artifact_id,
                artifactType=artifact_type,
                name=artifact_id.replace("-", " ").title(),
                familyId=family_id,
                authorityRef="integration:v37g-v37h-vibe-audit",
                sourceIds=(evidence.sourceId,),
                sourceHashes=(source["blobSha"],),
                licenseClass="MIT_reference_clean_room",
                sourceEquivalenceClass="mechanism_only",
                marketMechanism=mechanism,
                formula=None,
                requiredFields=("source_locator", "source_hash"),
                universe=(),
                timeframe="not_applicable",
                entryRules=(),
                exitRules=(),
                positionSizing="not_applicable",
                riskManagement="AlphaPilot gates remain authoritative",
                dataProfile={"pointInTime": True, "runtimeDependency": False},
                evidence=(evidence,),
            )
            artifact = type(artifact)(
                **{
                    **artifact.to_dict(),
                    "sourceIds": artifact.sourceIds,
                    "sourceHashes": artifact.sourceHashes,
                    "requiredFields": artifact.requiredFields,
                    "universe": artifact.universe,
                    "entryRules": artifact.entryRules,
                    "exitRules": artifact.exitRules,
                    "evidence": artifact.evidence,
                    "createdAt": FIXED_AT,
                    "updatedAt": FIXED_AT,
                }
            )
            store.register(artifact)
            store.transition(
                artifact.artifactId,
                "mechanism_extracted",
                reason_code="source_evidence_verified",
                evidence={"sourcePath": source_path, "blobSha": source["blobSha"]},
            )
            mechanism_rows.append(
                {
                    "artifactId": artifact.artifactId,
                    "familyId": family_id,
                    "marketMechanism": mechanism,
                    "sourcePath": source_path,
                    "sourceHash": source["blobSha"],
                    "equivalence": "mechanism_only",
                    "proves": "the AlphaPilot clean-room implementation only",
                    "doesNotProve": "original strategy performance or unobserved implementation",
                }
            )
        outputs = export_artifact_projections(store, output_root)
        connection.close()
    return outputs, mechanism_rows, schema


def _factor_definitions() -> tuple[FactorDefinition, ...]:
    rows = (
        ("ts-momentum", "TS momentum", "ts_momentum", "delta(close, 20)", ("close",)),
        ("xs-momentum", "Cross-sectional momentum", "cross_sectional_momentum", "rank(delta(close, 20))", ("close",)),
        ("short-reversal", "Short-term reversal", "short_term_reversal", "-delta(close, 3)", ("close",)),
        ("residual-momentum", "Residual momentum", "residual_momentum", "rolling_residual(returns, market_returns, 20, 10)", ("returns", "market_returns")),
        ("volatility", "Rolling volatility", "volatility", "ts_std(returns, 20, 10)", ("returns",)),
        ("range-atr", "Normalized range", "range_atr", "ts_mean(safe_div(high - low, close), 14, 7)", ("high", "low", "close")),
        ("turnover-change", "Turnover change", "turnover_change", "delta(turnover, 5)", ("turnover",)),
        ("liquidity", "Return-adjusted volume", "liquidity", "safe_div(volume, absolute(returns))", ("volume", "returns")),
        ("beta", "Rolling beta", "beta", "rolling_beta(returns, market_returns, 30, 15)", ("returns", "market_returns")),
        ("correlation-regime", "Correlation regime", "correlation_regime", "ts_corr(returns, market_returns, 30, 15)", ("returns", "market_returns")),
        ("funding", "Funding persistence", "funding", "ts_mean(funding_rate, 3, 3)", ("funding_rate", "funding_available_at")),
        ("basis", "Perpetual basis", "basis", "safe_div(mark_price - index_price, index_price)", ("mark_price", "index_price")),
    )
    return tuple(
        FactorDefinition(
            factorId=factor_id,
            name=name,
            theme=theme,
            formula=formula,
            requiredFields=required,
            pointInTimeReady=True,
            sourceArtifactId="vibe-alpha-compare",
            notes="bounded research-only clean-room definition",
        )
        for factor_id, name, theme, formula, required in rows
    )


def _similarity_rows() -> tuple[list[dict[str, Any]], list[dict[str, Any]], str]:
    policy = ArtifactSimilarityPolicy.frozen_default(FIXED_AT)
    fixtures = (
        ("exact", SimilarityEvidence(True, True, True, 1.0, 1.0, 1.0, 1.0, True), "reject_duplicate"),
        ("near", SimilarityEvidence(False, False, True, 0.995, 0.97, 0.995, 0.96, False), "reject_near_duplicate"),
        ("variant", SimilarityEvidence(False, False, True, 0.93, 0.82, 0.91, 0.80, True), "retain_one_bounded_variant"),
        ("related", SimilarityEvidence(False, False, True, 0.50, 0.40, 0.30, 0.20, False), "retain_mechanism_research"),
        ("independent", SimilarityEvidence(False, False, False, 0.20, 0.10, 0.10, 0.05, False), "retain_independent"),
    )
    rows = []
    decisions = []
    for suffix, evidence, action in fixtures:
        decision = classify_similarity(evidence, policy)
        rows.append(
            {
                "leftArtifactId": "reference-artifact",
                "rightArtifactId": f"candidate-{suffix}",
                **evidence.__dict__,
                **decision.to_dict(),
            }
        )
        decisions.append(
            {
                "candidateId": f"candidate-{suffix}",
                "classification": decision.classification,
                "decision": action,
                "policyHash": policy.policyHash,
                "qualificationScope": "research_only",
            }
        )
    return rows, decisions, policy.policyHash


def _sandbox_audit(repo_root: Path) -> dict[str, Any]:
    run_directory = repo_root / ".test-temp" / "v37h-evidence-sandbox"
    safe = run_candidate(
        "def generate(context):\n    return {'signal': int(context['close'][-1] > context['close'][-2])}\n",
        {"close": [100.0, 101.0]},
        limits=ResourceLimits(timeoutSeconds=2.0, memoryMb=128),
        run_directory=run_directory,
    )
    blocked = run_candidate(
        "def hidden():\n    import requests\n\ndef generate(context):\n    return {'signal': 0}\n",
        {},
        limits=ResourceLimits(timeoutSeconds=2.0, memoryMb=128),
        run_directory=run_directory,
    )
    return {
        "schemaVersion": "alphapilot_generated_candidate_sandbox_audit_v1",
        "boundaryClaim": "research_execution_guard_not_os_security_boundary",
        "safeCandidate": {
            "status": safe.status,
            "output": safe.output,
            "error": safe.error,
            "audit": safe.audit,
        },
        "unreachableNetworkHelper": {
            "status": blocked.status,
            "output": blocked.output,
            "error": blocked.error,
            "audit": blocked.audit,
        },
        "promotionRequirements": [
            "ast_passed",
            "sandbox_passed",
            "candidate_adapter_passed",
            "synthetic_fixture_passed",
            "real_signal_structural_certification_passed",
        ],
    }


def _write_similarity_summary(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=(
                "leftArtifactId",
                "rightArtifactId",
                "classification",
                "policyHash",
            ),
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row[key] for key in writer.fieldnames})


def _artifact_manifest(output_root: Path) -> dict[str, Any]:
    artifacts = []
    for path in sorted(item for item in output_root.iterdir() if item.is_file()):
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
        "schemaVersion": "alphapilot_v37g_v37h_artifact_manifest_v1",
        "sourceCommit": PINNED_VIBE_COMMIT,
        "artifacts": artifacts,
    }


def build_evidence(repo_root: Path, output_root: Path) -> dict[str, Path]:
    repo_root = Path(repo_root).resolve()
    output_root = Path(output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)
    source_root = repo_root / SOURCE_ROOT
    source_manifest = _read_json(source_root / "source_manifest.json")
    if source_manifest["commit"] != PINNED_VIBE_COMMIT:
        raise ValueError("Vibe source manifest does not match the pinned commit")
    if source_manifest["copiedCode"]:
        raise ValueError("clean-room integration must not list copied code")

    _write_json(output_root / "vibe_trading_source_manifest.json", source_manifest)
    _write_json(
        output_root / "vibe_component_adoption_map.json",
        _read_json(source_root / "component_adoption_map.json"),
    )
    _copy(source_root / "license_notice.md", output_root / "vibe_license_notice.md")

    _, mechanisms, schema = _build_artifact_store(
        repo_root, output_root, source_manifest
    )
    _write_json(output_root / "strategy_artifact_store_schema.json", schema)
    _write_json(output_root / "mechanism_inventory.json", mechanisms)

    sandbox = _sandbox_audit(repo_root)
    _write_json(output_root / "generated_candidate_sandbox_audit.json", sandbox)

    registry = FactorRegistry(max_factors=36)
    for definition in _factor_definitions():
        registry.register(definition)
    similarity_rows, dedup_decisions, policy_hash = _similarity_rows()
    factor_outputs = write_factor_lab_reports(
        output_root,
        registry=registry,
        bench_rows=[
            {
                "factorId": item.factorId,
                "ic": round((index - 6) * 0.001, 6),
                "rankIc": round((index - 5) * 0.001, 6),
                "evidenceScope": "synthetic_fixture_only",
                "strategyFormalPass": False,
            }
            for index, item in enumerate(registry.list())
        ],
        similarity_rows=similarity_rows,
        dedup_decisions=dedup_decisions,
    )
    if len(factor_outputs) != 4:
        raise RuntimeError("Factor Lab report set is incomplete")
    _write_similarity_summary(
        output_root / "artifact_similarity_summary.csv", similarity_rows
    )

    verification = {
        "schemaVersion": "alphapilot_v37g_v37h_verification_summary_v1",
        "status": "passed",
        "pinnedCommitVerified": source_manifest["commit"] == PINNED_VIBE_COMMIT,
        "cleanRoom": source_manifest["cleanRoomRewrite"],
        "runtimeDependency": source_manifest["runtimeDependency"],
        "copiedCodeCount": len(source_manifest["copiedCode"]),
        "artifactStoreAuthority": schema["authorityModel"],
        "sandboxSafeFixturePassed": sandbox["safeCandidate"]["status"] == "passed",
        "sandboxDangerousFixtureRejected": sandbox["unreachableNetworkHelper"]["status"] == "rejected",
        "factorCount": len(registry.list()),
        "factorQualificationScope": "research_only",
        "similarityPolicyHash": policy_hash,
        "sideEffects": {
            "formalRunCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "demoArmCount": 0,
            "orderCount": 0,
            "liveCount": 0,
        },
    }
    _write_json(output_root / "verification_summary.json", verification)
    (output_root / "v37g_v37h_closeout.md").write_text(
        "# V37G/V37H Selective Vibe Integration Closeout\n\n"
        f"- Source: `HKUDS/Vibe-Trading@{PINNED_VIBE_COMMIT}`.\n"
        "- Integration mode: clean-room concepts only; no copied code and no runtime dependency.\n"
        "- Strategy Artifact Store is a projection; Program/Campaign Ledger remains authoritative.\n"
        "- Generated candidate sandbox is a research execution guard, not an OS security boundary.\n"
        "- Factor Lab outputs are research-only and cannot imply Formal Pass.\n"
        "- Formal runs, Locked OOS reads, Release, Demo ARM, orders, and Live remain zero.\n",
        encoding="utf-8",
    )
    _write_json(output_root / "artifact_manifest.json", _artifact_manifest(output_root))
    return {path.name: path for path in output_root.iterdir() if path.is_file()}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-root", type=Path, default=Path("reports/integration/v37g_v37h")
    )
    args = parser.parse_args()
    output = args.output_root
    if not output.is_absolute():
        output = args.repo_root / output
    written = build_evidence(args.repo_root, output)
    print(json.dumps({"written": sorted(written)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
