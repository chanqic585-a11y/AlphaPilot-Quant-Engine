"""Immutable execution records for leg-level Advisory-R exits."""

from __future__ import annotations

from dataclasses import dataclass

from .models import ExitPolicy


@dataclass(frozen=True)
class ExitCosts:
    feeBpsPerSide: float = 0.0
    slippageBpsPerSide: float = 0.0
    spreadBpsPerSide: float = 0.0


@dataclass(frozen=True)
class ExitLeg:
    fraction: float
    reason: str
    triggerPosition: int
    executionPosition: int
    triggerTimestamp: str
    executionTimestamp: str
    price: float
    grossR: float
    feesR: float
    slippageR: float
    spreadProxyR: float
    fundingR: float
    netR: float
    isGapFill: bool = False
    ambiguousPath: bool = False


@dataclass(frozen=True)
class ExitExecutionResult:
    signalTimestamp: str
    entryTimestamp: str
    exitTimestamp: str
    signalPosition: int
    entryPosition: int
    exitPosition: int
    entryReference: str
    direction: str
    entryPrice: float
    initialStopPrice: float
    riskDistance: float
    exitPolicy: ExitPolicy
    exitPolicyHash: str
    legs: tuple[ExitLeg, ...]
    stopHistory: tuple[float, ...]
    ambiguousPath: bool
    grossR: float
    feesR: float
    slippageR: float
    spreadProxyR: float
    fundingR: float
    netR: float
    mfeR: float
    maeR: float
    givebackR: float

