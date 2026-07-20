from __future__ import annotations

from dataclasses import replace

import pytest

from alphapilot.portfolio_rescue.contracts import (
    CampaignContract,
    SleeveContract,
    build_default_campaign,
)


def test_default_campaign_freezes_three_distinct_preexisting_sleeves() -> None:
    campaign = build_default_campaign()

    assert [row.candidate_id for row in campaign.sleeves] == [
        "v13_7_40_1h_short_rejection_2149_asset_filter_top10",
        "v13_7_20_lf_research_candidate_117",
        "v13_7_20_lf_research_candidate_090",
    ]
    assert len({row.family for row in campaign.sleeves}) == 3
    assert all(row.selection_basis == "preexisting_source_rank_and_mechanism_distinctness" for row in campaign.sleeves)
    assert 6 <= len(campaign.policies) <= 8
    assert campaign.maximum_development_trials == 8
    assert campaign.status == "development_only"
    assert campaign.formal_candidate_count == 0
    assert campaign.locked_oos_read_count == 0
    assert campaign.release_count == 0
    assert campaign.campaign_hash.startswith("portfolio_rescue_campaign_")


def test_campaign_rejects_duplicate_family_and_trial_budget_overrun() -> None:
    campaign = build_default_campaign()
    duplicate = replace(campaign.sleeves[1], family=campaign.sleeves[0].family)

    with pytest.raises(ValueError, match="duplicate_sleeve_family"):
        CampaignContract(
            campaign_id="bad",
            sleeves=(campaign.sleeves[0], duplicate),
            policies=campaign.policies,
        )

    with pytest.raises(ValueError, match="development_trial_budget_exceeded"):
        CampaignContract(
            campaign_id="bad_budget",
            sleeves=campaign.sleeves,
            policies=campaign.policies + campaign.policies[:3],
            maximum_development_trials=8,
        )


def test_campaign_rejects_more_than_three_sleeves() -> None:
    campaign = build_default_campaign()
    extra = SleeveContract(
        candidate_id="extra",
        family="extra_family",
        direction="long",
        timeframe="4h",
        selection_basis="preexisting_source_rank_and_mechanism_distinctness",
        source_rank=1,
    )

    with pytest.raises(ValueError, match="maximum_three_sleeves"):
        CampaignContract(
            campaign_id="too_many",
            sleeves=campaign.sleeves + (extra,),
            policies=campaign.policies,
        )
