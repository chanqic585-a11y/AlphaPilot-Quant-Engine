"""Typed state for public-market, order-free local forward observation."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


TIMEFRAME_MILLISECONDS = {
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "1h": 60 * 60 * 1000,
    "4h": 4 * 60 * 60 * 1000,
    "1d": 24 * 60 * 60 * 1000,
}


@dataclass(frozen=True)
class ForwardRiskEnvelope:
    initialEquityUsdt: float = 1000.0
    riskPerTradePercent: float = 0.25
    maxOpenRiskPercent: float = 1.0
    maxOrderNotionalUsdt: float = 250.0
    maxConcurrentPositions: int = 3
    feeRate: float = 0.0005
    slippageRate: float = 0.0002
    rewardRiskRatio: float = 2.0

    def validate(self) -> None:
        if self.initialEquityUsdt != 1000.0:
            raise ValueError("V13.19 forward accounts must start with 1000 USDT")
        if not 0 < self.riskPerTradePercent <= 1.0:
            raise ValueError("Forward risk per trade must be within (0, 1%]")
        if self.maxOpenRiskPercent < self.riskPerTradePercent:
            raise ValueError("Forward max open risk cannot be below per-trade risk")
        if self.maxOrderNotionalUsdt <= 0 or self.maxConcurrentPositions <= 0:
            raise ValueError("Forward notional and concurrency limits must be positive")
        if self.feeRate < 0 or self.slippageRate < 0:
            raise ValueError("Forward costs must be non-negative")
        if self.rewardRiskRatio < 2.0:
            raise ValueError("Forward reward/risk must be at least 2R")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ForwardBar:
    instrumentId: str
    timeframe: str
    timestampMs: int
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True)
class ForwardDecision:
    signalId: str
    direction: str
    riskDistance: float
    factorContext: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PendingForwardSignal:
    signalId: str
    instrumentId: str
    timeframe: str
    direction: str
    decisionTimestampMs: int
    riskDistance: float
    factorContext: dict[str, Any]


@dataclass(frozen=True)
class VirtualForwardPosition:
    positionId: str
    signalId: str
    instrumentId: str
    timeframe: str
    direction: str
    decisionTimestampMs: int
    entryTimestampMs: int
    entryBasePrice: float
    entryFillPrice: float
    quantity: float
    riskDistance: float
    riskAmountUsdt: float
    stopPrice: float
    targetPrice: float
    entryFeePaid: float
    entrySlippagePaid: float
    markPrice: float
    factorContext: dict[str, Any]


@dataclass
class ForwardState:
    forwardSessionId: str
    forwardReleaseId: str
    strategyCandidateId: str
    accountId: str
    initialEquity: float
    cashBalance: float
    equity: float
    realizedPnl: float = 0.0
    totalFeesPaid: float = 0.0
    totalSlippagePaid: float = 0.0
    peakEquity: float = 1000.0
    maxDrawdownPercent: float = 0.0
    closedOutcomeCount: int = 0
    lastObservedByInstrument: dict[str, int] = field(default_factory=dict)
    pendingSignals: dict[str, PendingForwardSignal] = field(default_factory=dict)
    openPositions: dict[str, VirtualForwardPosition] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schemaVersion"] = "local_forward_state_v1"
        return payload

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ForwardState:
        values = dict(payload)
        values.pop("schemaVersion", None)
        values["pendingSignals"] = {
            key: PendingForwardSignal(**value)
            for key, value in dict(values.get("pendingSignals", {})).items()
        }
        values["openPositions"] = {
            key: VirtualForwardPosition(**value)
            for key, value in dict(values.get("openPositions", {})).items()
        }
        values["lastObservedByInstrument"] = {
            str(key): int(value)
            for key, value in dict(values.get("lastObservedByInstrument", {})).items()
        }
        return cls(**values)


@dataclass(frozen=True)
class ForwardTransition:
    state: ForwardState
    events: tuple[dict[str, Any], ...]
    closedOutcomes: tuple[dict[str, Any], ...]
