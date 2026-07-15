"""Write machine-readable V2 gate migration and causality policies."""

from __future__ import annotations

import json
from pathlib import Path

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.research_screening.gate_schema import (
    EXECUTION_FACT_FIELDS,
    PUBLIC_GATE_FIELDS,
)
from alphapilot.research_screening.translation_parity import (
    IDENTITY_FIELDS,
    NUMERIC_FIELDS,
)


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _with_hash(payload: dict[str, object], *, prefix: str, field: str) -> dict[str, object]:
    return {**payload, field: stable_hash(payload, prefix=prefix)}


def write_methodology_reports(output_dir: Path) -> dict[str, Path]:
    gate_core: dict[str, object] = {
        "schemaVersion": "gate_migration_report_v2",
        "status": "active",
        "deprecatedFields": [
            "basePassed",
            "formalPassed",
            "oosMetrics",
            "fullBacktestExecuted",
        ],
        "replacementFields": list(PUBLIC_GATE_FIELDS),
        "executionFactFields": list(EXECUTION_FACT_FIELDS),
        "eventGateModule": "alphapilot.research_screening.event_strategy_gates",
        "portfolioGateModule": "alphapilot.research_screening.portfolio_strategy_gates",
        "compatibilityPolicy": "historical artifacts remain readable but cannot claim V2 formal status",
    }
    gate = {**gate_core, "reportHash": stable_hash(gate_core, prefix="gate_migration")}

    causality_core: dict[str, object] = {
        "schemaVersion": "causality_policy_v2",
        "availableAtRule": "availableAt <= signalDecisionTime",
        "nextBarExecution": True,
        "fundingPolicy": "settled_after_publication; predicted_requires_contemporaneous_public_proof",
        "openInterestPolicy": "delay_one_source_period_when_publication_latency_is_unproven",
        "pitUniversePolicy": "completed_source_bar_only",
        "purgePolicy": "at_least_maximum_holding_horizon",
        "embargoPolicy": "frozen_in_preregistration",
        "boundaryCrossingEvents": "drop_not_truncate",
        "requiredObservationTimestamps": [
            "eventTimestamp",
            "observedAt",
            "publishedAt",
            "availableAt",
            "sourceTimestamp",
            "ageSeconds",
            "publicationLagSeconds",
        ],
    }
    causality = {
        **causality_core,
        "policyHash": stable_hash(causality_core, prefix="causality_policy"),
    }
    parity_core: dict[str, object] = {
        "schemaVersion": "translation_parity_policy_v2",
        "identityFields": list(IDENTITY_FIELDS),
        "numericFields": list(NUMERIC_FIELDS),
        "identityMatchRequired": 1.0,
        "minimumNumericMatchRate": 0.99,
        "outsideTolerancePolicy": "every_remainder_requires_explicit_explanation",
    }
    benchmark_core: dict[str, object] = {
        "schemaVersion": "benchmark_registry_v2",
        "eventBaselineMatching": {
            "sameSymbols": True,
            "sameMonths": True,
            "sameEventCount": True,
            "sameHoldingHorizon": True,
            "sameExitGeometry": True,
            "sameCostScenario": True,
        },
        "portfolioMomentumBaseline": {
            "lookbackDays": 20,
            "samePitUniverse": True,
            "sameRebalanceSchedule": True,
            "sameGrossExposure": True,
            "sameBetaPolicy": True,
            "sameCosts": True,
        },
    }
    bootstrap_core: dict[str, object] = {
        "schemaVersion": "cluster_bootstrap_policy_v2",
        "minimumDraws": 5000,
        "clusterKeys": ["symbol", "eventMonth"],
        "confidenceLevels": [0.80, 0.90, 0.95],
        "formalEventBounds": ["profitFactorLower90", "averageNetRLower90"],
        "seedPolicy": "frozen_in_preregistration",
    }
    holdout_core: dict[str, object] = {
        "schemaVersion": "clean_holdout_policy_v2",
        "allowedAccessTransition": "0_to_1_once",
        "recommendedResearchSymbolShare": 0.70,
        "recommendedHoldoutSymbolShare": 0.30,
        "failedCampaignAction": "close_permanently",
        "technicalReplay": "pre_metric_incident_and_byte_identical_frozen_hashes_only",
        "requiredFrozenHashes": [
            "codeCommit",
            "dataSnapshotHash",
            "preregistrationHash",
            "strategyDefinitionHash",
            "exitModelHash",
            "benchmarkHash",
            "riskCapitalHash",
            "environmentManifestHash",
        ],
    }
    exit_core: dict[str, object] = {
        "schemaVersion": "exit_geometry_schema_v2",
        "initialStopMayWiden": False,
        "positionSizing": "risk_amount_divided_by_initial_stop_distance",
        "optionalPartialAtR": 1.0,
        "eventRemainingTargetMinimumR": 2.0,
        "portfolioPerSymbolRTarget": None,
    }
    parity = _with_hash(
        parity_core, prefix="translation_parity_policy", field="policyHash"
    )
    holdout = _with_hash(holdout_core, prefix="holdout_policy", field="policyHash")
    parity_path = _write(output_dir / "translation_parity_policy.json", parity)
    holdout_path = _write(output_dir / "holdout_policy.json", holdout)
    _write(output_dir / "translation_parity_report.json", parity)
    _write(output_dir / "holdout_unlock_policy.json", holdout)
    return {
        "gateMigration": _write(output_dir / "gate_migration_report.json", gate),
        "causalityPolicy": _write(output_dir / "causality_policy.json", causality),
        "translationParity": parity_path,
        "benchmarkRegistry": _write(
            output_dir / "benchmark_registry.json",
            _with_hash(benchmark_core, prefix="benchmark_registry", field="registryHash"),
        ),
        "bootstrapPolicy": _write(
            output_dir / "bootstrap_policy.json",
            _with_hash(bootstrap_core, prefix="bootstrap_policy", field="policyHash"),
        ),
        "holdoutPolicy": holdout_path,
        "exitGeometry": _write(
            output_dir / "exit_geometry_schema.json",
            _with_hash(exit_core, prefix="exit_geometry", field="schemaHash"),
        ),
    }


def main() -> int:
    write_methodology_reports(Path("reports/research_factory_repair"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
