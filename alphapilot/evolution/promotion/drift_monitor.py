"""Deterministic Demo drift checks that fail closed on integrity problems."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class DemoDriftObservation:
    dataFresh: bool
    metadataFresh: bool
    clockSynchronized: bool
    ledgerMatchesExchange: bool
    checksumsMatch: bool
    rollingProfitFactor: float
    consecutiveLosses: int
    observedSlippageBps: float
    assumedSlippageBps: float
    calibrationError: float
    regimePerformanceDrop: float


@dataclass(frozen=True)
class DriftCheck:
    checkId: str
    severity: str
    triggered: bool
    detail: str


@dataclass(frozen=True)
class DriftEvaluation:
    severity: str
    pauseRequired: bool
    reasonCodes: tuple[str, ...]
    checks: tuple[DriftCheck, ...]


_SEVERITY_RANK = {"none": 0, "warning": 1, "critical": 2}


def evaluate_demo_drift(observation: DemoDriftObservation) -> DriftEvaluation:
    numbers = (
        observation.rollingProfitFactor,
        observation.observedSlippageBps,
        observation.assumedSlippageBps,
        observation.calibrationError,
        observation.regimePerformanceDrop,
    )
    if not all(math.isfinite(float(value)) for value in numbers):
        raise ValueError("Drift observation contains non-finite metrics")
    if observation.consecutiveLosses < 0 or observation.assumedSlippageBps < 0:
        raise ValueError("Drift observation contains invalid negative metrics")
    slippage_ratio = (
        observation.observedSlippageBps / observation.assumedSlippageBps
        if observation.assumedSlippageBps > 0
        else (float("inf") if observation.observedSlippageBps > 0 else 1.0)
    )
    raw = (
        ("market_data_stale", "critical", not observation.dataFresh, "Ticker or candle cache is stale"),
        ("instrument_metadata_stale", "critical", not observation.metadataFresh, "Instrument metadata is stale"),
        ("clock_unsynchronized", "critical", not observation.clockSynchronized, "Exchange clock is not synchronized"),
        ("ledger_exchange_mismatch", "critical", not observation.ledgerMatchesExchange, "Local ledger differs from Demo positions"),
        ("checksum_mismatch", "critical", not observation.checksumsMatch, "Release checksum changed"),
        ("rolling_profit_factor", "critical", observation.rollingProfitFactor < 1.0, "Rolling profit factor fell below 1.0"),
        ("consecutive_losses", "critical", observation.consecutiveLosses >= 5, "Five or more consecutive losses"),
        ("slippage_drift", "critical", slippage_ratio >= 3.0, "Observed slippage is at least 3x assumption"),
        ("calibration_drift", "warning", observation.calibrationError > 0.10, "Probability calibration error exceeded 0.10"),
        ("regime_drift", "warning", observation.regimePerformanceDrop > 0.30, "Regime performance drop exceeded 30%"),
        ("slippage_warning", "warning", 2.0 <= slippage_ratio < 3.0, "Observed slippage is at least 2x assumption"),
        ("loss_streak_warning", "warning", 3 <= observation.consecutiveLosses < 5, "Three or four consecutive losses"),
    )
    checks = tuple(DriftCheck(*item) for item in raw)
    triggered = tuple(check for check in checks if check.triggered)
    severity = max((check.severity for check in triggered), key=lambda item: _SEVERITY_RANK[item], default="none")
    return DriftEvaluation(
        severity=severity,
        pauseRequired=severity != "none",
        reasonCodes=tuple(check.checkId for check in triggered),
        checks=checks,
    )
