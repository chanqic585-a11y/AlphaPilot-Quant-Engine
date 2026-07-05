"""Registry constants for V13.4.25 research hypotheses."""

from __future__ import annotations

RESEARCH_ONLY_WARNING = "Research hypothesis only. Not a strategy, not a signal, not Dry-run approval."

SOURCE_REPORTS = {
    "factorEvaluation": "reports/v13_4_22_factor_evaluation_report.json",
    "factorCandidates": "reports/v13_4_22_factor_candidates.json",
    "benchmarkSuite": "reports/v13_4_23_benchmark_suite_report.json",
    "benchmarkReview": "reports/v13_4_24_benchmark_result_review.json",
    "benchmarkArchive": "reports/v13_4_24_benchmark_status_archive.json",
}

REQUIRED_HYPOTHESIS_IDS = [
    "HYP-001",
    "HYP-002",
    "HYP-003",
    "HYP-004",
    "HYP-005",
    "HYP-006",
    "HYP-007",
    "HYP-008",
]

REQUIRED_REJECTED_IDS = [
    "HYP-R01",
    "HYP-R02",
    "HYP-R03",
]

HYPOTHESIS_CATEGORIES = [
    "factor_based",
    "benchmark_informed",
    "regime_based",
    "execution_reality",
    "rejected",
]

HYPOTHESIS_STATUSES = [
    "research_only",
    "rejected",
    "deferred",
]

HYPOTHESIS_PRIORITIES = [
    "high",
    "medium",
    "low",
]
