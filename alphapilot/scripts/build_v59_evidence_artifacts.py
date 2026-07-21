"""Build versioned V59 adaptive-learning evidence without promotion side effects."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sqlite3
import subprocess
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.adaptive_learning.v59_evidence_artifacts import (
    build_alpha191_compatibility_audit,
    build_model_validation_report,
    build_qlib_preflight_audit,
    build_training_dataset_manifest,
    run_shadow_inference_engineering_audit,
)
from alphapilot.evolution.registry.hashing import stable_hash


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def _read_latest_model(registry_db: Path) -> dict[str, Any]:
    if not registry_db.is_file():
        raise FileNotFoundError(registry_db)
    connection = sqlite3.connect(f"file:{registry_db.as_posix()}?mode=ro", uri=True)
    try:
        row = connection.execute(
            """
            SELECT modelId, status, payloadJson
            FROM Models
            ORDER BY createdAt DESC, modelId DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ValueError("V59 registry contains no model records")
    payload = json.loads(row[2])
    artifact = dict(payload.get("artifact") or {})
    if not artifact:
        raise ValueError(f"Model {row[0]} has no artifact payload")
    return {"modelId": row[0], "status": row[1], "artifact": artifact}


def _load_feature_rows(
    *, matrix_path: Path, feature_names: Sequence[str], row_limit: int
) -> list[list[float]]:
    frame = pd.read_parquet(matrix_path, columns=list(feature_names))
    frame = frame.replace([math.inf, -math.inf], float("nan")).dropna()
    if frame.empty:
        raise ValueError("Formal factor matrix has no finite model input rows")
    return frame.head(row_limit).astype(float).values.tolist()


