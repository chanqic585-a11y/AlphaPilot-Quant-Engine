"""Derive immutable market-data requirements from strategy logic."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash

from .repository import WorkflowRepository
from .states import WorkflowConflict
from .types import StrategyDataContractRecord, StrategyVersionRecord


DATA_CONTRACT_SCHEMA_VERSION = "strategy_data_contract_v1"
SUPPORTED_TIMEFRAME_PLANS: dict[str, dict[str, str | None]] = {
    "5m": {"signal": "5m", "execution": "5m", "fallback": None},
    "15m": {"signal": "15m", "execution": "5m", "fallback": None},
    "1h": {"signal": "1h", "execution": "5m", "fallback": "15m"},
    "4h": {"signal": "4h", "execution": "5m", "fallback": "15m"},
}


def timeframe_plan(primary_timeframe: str) -> dict[str, str | None]:
    normalized = str(primary_timeframe or "").strip().lower()
    plan = SUPPORTED_TIMEFRAME_PLANS.get(normalized)
    if plan is None:
        raise ValueError(f"unsupported_strategy_timeframe:{normalized or 'missing'}")
    return dict(plan)


def _strategy_content_hash(version: StrategyVersionRecord) -> str:
    return stable_hash(
        {
            "strategyFamilyId": version.strategyFamilyId,
            "definition": version.definition,
            "parameters": version.parameters,
            "modelArtifactId": version.modelArtifactId,
        }
    )


def _market_type(definition: dict[str, Any]) -> str:
    value = str(definition.get("market") or definition.get("marketType") or "")
    normalized = value.strip().lower()
    if normalized in {"swap", "usdt_swap", "crypto_usdt_swap"}:
        return "swap"
    raise ValueError(f"unsupported_strategy_market:{normalized or 'missing'}")


def _target_r(version: StrategyVersionRecord) -> float:
    value = version.definition.get(
        "targetR", version.parameters.get("targetRMultiple", 0.0)
    )
    try:
        target_r = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("target_r_invalid") from error
    if target_r < 2.0:
        raise ValueError("target_r_below_2")
    return target_r


def _cost_policy(definition: dict[str, Any]) -> dict[str, Any]:
    backtest = definition.get("backtest")
    backtest_config = backtest if isinstance(backtest, dict) else {}
    source_costs = backtest_config.get("costModel")
    costs = source_costs if isinstance(source_costs, dict) else {}
    return {
        "feeRate": float(costs.get("feeRate", 0.0005)),
        "slippageRate": float(costs.get("slippageRate", 0.0002)),
        "fundingRequiredForSwap": True,
        "latencyBars": [0, 1, 2],
        "stressMultipliers": [1.0, 1.5, 2.0],
    }


def derive_strategy_data_contract(
    version: StrategyVersionRecord,
    repository: WorkflowRepository,
) -> StrategyDataContractRecord:
    registered = repository.get_strategy_version(version.strategyVersionId)
    expected_hash = _strategy_content_hash(version)
    if (
        registered is None
        or registered.contentHash != version.contentHash
        or expected_hash != version.contentHash
    ):
        raise WorkflowConflict(
            f"strategy_content_hash_mismatch:{version.strategyVersionId}"
        )

    definition = version.definition
    plan = timeframe_plan(str(definition.get("timeframe") or ""))
    target_r = _target_r(version)
    direction = str(definition.get("direction") or "").strip().lower()
    if direction not in {"long", "short", "both"}:
        raise ValueError(f"unsupported_strategy_direction:{direction or 'missing'}")

    contract = {
        "schemaVersion": DATA_CONTRACT_SCHEMA_VERSION,
        "strategyVersionId": version.strategyVersionId,
        "strategyContentHash": version.contentHash,
        "marketType": _market_type(definition),
        "direction": direction,
        "signalTimeframe": plan["signal"],
        "executionTimeframe": plan["execution"],
        "executionFallbackTimeframe": plan["fallback"],
        "requestedStart": "2020-01-01T00:00:00+00:00",
        "requestedEndPolicy": "latest_completed_at_run",
        "targetR": target_r,
        "requiredDataKinds": ["ohlcv", "funding", "instrument_metadata"],
        "universePolicy": {
            "type": "point_in_time_dynamic_liquid_usdt_swap",
            "minimumMembers": 20,
            "targetMembers": 50,
            "candidateDiscovery": ["local_catalog", "okx_public_instruments"],
        },
        "validationPolicy": {
            "purgedWalkForward": True,
            "unseenSymbolHoldout": True,
            "lockedOos": True,
            "regimeCoverage": [
                "bull",
                "bear",
                "range",
                "crash",
                "volatility_expansion",
            ],
            "sameBarAmbiguity": "stop_first",
        },
        "costPolicy": _cost_policy(definition),
    }
    content_hash = stable_hash(contract, prefix="strategy_data_contract")
    return repository.create_strategy_data_contract(
        StrategyDataContractRecord(
            strategyDataContractId=content_hash,
            strategyVersionId=version.strategyVersionId,
            schemaVersion=DATA_CONTRACT_SCHEMA_VERSION,
            contract=contract,
            contentHash=content_hash,
        )
    )
