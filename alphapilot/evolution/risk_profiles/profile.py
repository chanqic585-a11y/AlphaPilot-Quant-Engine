"""Immutable, bounded risk profiles for every AlphaPilot execution environment."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import RiskProfileActivationRecord, RiskProfileRecord


ENVIRONMENTS = {"local_forward", "okx_demo", "live_canary", "live_standard"}


@dataclass(frozen=True)
class RiskProfileSpec:
    profileKey: str
    version: int
    environment: str
    name: str
    capitalLimitUsdt: float = 1000.0
    maxActiveStrategies: int = 1
    maxConcurrentPositions: int = 1
    maxPositionsPerStrategy: int = 1
    maxPositionsPerSymbol: int = 1
    maxOrderNotionalUsdt: float = 100.0
    maxLeverage: int = 1
    marginMode: str = "isolated"
    riskPerTradePercent: float = 0.25
    maxOpenRiskPercent: float = 1.0
    maxStrategyOpenRiskPercent: float = 1.0
    maxSymbolOpenRiskPercent: float = 0.5
    maxDirectionOpenRiskPercent: float = 1.0
    maxCorrelatedOpenRiskPercent: float = 1.0
    dailyLossStopPercent: float = 1.0
    maxDrawdownStopPercent: float = 2.5
    canaryLossStopUsdt: float = 25.0
    cooldownAfterLossMinutes: int = 60
    rewardRiskRatio: float = 2.0
    feeRate: float = 0.0005
    slippageRate: float = 0.0002
    allowNewEntries: bool = True
    allowedStrategyIds: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schemaVersion"] = "risk_profile_v1"
        payload["allowedStrategyIds"] = list(self.allowedStrategyIds)
        return payload


def safety_envelope(environment: str) -> dict[str, Any]:
    normalized = str(environment or "").strip()
    if normalized not in ENVIRONMENTS:
        raise ValueError(f"Unsupported risk-profile environment: {normalized}")
    live = normalized.startswith("live_")
    return {
        "schemaVersion": "risk_safety_envelope_v1",
        "environment": normalized,
        "maxCapitalLimitUsdt": 100000.0,
        "maxActiveStrategies": 10 if live else 20,
        "maxConcurrentPositions": 20 if live else 50,
        "maxOrderNotionalToCapitalRatio": 1.0,
        "maxLeverage": 5,
        "maxRiskPerTradePercent": 1.0 if live else 2.0,
        "maxOpenRiskPercent": 5.0 if live else 10.0,
        "maxDailyLossStopPercent": 5.0 if live else 10.0,
        "maxDrawdownStopPercent": 15.0 if live else 25.0,
        "minimumRewardRiskRatio": 2.0,
        "allowedMarginModes": ["isolated"],
        "routineUiCanChangeEnvelope": False,
    }


def _positive_finite(profile: RiskProfileSpec, names: tuple[str, ...]) -> None:
    for name in names:
        value = float(getattr(profile, name))
        if not math.isfinite(value) or value <= 0:
            raise ValueError(f"Risk profile field must be finite and positive: {name}")


def validate_profile(
    profile: RiskProfileSpec,
    envelope: dict[str, Any] | None = None,
) -> None:
    limits = dict(envelope or safety_envelope(profile.environment))
    if not profile.profileKey.strip() or not profile.name.strip() or profile.version <= 0:
        raise ValueError("Risk profile identity, name, and positive version are required")
    if profile.environment not in ENVIRONMENTS:
        raise ValueError("Risk profile environment is unsupported")
    _positive_finite(
        profile,
        (
            "capitalLimitUsdt",
            "maxActiveStrategies",
            "maxConcurrentPositions",
            "maxPositionsPerStrategy",
            "maxPositionsPerSymbol",
            "maxOrderNotionalUsdt",
            "maxLeverage",
            "riskPerTradePercent",
            "maxOpenRiskPercent",
            "maxStrategyOpenRiskPercent",
            "maxSymbolOpenRiskPercent",
            "maxDirectionOpenRiskPercent",
            "maxCorrelatedOpenRiskPercent",
            "dailyLossStopPercent",
            "maxDrawdownStopPercent",
            "canaryLossStopUsdt",
            "rewardRiskRatio",
        ),
    )
    if profile.cooldownAfterLossMinutes < 0:
        raise ValueError("Risk profile cooldown cannot be negative")
    if profile.feeRate < 0 or profile.slippageRate < 0:
        raise ValueError("Risk profile costs cannot be negative")
    if profile.marginMode not in set(limits["allowedMarginModes"]):
        raise ValueError("Risk profile margin mode exceeds the reviewed SafetyEnvelope")
    bounded = {
        "capitalLimitUsdt": "maxCapitalLimitUsdt",
        "maxActiveStrategies": "maxActiveStrategies",
        "maxConcurrentPositions": "maxConcurrentPositions",
        "maxLeverage": "maxLeverage",
        "riskPerTradePercent": "maxRiskPerTradePercent",
        "maxOpenRiskPercent": "maxOpenRiskPercent",
        "dailyLossStopPercent": "maxDailyLossStopPercent",
        "maxDrawdownStopPercent": "maxDrawdownStopPercent",
    }
    for field_name, limit_name in bounded.items():
        if float(getattr(profile, field_name)) > float(limits[limit_name]):
            raise ValueError(f"Risk profile exceeds SafetyEnvelope: {field_name}")
    if profile.maxOrderNotionalUsdt > profile.capitalLimitUsdt * float(
        limits["maxOrderNotionalToCapitalRatio"]
    ):
        raise ValueError("Order notional exceeds the reviewed capital ratio")
    if profile.maxPositionsPerStrategy > profile.maxConcurrentPositions:
        raise ValueError("Per-strategy position limit exceeds portfolio concurrency")
    if profile.maxPositionsPerSymbol > profile.maxConcurrentPositions:
        raise ValueError("Per-symbol position limit exceeds portfolio concurrency")
    for field_name in (
        "riskPerTradePercent",
        "maxStrategyOpenRiskPercent",
        "maxSymbolOpenRiskPercent",
        "maxDirectionOpenRiskPercent",
        "maxCorrelatedOpenRiskPercent",
    ):
        if float(getattr(profile, field_name)) > profile.maxOpenRiskPercent:
            raise ValueError(f"Risk profile sub-limit exceeds total open risk: {field_name}")
    if profile.canaryLossStopUsdt > profile.capitalLimitUsdt:
        raise ValueError("Canary loss stop cannot exceed the capital limit")
    if profile.rewardRiskRatio < float(limits["minimumRewardRiskRatio"]):
        raise ValueError("Risk profile reward/risk must remain at least 2R")


def conservative_profile(environment: str, *, version: int = 1) -> RiskProfileSpec:
    normalized = str(environment or "").strip()
    base = RiskProfileSpec(
        profileKey=f"{normalized}_conservative",
        version=version,
        environment=normalized,
        name=f"{normalized.replace('_', ' ').title()} Conservative",
    )
    if normalized == "local_forward":
        return replace(
            base,
            maxActiveStrategies=4,
            maxConcurrentPositions=3,
            maxPositionsPerStrategy=2,
            maxOrderNotionalUsdt=250.0,
            maxLeverage=2,
            dailyLossStopPercent=2.0,
            maxDrawdownStopPercent=5.0,
        )
    if normalized == "okx_demo":
        return replace(
            base,
            maxActiveStrategies=4,
            maxConcurrentPositions=3,
            maxPositionsPerStrategy=2,
            maxOrderNotionalUsdt=250.0,
            maxLeverage=2,
            dailyLossStopPercent=2.0,
            maxDrawdownStopPercent=5.0,
        )
    if normalized == "live_standard":
        return replace(
            base,
            maxActiveStrategies=3,
            maxConcurrentPositions=3,
            maxPositionsPerStrategy=2,
            maxOrderNotionalUsdt=250.0,
            maxLeverage=2,
            dailyLossStopPercent=2.0,
            maxDrawdownStopPercent=5.0,
            allowNewEntries=False,
        )
    if normalized != "live_canary":
        raise ValueError(f"Unsupported conservative profile environment: {normalized}")
    return base


def build_risk_profile_record(
    profile: RiskProfileSpec,
    *,
    status: str = "draft",
) -> RiskProfileRecord:
    limits = safety_envelope(profile.environment)
    validate_profile(profile, limits)
    payload = profile.to_dict()
    identity = {
        "profileKey": profile.profileKey,
        "version": profile.version,
        "environment": profile.environment,
        "profile": payload,
        "safetyEnvelope": limits,
    }
    content_hash = stable_hash(identity)
    return RiskProfileRecord(
        riskProfileId=stable_hash(identity, prefix="risk_profile"),
        profileKey=profile.profileKey,
        version=profile.version,
        environment=profile.environment,
        name=profile.name,
        status=status,
        profile=payload,
        safetyEnvelope=limits,
        contentHash=content_hash,
    )


def register_default_risk_profiles(repository: RegistryRepository) -> dict[str, RiskProfileRecord]:
    records: dict[str, RiskProfileRecord] = {}
    for environment in sorted(ENVIRONMENTS):
        record = build_risk_profile_record(
            conservative_profile(environment),
            status="preset",
        )
        records[environment] = repository.create_risk_profile(record)
    return records


def activate_risk_profile(
    repository: RegistryRepository,
    profile: RiskProfileRecord,
    *,
    actor: str,
    reason: str,
    action: str = "activated",
) -> RiskProfileActivationRecord:
    registered = repository.get_risk_profile(profile.riskProfileId)
    if registered is None or registered.contentHash != profile.contentHash:
        raise ValueError("Risk profile must be registered with a matching checksum")
    current = repository.get_active_risk_profile(profile.environment)
    payload = {
        "environment": profile.environment,
        "riskProfileId": profile.riskProfileId,
        "previousRiskProfileId": current.riskProfileId if current else None,
        "action": action,
        "actor": str(actor or "system"),
        "reason": str(reason or "profile_activation"),
    }
    content_hash = stable_hash(payload)
    return repository.create_risk_profile_activation(
        RiskProfileActivationRecord(
            activationId=stable_hash(
                {**payload, "ordinal": len(repository.list_risk_profile_activations(environment=profile.environment))},
                prefix="risk_profile_activation",
            ),
            environment=profile.environment,
            riskProfileId=profile.riskProfileId,
            previousRiskProfileId=current.riskProfileId if current else None,
            action=action,
            actor=payload["actor"],
            reason=payload["reason"],
            contentHash=content_hash,
        )
    )


def execution_envelope(record: RiskProfileRecord) -> dict[str, Any]:
    profile = dict(record.profile)
    return {
        **profile,
        "riskProfileId": record.riskProfileId,
        "riskProfileHash": record.contentHash,
        "profileKey": record.profileKey,
        "profileVersion": record.version,
    }
