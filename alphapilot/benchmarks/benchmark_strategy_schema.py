"""Benchmark strategy schema.

Benchmarks are comparison references only. They are not live strategies.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class BenchmarkStrategySpec:
    benchmarkId: str
    name: str
    purpose: str
    hypothesis: str
    requiredFields: list[str]
    comparisonMetrics: list[str]
    implementationStatus: str = "design_only"
    dryRunApproved: bool = False
    liveTradingApproved: bool = False
    riskNotes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
