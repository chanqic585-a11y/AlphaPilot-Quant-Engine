from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from alphapilot.automatic_candidate_research.btc_downside_spillover import (
    build_btc_downside_signal_table,
    replay_btc_downside_spillover,
)
from alphapilot.automatic_candidate_research.fixed_core_snapshot import (
    build_fixed_core_snapshot_manifest,
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
    / "strategy_research_source_registry_v36_6.json"
)


def test_v36_6_registry_freezes_two_spillover_candidates() -> None:
    registry = ReplicationSourceRegistry.load(REGISTRY_PATH)
    preregistration = build_preregistration(
        registry=registry,
        campaign_id="v36-6-spillover-fixture",
        created_at="2026-07-19T00:00:00Z",
        comparison_panel={
            "developmentStart": "2021-01-01T00:00:00Z",
            "developmentEnd": "2025-01-01T00:00:00Z",
            "dataSnapshotId": "snapshot-fixture",
            "costPolicyHash": "cost-policy-fixture",
            "capitalPolicyHash": "capital-policy-fixture",
            "benchmarkPolicyHash": "benchmark-policy-fixture",
            "randomSeed": 366,
        },
    )

    assert registry.family_ids == ("crypto_btc_downside_spillover_v1",)
    assert preregistration["eligibleCandidateIds"] == [
        "v36_6_btc_downside_spillover_crypto_adaptation",
        "v36_6_btc_downside_spillover_source_replication",
    ]
    assert preregistration["eligibleCandidateCount"] == 2
    assert preregistration["trialCount"] == 6
    assert preregistration["lockedOosReadCount"] == 0


def test_btc_downside_signal_is_causal_when_future_rows_are_appended() -> None:
    frame = _spillover_frames(periods=4_000)[("BTC-USDT-SWAP", "1h")]
    cutoff = 3_600
    original = build_btc_downside_signal_table(
        frame.iloc[:cutoff].copy(),
        shock_lookback_bars=720,
        shock_quantile=0.05,
        minimum_shock_return=-0.015,
    )
    extended = frame.copy()
    extended.loc[cutoff:, "close"] = extended.loc[cutoff:, "close"] * 7.0
    extended.loc[cutoff:, "high"] = extended.loc[cutoff:, "close"] * 1.01
    extended.loc[cutoff:, "low"] = extended.loc[cutoff:, "close"] * 0.99
    with_future = build_btc_downside_signal_table(
        extended,
        shock_lookback_bars=720,
        shock_quantile=0.05,
        minimum_shock_return=-0.015,
    )

    pd.testing.assert_series_equal(
        original["shockThreshold"].reset_index(drop=True),
        with_future.iloc[:cutoff]["shockThreshold"].reset_index(drop=True),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        original["shockSignal"].reset_index(drop=True),
        with_future.iloc[:cutoff]["shockSignal"].reset_index(drop=True),
        check_names=False,
    )


def test_spillover_replay_passes_prefilter_on_known_causal_fixture() -> None:
    frames = _spillover_frames(periods=7_200)
    definition = {
        "candidateId": "fixture_spillover",
        "familyId": "crypto_btc_downside_spillover_v1",
        "timeframe": "1h",
        "shockLookbackBars": 720,
        "shockQuantile": 0.05,
        "minimumShockReturn": -0.015,
        "atrBars": 24,
        "stopAtr": 2.5,
        "maximumHoldBars": 3,
        "targetSymbols": [
            "ETH-USDT-SWAP",
            "XRP-USDT-SWAP",
            "LTC-USDT-SWAP",
        ],
        "minimumEventCount": 60,
        "adaptation": False,
    }

    metrics, events, prefilter = replay_btc_downside_spillover(
        frames=frames,
        definition=definition,
        round_trip_cost_rate=0.0012,
    )

    assert metrics["eventCount"] >= 60
    assert metrics["averageNetR"] > 0
    assert metrics["profitFactor"] > 1
    assert len(events) == metrics["eventCount"]
    assert prefilter["passed"] is True
    assert prefilter["lockedOosReadCount"] == 0


