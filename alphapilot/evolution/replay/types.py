"""Typed contracts for deterministic event-time historical replay."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ReplayConfig:
    stopLossR: float = 1.0
    takeProfitR: float = 2.0
    maxHoldingBars: int = 12
    feeRate: float = 0.0005
    slippageRate: float = 0.0002
    maxConcurrentPositions: int = 3

    def validate(self) -> None:
        if self.stopLossR <= 0 or self.takeProfitR / self.stopLossR < 2.0:
            raise ValueError("Replay reward/risk must be at least 2R")
        if self.maxHoldingBars <= 0 or self.maxConcurrentPositions <= 0:
            raise ValueError("Replay holding period and concurrency must be positive")
        if self.feeRate < 0 or self.slippageRate < 0:
            raise ValueError("Replay costs must be non-negative")


@dataclass(frozen=True)
class ReplaySignal:
    signalId: str
    instrumentId: str
    timeframe: str
    direction: str
    decisionTimestampMs: int
    riskDistance: float
    sourceEntityId: str
    strategyCandidateId: str | None = None


@dataclass(frozen=True)
class ReplayTrade:
    signalId: str
    instrumentId: str
    timeframe: str
    direction: str
    decisionTimestampMs: int
    entryTimestampMs: int
    exitTimestampMs: int
    entryBasePrice: float
    entryFillPrice: float
    exitBasePrice: float
    exitFillPrice: float
    stopPrice: float
    targetPrice: float
    exitReason: str
    holdingBars: int
    grossR: float
    netR: float
    grossReturn: float
    netReturn: float
    feePaid: float
    slippagePaid: float
    fundingPnl: float
    fundingDataAvailable: bool
    mfeR: float
    maeR: float
    sameBarAmbiguous: bool
    sourceEntityId: str
    strategyCandidateId: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SkippedReplaySignal:
    signalId: str
    instrumentId: str
    decisionTimestampMs: int
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReplayResult:
    config: ReplayConfig
    trades: tuple[ReplayTrade, ...]
    skippedSignals: tuple[SkippedReplaySignal, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "config": asdict(self.config),
            "trades": [trade.to_dict() for trade in self.trades],
            "skippedSignals": [item.to_dict() for item in self.skippedSignals],
        }
