"""Schema helpers for V13.4.27 market regime and data integrity review."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RegimeAwareFailureReview:
    conclusion: str
    evidence: list[str]
    limitations: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MarketRegimeDataIntegrityReport:
    reportId: str
    version: str
    status: str
    timerange: str
    dataPath: str
    timeframesChecked: list[str]
    dataIntegrity: dict[str, Any]
    btcRegime: dict[str, Any]
    regimeAwareFailureReview: RegimeAwareFailureReview
    safetyBoundary: dict[str, bool]
    generatedAt: str
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["regimeAwareFailureReview"] = self.regimeAwareFailureReview.to_dict()
        return payload
