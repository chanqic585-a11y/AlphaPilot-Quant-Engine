"""Frozen resource budget for the background research service."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from alphapilot.evolution.registry.hashing import stable_hash


@dataclass(frozen=True)
class ResearchServicePolicy:
    max_concurrent_campaigns: int
    max_concurrent_formal_runs: int
    max_campaigns: int
    max_families_per_campaign: int
    max_candidates_per_campaign: int
    max_formal_runs_per_campaign: int
    max_structural_revisions_per_family: int
    full_backtests_remaining: int

    @classmethod
    def default(cls) -> "ResearchServicePolicy":
        return cls(
            max_concurrent_campaigns=1,
            max_concurrent_formal_runs=1,
            max_campaigns=3,
            max_families_per_campaign=6,
            max_candidates_per_campaign=12,
            max_formal_runs_per_campaign=4,
            max_structural_revisions_per_family=1,
            full_backtests_remaining=96,
        )

    @property
    def policy_hash(self) -> str:
        return stable_hash(asdict(self), prefix="v35_research_policy")
