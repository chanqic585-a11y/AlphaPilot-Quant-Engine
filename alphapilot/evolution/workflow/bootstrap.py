"""Bootstrap immutable workflow profiles and legacy research candidates."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.short_cycle.workflow_candidates import (
    evidence_redesigned_short_cycle_workflow_candidates,
    redesigned_short_cycle_workflow_candidates,
    short_cycle_workflow_candidates,
)
from alphapilot.short_cycle.event_window_candidates import (
    cross_timeframe_workflow_candidate_pool,
    research_eligible_event_window_workflow_candidates,
)
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

DAILY_BACKTEST_GATE_RULES = {
    **DEFAULT_BACKTEST_GATE_RULES,
    "schemaVersion": "workflow_backtest_gate_daily_v1",
    "minimumTradeCount": 12,
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


def ensure_daily_backtest_gate_profile(
    repository: WorkflowRepository,
) -> GateProfileRecord:
    """Keep every quality gate while acknowledging sparse completed daily bars."""

    rules = DAILY_BACKTEST_GATE_RULES
    return repository.create_gate_profile(
        GateProfileRecord(
            gateProfileId="gate_profile_backtest_daily_v1",
            profileKey="daily_backtest",
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


def register_short_cycle_candidate_pack(
    registry: RegistryRepository,
    workflow: WorkflowRepository,
) -> tuple[StrategyVersionRecord, ...]:
    """Register the immutable V13.27.3 candidates without starting work."""

    gate = ensure_default_backtest_gate_profile(workflow)
    versions: list[StrategyVersionRecord] = []
    for item in short_cycle_workflow_candidates():
        family = ensure_strategy_family(
            repository=registry,
            family_key=item.familyKey,
            name=item.displayName,
            metadata={
                "candidatePack": "V13.27.3",
                "direction": item.direction,
                "timeframe": item.timeframe,
            },
        )
        versions.append(
            register_strategy_version(
                workflow,
                strategy_family_id=family.strategyFamilyId,
                display_name=item.displayName,
                source_type="short_cycle_candidate_pack_v13_27_3",
                definition=item.definition(),
                parameters=item.parameters,
                initial_gate_profile_id=gate.gateProfileId,
            )
        )
    return tuple(versions)


def register_redesigned_short_cycle_candidate_pack(
    registry: RegistryRepository,
    workflow: WorkflowRepository,
) -> tuple[StrategyVersionRecord, ...]:
    """Register six evidence-informed V13.27.13 candidates without running them."""

    gate = ensure_default_backtest_gate_profile(workflow)
    versions: list[StrategyVersionRecord] = []
    for item in redesigned_short_cycle_workflow_candidates():
        family = ensure_strategy_family(
            repository=registry,
            family_key=item.familyKey,
            name=item.displayName,
            metadata={
                "candidatePack": "V13.27.13",
                "direction": item.direction,
                "timeframe": item.timeframe,
                "redesignReason": "prior_pack_structurally_weak",
            },
        )
        versions.append(
            register_strategy_version(
                workflow,
                strategy_family_id=family.strategyFamilyId,
                display_name=item.displayName,
                source_type="short_cycle_redesign_pack_v13_27_13",
                definition=item.definition(),
                parameters=item.parameters,
                initial_gate_profile_id=gate.gateProfileId,
            )
        )
    return tuple(versions)


def register_evidence_redesigned_short_cycle_candidate_pack(
    registry: RegistryRepository,
    workflow: WorkflowRepository,
) -> tuple[StrategyVersionRecord, ...]:
    """Register six event-driven successors learned from archived weak packs."""

    gate = ensure_default_backtest_gate_profile(workflow)
    versions: list[StrategyVersionRecord] = []
    for item in evidence_redesigned_short_cycle_workflow_candidates():
        family = ensure_strategy_family(
            repository=registry,
            family_key=item.familyKey,
            name=item.displayName,
            metadata={
                "candidatePack": "V13.27.15",
                "direction": item.direction,
                "timeframe": item.timeframe,
                "redesignReason": "archived_packs_overtraded_after_costs",
                "eventDrivenEntry": True,
            },
        )
        versions.append(
            register_strategy_version(
                workflow,
                strategy_family_id=family.strategyFamilyId,
                display_name=item.displayName,
                source_type="short_cycle_evidence_redesign_pack_v13_27_15",
                definition=item.definition(),
                parameters=item.parameters,
                initial_gate_profile_id=gate.gateProfileId,
            )
        )
    return tuple(versions)


def register_v13_27_17_event_window_candidate_pack(
    registry: RegistryRepository,
    workflow: WorkflowRepository,
) -> tuple[StrategyVersionRecord, ...]:
    """Register only direct-pre-screen eligible event-window candidates."""

    gate = ensure_default_backtest_gate_profile(workflow)
    versions: list[StrategyVersionRecord] = []
    for item in research_eligible_event_window_workflow_candidates():
        family = ensure_strategy_family(
            repository=registry,
            family_key=item.familyKey,
            name=item.displayName,
            metadata={
                "candidatePack": "V13.27.17",
                "direction": item.direction,
                "timeframe": item.timeframe,
                "directPrescreenEligible": True,
            },
        )
        versions.append(
            register_strategy_version(
                workflow,
                strategy_family_id=family.strategyFamilyId,
                display_name=item.displayName,
                source_type="event_window_research_eligible_pack_v13_27_17",
                definition=item.definition(),
                parameters=item.parameters,
                initial_gate_profile_id=gate.gateProfileId,
            )
        )
    return tuple(versions)


def register_v13_27_18_cross_timeframe_candidate_pack(
    registry: RegistryRepository,
    workflow: WorkflowRepository,
) -> tuple[StrategyVersionRecord, ...]:
    """Register five research-only definitions per supported timeframe."""

    default_gate = ensure_default_backtest_gate_profile(workflow)
    daily_gate = ensure_daily_backtest_gate_profile(workflow)
    versions: list[StrategyVersionRecord] = []
    for item in cross_timeframe_workflow_candidate_pool():
        metadata = dict(item.researchMetadata or {})
        family = ensure_strategy_family(
            repository=registry,
            family_key=item.familyKey,
            name=item.displayName,
            metadata={
                "candidatePack": "V13.27.18",
                "direction": item.direction,
                "timeframe": item.timeframe,
                "selectionTier": metadata.get("selectionTier"),
                "formalPromotionEvidence": False,
            },
        )
        gate = daily_gate if item.timeframe == "1d" else default_gate
        versions.append(
            register_strategy_version(
                workflow,
                strategy_family_id=family.strategyFamilyId,
                display_name=item.displayName,
                source_type="cross_timeframe_research_pack_v13_27_18",
                definition=item.definition(),
                parameters=item.parameters,
                initial_gate_profile_id=gate.gateProfileId,
            )
        )
    return tuple(versions)


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
