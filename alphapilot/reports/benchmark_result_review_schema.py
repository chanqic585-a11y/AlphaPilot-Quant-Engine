"""Schema for V13.4.24 benchmark result review."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class BenchmarkResultReviewReport:
    reportId: str
    sourceBenchmarkReport: str
    sourceBenchmarkSummary: str
    sourceBenchmarkManifest: str
    currentStatus: str
    dryRunApproved: bool
    liveTradingApproved: bool
    noTradeComparison: dict[str, Any]
    buyHoldBtcComparison: dict[str, Any]
    benchmarkReviews: list[dict[str, Any]]
    bestBenchmarkReview: dict[str, Any]
    failureFindings: list[str]
    usefulHypothesisSeeds: list[dict[str, Any]]
    rejectedIdeas: list[dict[str, Any]]
    strategyResearchReset: dict[str, Any]
    recommendedNextStep: str
    warnings: list[str]
    generatedAt: str
    source: str = "alphapilot_v13_4_24_benchmark_result_review"
    inputReports: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
