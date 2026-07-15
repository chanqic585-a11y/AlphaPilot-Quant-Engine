"""Write machine-readable V2 gate migration and causality policies."""

from __future__ import annotations

import json
from pathlib import Path

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.research_screening.gate_schema import (
    EXECUTION_FACT_FIELDS,
    PUBLIC_GATE_FIELDS,
)


def _write(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


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
    return {
        "gateMigration": _write(output_dir / "gate_migration_report.json", gate),
        "causalityPolicy": _write(output_dir / "causality_policy.json", causality),
    }


def main() -> int:
    write_methodology_reports(Path("reports/research_factory_repair"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
