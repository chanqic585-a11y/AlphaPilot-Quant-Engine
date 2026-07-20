"""Frozen identities and budget for the V13.27.1.46 rescue campaign."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


@dataclass(frozen=True)
class SleeveContract:
    candidate_id: str
    family: str
    direction: str
    timeframe: str
    selection_basis: str
    source_rank: int

    @property
    def sleeve_hash(self) -> str:
        return stable_hash(asdict(self), prefix="portfolio_rescue_sleeve")

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "sleeve_hash": self.sleeve_hash}


@dataclass(frozen=True)
class RiskPolicy:
    policy_id: str
    pair_cooldown_days: int
    maximum_concurrent_positions: int
    same_direction_cap: int
    losing_pair_cooldown_days: int
    additional_cost_stress_r: tuple[float, ...] = (0.05, 0.10)
    version: str = "v13.27.1.46"

    @property
    def policy_hash(self) -> str:
        return stable_hash(asdict(self), prefix="portfolio_rescue_policy")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["additional_cost_stress_r"] = list(self.additional_cost_stress_r)
        payload["policy_hash"] = self.policy_hash
        return payload


@dataclass(frozen=True)
class CampaignContract:
    campaign_id: str
    sleeves: tuple[SleeveContract, ...]
    policies: tuple[RiskPolicy, ...]
    maximum_development_trials: int = 8
    status: str = "development_only"
    formal_candidate_count: int = 0
    locked_oos_read_count: int = 0
    release_count: int = 0

    def __post_init__(self) -> None:
        if not 2 <= len(self.sleeves) <= 3:
            raise ValueError("maximum_three_sleeves")
        families = [row.family for row in self.sleeves]
        if len(families) != len(set(families)):
            raise ValueError("duplicate_sleeve_family")
        if not 6 <= len(self.policies) <= self.maximum_development_trials:
            raise ValueError("development_trial_budget_exceeded")
        if self.status != "development_only":
            raise ValueError("campaign_must_be_development_only")
        if any((self.formal_candidate_count, self.locked_oos_read_count, self.release_count)):
            raise ValueError("formal_oos_or_release_claim_forbidden")

    @property
    def campaign_hash(self) -> str:
        return stable_hash(
            {
                "campaign_id": self.campaign_id,
                "sleeves": [row.to_dict() for row in self.sleeves],
                "policies": [row.to_dict() for row in self.policies],
                "maximum_development_trials": self.maximum_development_trials,
                "status": self.status,
                "formal_candidate_count": self.formal_candidate_count,
                "locked_oos_read_count": self.locked_oos_read_count,
                "release_count": self.release_count,
            },
            prefix="portfolio_rescue_campaign",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaignHash": self.campaign_hash,
            "campaignId": self.campaign_id,
            "formalCandidateCount": self.formal_candidate_count,
            "lockedOosReadCount": self.locked_oos_read_count,
            "maximumDevelopmentTrials": self.maximum_development_trials,
            "policies": [row.to_dict() for row in self.policies],
            "releaseCount": self.release_count,
            "sleeves": [row.to_dict() for row in self.sleeves],
            "status": self.status,
        }


def build_default_campaign() -> CampaignContract:
    selection = "preexisting_source_rank_and_mechanism_distinctness"
    sleeves = (
        SleeveContract(
            candidate_id="v13_7_40_1h_short_rejection_2149_asset_filter_top10",
            family="short_rejection",
            direction="short",
            timeframe="1h",
            selection_basis=selection,
            source_rank=1,
        ),
        SleeveContract(
            candidate_id="v13_7_20_lf_research_candidate_117",
            family="mean_reversion",
            direction="long",
            timeframe="1d",
            selection_basis=selection,
            source_rank=2,
        ),
        SleeveContract(
            candidate_id="v13_7_20_lf_research_candidate_090",
            family="squeeze_breakout",
            direction="long",
            timeframe="1d",
            selection_basis=selection,
            source_rank=4,
        ),
    )
    policies = (
        RiskPolicy("raw_baseline", 0, 99, 99, 0),
        RiskPolicy("pair_7d_cooldown", 7, 99, 99, 0),
        RiskPolicy("pair_14d_cooldown", 14, 99, 99, 0),
        RiskPolicy("pair_14d_max2", 14, 2, 2, 0),
        RiskPolicy("pair_14d_max2_direction1", 14, 2, 1, 0),
        RiskPolicy("pair_14d_max2_direction1_loss21d", 14, 2, 1, 21),
    )
    return CampaignContract(
        campaign_id="v13_27_1_46_demo_replay_portfolio_rescue_20260720",
        sleeves=sleeves,
        policies=policies,
    )
