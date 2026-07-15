from __future__ import annotations

from alphapilot.validation.candidate_deduplication import deduplicate_candidates
from alphapilot.validation.candidate_selection import discover_candidates


def _candidate(
    strategy_id: str,
    family: str,
    definition_hash: str,
    signal_hash: str | None = None,
) -> dict:
    return {
        "strategyId": strategy_id,
        "strategyName": family,
        "strategyFamily": family,
        "timeframe": "1h",
        "status": "archived",
        "primaryFailureType": "risk_model_failure",
        "signalLayer": {"profitFactor": 1.32, "averageNetR": 0.18},
        "evidenceBasis": {"tradeCount": 200},
        "strategyDefinitionHash": definition_hash,
        "signalDefinitionHash": signal_hash or definition_hash,
    }


def test_duplicate_versions_count_as_one_family_vote() -> None:
    family = "short_cycle_event_1h_sweep_reclaim_factor_v2"
    candidates = discover_candidates(
        [
            _candidate("strategy_version_05c158", family, "same_hash"),
            _candidate("strategy_version_54dc908", family, "same_hash"),
        ]
    )

    report = deduplicate_candidates(candidates)

    assert report.candidate_version_count == 2
    assert report.candidate_family_count == 1
    assert report.canonical_representative_count == 1
    assert report.duplicate_version_count == 1
    assert report.canonical_candidates[0].strategy_version_id == (
        "strategy_version_05c158"
    )
    assert report.version_to_representative["strategy_version_54dc908"] == (
        "strategy_version_05c158"
    )


def test_same_family_with_different_signal_hash_is_not_silently_merged() -> None:
    family = "short_cycle_event_1h_sweep_reclaim_factor_v2"
    candidates = discover_candidates(
        [
            _candidate("v1", family, "hash_a"),
            _candidate("v2", family, "hash_b"),
        ]
    )

    report = deduplicate_candidates(candidates)

    assert report.canonical_representative_count == 2
    assert report.duplicate_version_count == 0
    assert report.family_definition_conflicts == {family: ["hash_a", "hash_b"]}


def test_research_metadata_difference_does_not_duplicate_same_signal() -> None:
    family = "short_cycle_event_1h_sweep_reclaim_factor_v2"
    candidates = discover_candidates(
        [
            _candidate("v1", family, "definition_a", "same_signal"),
            _candidate("v2", family, "definition_b", "same_signal"),
        ]
    )

    report = deduplicate_candidates(candidates)

    assert report.canonical_representative_count == 1
    assert report.duplicate_version_count == 1