def test_fixed_core_snapshot_references_and_verifies_existing_partitions(
    tmp_path: Path,
) -> None:
    data_root = tmp_path / "data"
    partition = data_root / "_alphapilot/canonical/okx/swap/ohlcv/BTC/1h/test.parquet"
    partition.parent.mkdir(parents=True)
    _fixture_frame(periods=48).to_parquet(partition, index=False)
    digest = hashlib.sha256(partition.read_bytes()).hexdigest()
    core_path = tmp_path / "core_universe.json"
    core_path.write_text(
        json.dumps(
            {
                "cohortType": "fixed_core_cohort",
                "historicalPitUniverse": False,
                "coreUniverseHash": "core-fixture",
                "members": [
                    {
                        "instrumentId": "BTC-USDT-SWAP",
                        "profiles": {
                            "1h": {
                                "filePath": str(partition.relative_to(data_root)),
                                "sha256": digest,
                                "rowCount": 48,
                            }
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    output_path = tmp_path / "snapshot.json"

    manifest = build_fixed_core_snapshot_manifest(
        core_universe_path=core_path,
        data_root=data_root,
        output_path=output_path,
        timeframes=("1h",),
    )

    assert manifest["status"] == "completed"
    assert manifest["historicalPitUniverse"] is False
    assert manifest["partitionCount"] == 1
    assert manifest["partitions"][0]["outputSha256"] == digest
    assert manifest["partitions"][0]["outputPath"] == str(partition.resolve())
    assert output_path.is_file()


def _fixture_frame(*, periods: int) -> pd.DataFrame:
    dates = pd.date_range("2022-01-01", periods=periods, freq="1h", tz="UTC")
    price = 100.0
    rows: list[dict[str, object]] = []
    for date in dates:
        open_price = price
        price *= 1.0001
        rows.append(
            {
                "date": date,
                "open": open_price,
                "high": max(open_price, price) * 1.001,
                "low": min(open_price, price) * 0.999,
                "close": price,
                "volume": 1_000_000.0,
                "confirmed": 1,
            }
        )
    return pd.DataFrame(rows)


def _spillover_frames(*, periods: int) -> dict[tuple[str, str], pd.DataFrame]:
    dates = pd.date_range("2022-01-01", periods=periods, freq="1h", tz="UTC")
    shock_indices = set(range(800, periods - 8, 96))
    btc_returns = np.full(periods, 0.0001, dtype=float)
    for index in shock_indices:
        btc_returns[index] = -0.03

    frames: dict[tuple[str, str], pd.DataFrame] = {}
    frames[("BTC-USDT-SWAP", "1h")] = _frame_from_returns(dates, btc_returns, 100.0)
    for offset, symbol in enumerate(
        ("ETH-USDT-SWAP", "XRP-USDT-SWAP", "LTC-USDT-SWAP")
    ):
        target_returns = np.full(periods, 0.0001, dtype=float)
        for index in shock_indices:
            target_returns[index + 1 : index + 4] = -0.012
        frames[(symbol, "1h")] = _frame_from_returns(
            dates, target_returns, 50.0 + offset * 25.0
        )
    return frames


def _frame_from_returns(
    dates: pd.DatetimeIndex,
    returns: np.ndarray,
    starting_price: float,
) -> pd.DataFrame:
    price = starting_price
    rows: list[dict[str, object]] = []
    for date, change in zip(dates, returns, strict=True):
        open_price = price
        price *= 1.0 + float(change)
        rows.append(
            {
                "date": date,
                "open": open_price,
                "high": max(open_price, price) * 1.001,
                "low": min(open_price, price) * 0.999,
                "close": price,
                "volume": 1_000_000.0,
                "confirmed": 1,
            }
        )
    return pd.DataFrame(rows)
