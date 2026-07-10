"""Build complete, evidence-bound strategy candidates for shadow review only."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import StrategyCandidateRecord

from .family_registry import ensure_strategy_family


@dataclass(frozen=True)
class StrategyCandidateDraft:
    name: str
    familyKey: str
    direction: str
    marketDefinition: dict[str, Any]
    entryRules: list[str]
    exitRules: dict[str, Any]
    riskRules: dict[str, Any]
    evidence: dict[str, Any]


def _positive_number(value: Any, field_name: str) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be numeric") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"{field_name} must be finite and positive")
    return parsed


def _positive_integer(value: Any, field_name: str) -> int:
    parsed = _positive_number(value, field_name)
    if parsed != int(parsed):
        raise ValueError(f"{field_name} must be an integer")
    return int(parsed)


def _validate_registered_evidence(
    evidence: dict[str, Any], repository: RegistryRepository
) -> None:
    required = {
        "dataSnapshotId",
        "factorRunIds",
        "experimentIds",
        "walkForwardManifestHash",
        "formalGateStatus",
    }
    missing = sorted(required - set(evidence))
    if missing:
        raise ValueError(f"Candidate evidence is incomplete: {', '.join(missing)}")
    if evidence.get("formalGateStatus") != "passed":
        raise ValueError("Formal research gate must pass before candidate creation")
    if not str(evidence.get("walkForwardManifestHash")).startswith("walk_forward_"):
        raise ValueError("Candidate requires a purged walk-forward manifest hash")
    snapshot_id = str(evidence.get("dataSnapshotId"))
    if repository.get_data_snapshot(snapshot_id) is None:
        raise ValueError(f"Unregistered data snapshot: {snapshot_id}")
    factor_run_ids = evidence.get("factorRunIds")
    experiment_ids = evidence.get("experimentIds")
    if not isinstance(factor_run_ids, list) or not factor_run_ids:
        raise ValueError("Candidate requires registered factorRunIds")
    if not isinstance(experiment_ids, list) or not experiment_ids:
        raise ValueError("Candidate requires registered experimentIds")
    for run_id in factor_run_ids:
        run = repository.get_factor_run(str(run_id))
        if run is None or run.status not in {"completed", "research_validated"}:
            raise ValueError(f"FactorRun is missing or not validated: {run_id}")
        if run.dataSnapshotId != snapshot_id or not bool(run.payload.get("pointInTimeValidated")):
            raise ValueError(f"FactorRun evidence is not point-in-time aligned: {run_id}")
    for experiment_id in experiment_ids:
        experiment = repository.get_experiment(str(experiment_id))
        if experiment is None or experiment.status != "research_validated":
            raise ValueError(f"Experiment is missing or not research_validated: {experiment_id}")
        if experiment.dataSnapshotId not in {None, snapshot_id}:
            raise ValueError(f"Experiment uses a different data snapshot: {experiment_id}")


def build_strategy_candidate(
    draft: StrategyCandidateDraft,
    *,
    repository: RegistryRepository,
) -> StrategyCandidateRecord:
    if draft.direction not in {"long", "short", "both"}:
        raise ValueError("direction must be long, short, or both")
    market_required = {"exchange", "marketType", "timeframe", "universePolicy"}
    if market_required - set(draft.marketDefinition):
        raise ValueError("marketDefinition is incomplete")
    if not draft.entryRules or not all(
        isinstance(rule, str) and rule.startswith("factor_expression_") for rule in draft.entryRules
    ):
        raise ValueError("entryRules must reference validated factor expression ids")
    exit_required = {"stopLossR", "takeProfitR", "maxHoldingBars"}
    risk_required = {"riskPerTradePct", "maxLeverage", "maxConcurrentPositions"}
    if exit_required - set(draft.exitRules) or risk_required - set(draft.riskRules):
        raise ValueError("exitRules and riskRules must be complete")
    stop_loss_r = _positive_number(draft.exitRules.get("stopLossR"), "stopLossR")
    take_profit_r = _positive_number(draft.exitRules.get("takeProfitR"), "takeProfitR")
    if take_profit_r / stop_loss_r < 2.0:
        raise ValueError("Strategy candidate reward/risk ratio must be at least 2R")
    _positive_integer(draft.exitRules.get("maxHoldingBars"), "maxHoldingBars")
    risk_per_trade = _positive_number(draft.riskRules.get("riskPerTradePct"), "riskPerTradePct")
    leverage = _positive_integer(draft.riskRules.get("maxLeverage"), "maxLeverage")
    concurrent = _positive_integer(
        draft.riskRules.get("maxConcurrentPositions"), "maxConcurrentPositions"
    )
    if risk_per_trade > 1.0:
        raise ValueError("riskPerTradePct cannot exceed 1% in a research candidate")
    if not 1 <= leverage <= 5 or concurrent > 10:
        raise ValueError("Research candidate leverage or concurrency exceeds the safety envelope")
    _validate_registered_evidence(draft.evidence, repository)
    family = ensure_strategy_family(
        repository=repository,
        family_key=draft.familyKey,
        name=draft.name,
        metadata={"direction": draft.direction, "marketDefinition": draft.marketDefinition},
    )
    candidate_payload = {
        "schemaVersion": "strategy_candidate_contract_v1",
        "name": draft.name,
        "familyKey": family.familyKey,
        "direction": draft.direction,
        "marketDefinition": draft.marketDefinition,
        "entryRules": sorted(set(draft.entryRules)),
        "exitRules": draft.exitRules,
        "riskRules": draft.riskRules,
        "evidence": draft.evidence,
        "rewardRiskRatio": take_profit_r / stop_loss_r,
        "executionEnabled": False,
        "demoPromotionAllowed": False,
        "livePromotionAllowed": False,
        "createsOrders": False,
    }
    content_hash = stable_hash(candidate_payload)
    return repository.create_strategy_candidate(
        StrategyCandidateRecord(
            strategyCandidateId=stable_hash(candidate_payload, prefix="strategy_candidate"),
            strategyFamilyId=family.strategyFamilyId,
            name=draft.name,
            status="shadow_candidate",
            candidate=candidate_payload,
            contentHash=content_hash,
        )
    )
