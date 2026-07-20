from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from alphapilot.automatic_candidate_research.intraday_session import (
    build_intraday_prefilter,
    build_session_signal_table,
    replay_intraday_session,
)
from alphapilot.automatic_candidate_research.preregistration import (
    build_preregistration,
)
from alphapilot.standard_replication import ReplicationSourceRegistry


REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = (
    REPO_ROOT
    / "research"
    / "source_registry"
    / "strategy_research_source_registry_v36_5.json"
)


def test_v36_5_registry_freezes_two_executable_candidates_and_blocks_carry() -> None:
    registry = ReplicationSourceRegistry.load(REGISTRY_PATH)
    preregistration = build_preregistration(
        registry=registry,
        campaign_id="v36-5-intraday-fixture",
        created_at="2026-07-19T00:00:00Z",
        comparison_panel={
            "developmentStart": "2021-02-01T00:00:00Z",
            "developmentEnd": "2025-01-01T00:00:00Z",
            "dataSnapshotId": "snapshot-fixture",
            "costPolicyHash": "cost-policy-fixture",
            "capitalPolicyHash": "capital-policy-fixture",
            "benchmarkPolicyHash": "benchmark-policy-fixture",
            "randomSeed": 365,
        },
    )

    assert registry.family_ids == (
        "crypto_funding_carry_v1",
        "crypto_intraday_session_predictability_v1",
    )
    assert preregistration["eligibleCandidateIds"] == [
        "v36_5_intraday_session_crypto_adaptation",
        "v36_5_intraday_session_source_replication",
    ]
    assert preregistration["eligibleCandidateCount"] == 2
    assert preregistration["blockedFamilyIds"] == ["crypto_funding_carry_v1"]
    assert preregistration["trialCount"] == 6
    assert "v36_5_funding_carry_source_replication" not in preregistration[
        "trialsByCandidate"
    ]
    assert all(
        len(trials) == 3
        for trials in preregistration["trialsByCandidate"].values()
    )


def test_session_signal_is_causal_when_future_rows_are_appended() -> None:
    frame = _patterned_frame(days=80)
    cutoff = len(frame) - 72
    original = build_session_signal_table(
        frame.iloc[:cutoff].copy(),
        lookback_sessions=12,
        minimum_session_mean=0.0005,
        adaptation=False,
    )
    extended = frame.copy()
    extended.loc[cutoff:, "close"] = extended.loc[cutoff:, "close"] * 5.0
    extended.loc[cutoff:, "high"] = extended.loc[cutoff:, "close"] * 1.01
    extended.loc[cutoff:, "low"] = extended.loc[cutoff:, "close"] * 0.99
    with_future = build_session_signal_table(
        extended,
        lookback_sessions=12,
        minimum_session_mean=0.0005,
        adaptation=False,
    )

    observed = with_future[with_future["sessionStart"] < frame.iloc[cutoff]["date"]]
    pd.testing.assert_series_equal(
        original["historicalMean"].reset_index(drop=True),
        observed["historicalMean"].reset_index(drop=True),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        original["predictedSide"].reset_index(drop=True),
        observed["predictedSide"].reset_index(drop=True),
        check_names=False,
    )
    assert original.groupby("sessionId").head(12)["predictedSide"].eq(0).all()


def test_intraday_replay_passes_prefilter_on_known_causal_fixture() -> None:
    frames = {
        (symbol, "1h"): _patterned_frame(days=120, price_offset=index * 50.0)
        for index, symbol in enumerate(
            ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
        )
    }
    definition = {
        "candidateId": "fixture_intraday",
        "familyId": "crypto_intraday_session_predictability_v1",
        "timeframe": "1h",
        "sessionHours": 8,
        "lookbackSessions": 12,
        "minimumSessionMean": 0.0005,
        "atrBars": 24,
        "stopAtr": 3.0,
        "maximumHoldBars": 7,
        "adaptation": False,
    }

    metrics, events, prefilter = replay_intraday_session(
        frames=frames,
        definition=definition,
        round_trip_cost_rate=0.0012,
    )

    assert metrics["eventCount"] >= 100
    assert metrics["averageNetR"] > 0
    assert metrics["profitFactor"] > 1
    assert len(events) == metrics["eventCount"]
    assert prefilter == build_intraday_prefilter(metrics=metrics, events=events)
    assert prefilter["passed"] is True
    assert prefilter["lockedOosReadCount"] == 0


def test_repository_canonical_definitions_are_frozen_and_metadata_only() -> None:
    intraday = json.loads(
        (
            REPO_ROOT
            / "research/canonical_replications/crypto_intraday_session_predictability_v1.json"
        ).read_text(encoding="utf-8")
    )
    carry = json.loads(
        (
            REPO_ROOT
            / "research/canonical_replications/crypto_funding_carry_v1.json"
        ).read_text(encoding="utf-8")
    )

    assert intraday["variantBudget"] == 2
    assert intraday["parameterTrialCountPerVariant"] == 3
    assert intraday["lockedOosReadCount"] == 0
    assert carry["status"] == "data_blocked"
    assert carry["executionCandidateCount"] == 0
    assert carry["requiredAlignedData"] == [
        "same_exchange_spot",
        "same_exchange_perpetual",
        "funding_rate",
        "dual_leg_cost_and_capacity",
    ]


def _patterned_frame(*, days: int, price_offset: float = 0.0) -> pd.DataFrame:
    dates = pd.date_range(
        "2024-01-01", periods=days * 24, freq="1h", tz="UTC"
    )
    session_side = np.select(
        [dates.hour < 8, dates.hour < 16],
        [1.0, -1.0],
        default=1.0,
    )
    hourly_return = session_side * 0.0015
    open_values = np.empty(len(dates), dtype=float)
    close_values = np.empty(len(dates), dtype=float)
    price = 100.0 + price_offset
    for index, change in enumerate(hourly_return):
        open_values[index] = price
        price = price * (1.0 + float(change))
        close_values[index] = price
    return pd.DataFrame(
        {
            "date": dates,
            "open": open_values,
            "high": np.maximum(open_values, close_values) * 1.001,
            "low": np.minimum(open_values, close_values) * 0.999,
            "close": close_values,
            "volume": 1_000_000.0,
        }
    )
