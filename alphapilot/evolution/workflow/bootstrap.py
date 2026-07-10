"""Bootstrap immutable workflow profiles and legacy research candidates."""

from __future__ import annotations

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.strategies.family_registry import ensure_strategy_family

from .repository import WorkflowRepository
from .service import register_strategy_version
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
