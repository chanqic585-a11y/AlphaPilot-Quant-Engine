"""Bootstrap immutable workflow profiles and legacy research candidates."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.strategies.family_registry import ensure_strategy_family

from .repository import WorkflowRepository
from .service import register_strategy_version
from .states import WorkflowConflict
from .types import GateProfileRecord, StrategyVersionRecord


DEFAULT_BACKTEST_GATE_RULES = {
    "schemaVersion": "workflow_backtest_gate_v1",
    "minimumTargetR": 2.0,
    "minimumTradeCount": 30,
    "minimumProfitFactor": 1.1,
    "minimumAverageNetR": 0.0,
    "maximumDrawdownR": 20.0,
    "requiresRegisteredDataSnapshot": True,
    "requiresPointInTimeValidation": True,
    "requiresPurgedWalkForward": True,
    "requiresLockedOos": True,
    "requiresCostStress": True,
    "requiresStability": True,
}


def ensure_default_backtest_gate_profile(
    repository: WorkflowRepository,
) -> GateProfileRecord:
    rules = DEFAULT_BACKTEST_GATE_RULES
    return repository.create_gate_profile(
        GateProfileRecord(
            gateProfileId="gate_profile_backtest_default_v1",
            profileKey="default_backtest",
            version=1,
            stage="backtest",
            status="active",
            rules=rules,
            contentHash=stable_hash(rules),
        )
    )


def register_alpha191_observer(
    registry: RegistryRepository,
    workflow: WorkflowRepository,
) -> StrategyVersionRecord:
    """Register the legacy Alpha191 observer without inventing formal lineage."""

    family = ensure_strategy_family(
        repository=registry,
        family_key="alpha191_crypto_observer",
        name="Alpha191 加密因子观察策略",
        metadata={
            "sourceReport": "reports/v13_5_23_alpha191_crypto_subset_replay_report.json",
            "legacyResearchOnly": True,
        },
    )
    gate = ensure_default_backtest_gate_profile(workflow)
    definition = {
        "schemaVersion": "strategy_workflow_definition_v1",
        "direction": "both",
        "market": "crypto_usdt_swap",
        "timeframe": "4h",
        "targetR": 2.0,
        "researchOnly": True,
        "backtest": {
            "adapterId": "alpha191_crypto_subset_v13_5_23",
            "dataSnapshotId": None,
            "walkForwardManifestHash": None,
            "lockedOosManifestHash": None,
            "costModel": {"feeRate": 0.0005, "slippageRate": 0.0002},
            "sourceReport": "reports/v13_5_23_alpha191_crypto_subset_replay_report.json",
        },
    }
    parameters = {
        "overlayId": "a191_short_exhaustion_quality_v01",
        "stopLossPct": 0.06,
        "horizonBars": 24,
        "targetRMultiple": 2.0,
    }
    return register_strategy_version(
        workflow,
        strategy_family_id=family.strategyFamilyId,
        display_name="Alpha191 加密因子观察策略",
        source_type="legacy_research_import",
        definition=definition,
        parameters=parameters,
        initial_gate_profile_id=gate.gateProfileId,
    )


def register_optimized_legacy_strategy(
    registry: RegistryRepository,
    workflow: WorkflowRepository,
    *,
    legacy_strategy_id: str,
    display_name: str,
    definition: dict[str, Any],
    base_parameters: dict[str, Any],
    parameters: dict[str, Any],
    source_type: str = "legacy_stage_optimization",
) -> StrategyVersionRecord:
    """Import a changed legacy strategy as a canonical backtest version."""

    legacy_id = str(legacy_strategy_id or "").strip()
    if not legacy_id:
        raise WorkflowConflict("legacy_strategy_id_required")
    if stable_hash(base_parameters) == stable_hash(parameters):
        raise WorkflowConflict("optimized_parameters_unchanged")

    target_values: list[float] = []
    for container in (definition, parameters):
        for key in ("targetR", "targetRMultiple", "targetRewardRiskRatio"):
            if key not in container:
                continue
            try:
                target_values.append(float(container[key]))
            except (TypeError, ValueError) as error:
                raise WorkflowConflict("target_r_must_be_numeric") from error
    if not target_values:
        raise WorkflowConflict("target_r_required")
    if min(target_values) < 2.0:
        raise WorkflowConflict("minimum_target_r_is_2")

    family_digest = stable_hash({"legacyStrategyId": legacy_id})[:24]
    family = ensure_strategy_family(
        repository=registry,
        family_key=f"legacy_optimized_{family_digest}",
        name=display_name,
        metadata={
            "legacyStrategyId": legacy_id,
            "optimizationImport": True,
        },
    )
    gate = ensure_default_backtest_gate_profile(workflow)
    enriched_definition = {
        **definition,
        "researchOnly": True,
        "optimizationLineage": {
            "legacyStrategyId": legacy_id,
            "baseParameterHash": stable_hash(base_parameters),
            "optimizedParameterHash": stable_hash(parameters),
        },
    }
    return register_strategy_version(
        workflow,
        strategy_family_id=family.strategyFamilyId,
        display_name=display_name,
        source_type=source_type,
        definition=enriched_definition,
        parameters=parameters,
        initial_gate_profile_id=gate.gateProfileId,
    )