def _explicit_evidence(
    *,
    schema_version: str,
    status: str,
    passed: bool | None,
    reason: str,
    evidence_ref: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    core = {
        "schemaVersion": schema_version,
        "status": status,
        "passed": passed,
        "reason": reason,
        "evidenceRef": evidence_ref,
        "details": details or {},
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {
        **core,
        "evidenceHash": stable_hash(core, prefix=schema_version),
    }


def _docker_daemon_available() -> bool:
    try:
        result = subprocess.run(
            ["docker", "info", "--format", "{{.ServerVersion}}"],
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production-registry", type=Path, required=True)
    parser.add_argument("--numeric-crossvalidation", type=Path, required=True)
    parser.add_argument("--formal-campaign", type=Path, required=True)
    parser.add_argument("--registry-audit", type=Path, required=True)
    parser.add_argument("--registry-db", type=Path, required=True)
    parser.add_argument("--matrix-path", type=Path, required=True)
    parser.add_argument("--qlib-readiness-gate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--demo-learning-samples", type=int, default=0)
    parser.add_argument("--live-learning-samples", type=int, default=0)
    parser.add_argument("--generated-at")
    parser.add_argument("--row-limit", type=int, default=512)
    args = parser.parse_args(argv)

    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    generated_at = args.generated_at or datetime.now(UTC).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    campaign = _load_json(args.formal_campaign.expanduser().resolve())
    registry_audit = _load_json(args.registry_audit.expanduser().resolve())
    alpha191 = build_alpha191_compatibility_audit(
        production_registry=_load_json(args.production_registry.expanduser().resolve()),
        numeric_crossvalidation=_load_json(
            args.numeric_crossvalidation.expanduser().resolve()
        ),
    )
    model_validation = build_model_validation_report(
        campaign=campaign,
        registry_audit=registry_audit,
    )
    matrix_path = args.matrix_path.expanduser().resolve()
    training_manifest = build_training_dataset_manifest(
        campaign=campaign,
        matrix_path=matrix_path,
        demo_learning_sample_count=args.demo_learning_samples,
        live_learning_sample_count=args.live_learning_samples,
    )
    model = _read_latest_model(args.registry_db.expanduser().resolve())
    artifact = model["artifact"]
    rows = _load_feature_rows(
        matrix_path=matrix_path,
        feature_names=artifact["featureNames"],
        row_limit=args.row_limit,
    )
    shadow_audit = run_shadow_inference_engineering_audit(
        model_artifact=artifact,
        feature_rows=rows,
        iterations=5,
    )
    qlib_preflight = build_qlib_preflight_audit(
        readiness_gate=_load_json(args.qlib_readiness_gate.expanduser().resolve()),
        qlib_package_available=importlib.util.find_spec("qlib") is not None,
        docker_daemon_available=_docker_daemon_available(),
    )

    artifacts: dict[str, dict[str, Any]] = {
        "alpha191_compatibility_audit.json": alpha191,
        "model_validation_report.json": model_validation,
        "training_dataset_manifest.json": training_manifest,
        "shadow_model_engineering_audit.json": shadow_audit,
        "alpha101_compatibility_audit.json": _explicit_evidence(
            schema_version="alpha101_crypto_compatibility_audit_v1",
            status="not_run",
            passed=None,
            reason="formal_crypto_validation_not_run",
        ),
        "qlib_campaign_manifest.json": qlib_preflight,
        "demo_learning_sample_audit.json": _explicit_evidence(
            schema_version="v59_demo_learning_sample_audit_v1",
            status="blocked",
            passed=False,
            reason="no_reconciled_closed_demo_strategy_outcomes",
            details={
                "eligibleSampleCount": args.demo_learning_samples,
                "engineeringSmokeExcluded": True,
            },
        ),
        "demo_decision_mode_validation.json": _explicit_evidence(
            schema_version="v59_demo_decision_mode_validation_v1",
            status="not_run",
            passed=None,
            reason="observer_only_no_decision_participation",
        ),
        "model_drift_report.json": _explicit_evidence(
            schema_version="v59_model_drift_report_v1",
            status="not_run",
            passed=None,
            reason="no_live_eligible_champion_model",
        ),
        "model_rollback_audit.json": _explicit_evidence(
            schema_version="v59_model_rollback_audit_v1",
            status="not_run",
            passed=None,
            reason="no_champion_predecessor_pair",
        ),
        "live_feature_pipeline_parity.json": _explicit_evidence(
            schema_version="v59_live_feature_pipeline_parity_v1",
            status="blocked",
            passed=False,
            reason="no_live_runtime_feature_replay",
            details={"environmentNeutralFeatureHashImplemented": True},
        ),
        "live_model_inference_audit.json": _explicit_evidence(
            schema_version="v59_live_model_inference_audit_v1",
            status="blocked",
            passed=False,
            reason="research_only_model_not_live_eligible",
            evidence_ref=shadow_audit["evidenceHash"],
            details={"engineeringChecksPassed": shadow_audit["engineeringChecksPassed"]},
        ),
        "exact_model_release_approval.json": _explicit_evidence(
            schema_version="v59_exact_model_release_approval_v1",
            status="not_run",
            passed=None,
            reason="no_live_eligible_model_release_exists",
        ),
        "online_inference_latency_audit.json": _explicit_evidence(
            schema_version="v59_online_inference_latency_audit_v1",
            status="completed" if shadow_audit["engineeringChecksPassed"] else "blocked",
            passed=bool(shadow_audit["engineeringChecksPassed"]),
            reason="research_model_latency_measurement_only",
            evidence_ref=shadow_audit["evidenceHash"],
            details={
                "modelHash": artifact["modelHash"],
                "latencyMs": shadow_audit["latencyMs"],
                "rowCount": shadow_audit["rowCount"],
            },
        ),
    }
    for filename, payload in artifacts.items():
        payload.setdefault("generatedAt", generated_at)
        _write_json_atomic(output_dir / filename, payload)

    factor_mining = pd.DataFrame(
        [
            {
                "status": "completed",
                "passed": True,
                "experimentCount": len(campaign.get("experiments") or []),
                "formalPromotionEligible": bool(campaign.get("formalPromotionEligible")),
                "campaignStatus": campaign.get("status"),
                "campaignReportId": campaign.get("reportId"),
                "grantsLiveAuthority": False,
                "createsOrders": False,
            }
        ]
    )
    factor_mining.to_parquet(output_dir / "factor_mining_trial_ledger.parquet", index=False)
    shadow_ledger = pd.DataFrame(
        [
            {
                "status": "completed",
                "passed": bool(shadow_audit["engineeringChecksPassed"]),
                "modelHash": artifact["modelHash"],
                "decisionMode": "observer",
                "rowCount": shadow_audit["rowCount"],
                "deterministic": shadow_audit["deterministic"],
                "changesOrders": False,
                "grantsLiveAuthority": False,
            }
        ]
    )
    shadow_ledger.to_parquet(output_dir / "demo_shadow_decision_ledger.parquet", index=False)

    summary_core = {
        "schemaVersion": "v59_evidence_artifact_summary_v1",
        "generatedAt": generated_at,
        "status": "completed_with_blockers",
        "modelId": model["modelId"],
        "modelHash": artifact["modelHash"],
        "campaignStatus": campaign.get("status"),
        "formalPromotionEligible": bool(campaign.get("formalPromotionEligible")),
        "candidateCount": len(campaign.get("strategyCandidates") or []),
        "liveEligibleModelCount": int(registry_audit.get("liveEligibleModelCount") or 0),
        "demoLearningSampleCount": args.demo_learning_samples,
        "liveLearningSampleCount": args.live_learning_samples,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    summary = {
        **summary_core,
        "summaryHash": stable_hash(summary_core, prefix="v59_evidence_summary"),
    }
    _write_json_atomic(output_dir / "evidence_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
