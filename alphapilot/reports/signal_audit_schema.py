"""AlphaPilot V13.4.2 signal audit report schema."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class SignalAuditReport:
    reportId: str
    strategyId: str
    sourceBacktestReport: str
    isMock: bool
    timerange: str
    pairs: list[str]
    overall: dict[str, Any]
    filterStats: list[dict[str, Any]] = field(default_factory=list)
    skipReasonCounts: list[dict[str, Any]] = field(default_factory=list)
    pairBreakdown: list[dict[str, Any]] = field(default_factory=list)
    monthlyBreakdown: list[dict[str, Any]] = field(default_factory=list)
    dataAvailability: dict[str, Any] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    generatedAt: str = ""
    source: str = "alphapilot_v13_4_2_signal_audit"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
