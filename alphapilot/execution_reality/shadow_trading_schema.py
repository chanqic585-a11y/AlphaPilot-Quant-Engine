"""Shadow trading data structures.

Shadow trading records hypothetical signal outcomes without creating orders.
V13.4.11 only defines the schema; it does not start polling or execution.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ShadowSignal:
    shadowSignalId: str
    proposalId: str | None
    strategyId: str
    symbol: str
    timeframe: str
    signalTime: str
    theoreticalEntryPrice: float
    positionNotional: float
    stopLossPrice: float | None = None
    takeProfitPrice: float | None = None
    bidPriceAtSignal: float | None = None
    askPriceAtSignal: float | None = None
    spreadPctAtSignal: float | None = None
    orderbookDepthAtSignal: dict[str, Any] | None = None
    status: str = "tracking_not_started"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ShadowExecutionSnapshot:
    shadowSignalId: str
    timestamp: str
    lastPrice: float | None
    bidPrice: float | None = None
    askPrice: float | None = None
    spreadPct: float | None = None
    orderbookDepth: dict[str, Any] | None = None
    label: str = "snapshot"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ShadowOutcome:
    shadowSignalId: str
    status: str
    followUp1m: ShadowExecutionSnapshot | None = None
    followUp5m: ShadowExecutionSnapshot | None = None
    followUp15m: ShadowExecutionSnapshot | None = None
    followUp1h: ShadowExecutionSnapshot | None = None
    followUp4h: ShadowExecutionSnapshot | None = None
    followUp24h: ShadowExecutionSnapshot | None = None
    wouldHitStop: bool | None = None
    wouldHitTakeProfit: bool | None = None
    maxFavorableExcursion: float | None = None
    maxAdverseExcursion: float | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

