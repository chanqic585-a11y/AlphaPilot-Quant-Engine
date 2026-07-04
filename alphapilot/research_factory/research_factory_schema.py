"""Strategy Research Factory design schema."""

from __future__ import annotations

from typing import Any


def build_strategy_research_factory_spec() -> dict[str, Any]:
    return {
        "factoryId": "strategy_research_factory_v01",
        "purpose": "Move AlphaPilot from write-strategy-first to validate-factor-first research.",
        "workflow": [
            "generate_candidate_factors",
            "evaluate_factors",
            "filter_stable_factors",
            "combine_factors_into_strategy_hypotheses",
            "compare_against_benchmark_suite",
            "implement_freqtrade_strategy_only_after_research_pass",
            "run_smoke_and_expanded_validation",
            "keep_dry_run_approval_as_separate_review",
        ],
        "integrationWithDynamicRegime": {
            "dynamicUniverseInput": "historical_dynamic_universe_snapshots",
            "regimeInput": "regimeLabel in FactorDataPanel",
            "factorEvaluationSegments": ["trend", "mean_reversion", "breakout", "avoid", "unknown"],
            "outputCandidateType": "dynamic_regime_strategy_candidate",
            "approvalBoundary": "Research factory output is not a trading gate and not a Dry-run approval.",
        },
        "auditRules": [
            "record source factor ids",
            "record data coverage and missing-rate caveats",
            "record benchmark comparison",
            "record rejected hypotheses",
            "record safety boundary before any strategy implementation",
        ],
        "researchOnly": True,
        "implementationStatus": "design_only",
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }
