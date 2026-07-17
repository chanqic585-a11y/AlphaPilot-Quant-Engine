from __future__ import annotations

import numpy as np
import pandas as pd

from alphapilot.formal_validation.formal_statistics import (
    campaign_fdr,
    deflated_sharpe_report,
    newey_west_alpha,
    probability_of_overfitting,
    stationary_bootstrap_test,
)


def test_newey_west_detects_persistent_positive_increment() -> None:
    differential = np.tile([0.002, 0.001, 0.003, 0.0025], 100)

    report = newey_west_alpha(differential, lag=5)

    assert report["alpha"] > 0
    assert report["hacT"] > 5
    assert report["oneSidedP"] < 0.001
    assert report["lagSensitivity"]["2"] < 0.001
    assert report["lagSensitivity"]["10"] < 0.001


def test_bh_and_by_match_known_ordering() -> None:
    report = campaign_fdr({"a": 0.001, "b": 0.02, "c": 0.2}, q=0.1)

    assert report["benjaminiHochberg"]["discoveries"] == ["a", "b"]
    assert report["benjaminiHochberg"]["adjustedPValues"]["a"] == 0.003
    assert report["benjaminiYekutieli"]["adjustedPValues"]["a"] > 0.003


def test_dsr_uses_actual_result_read_trial_count() -> None:
    returns = np.tile([0.01, -0.002, 0.008, 0.001], 100)

    report = deflated_sharpe_report(
        returns,
        actual_trials=10,
        comparable_trials=6,
        effective_trials=4,
        sharpe_std=0.4,
    )

    assert report["actualResultReadTrialCount"] == 10
    assert report["dsrActualTrials"] > 0.5
    assert report["observedSharpe"] > 0


def test_pbo_flags_selection_that_reverses_out_of_sample() -> None:
    index = pd.date_range("2024-01-01", periods=100, freq="D", tz="UTC")
    panel = pd.DataFrame(
        {
            "a": np.r_[np.full(50, 0.02), np.full(50, -0.02)],
            "b": np.r_[np.full(50, -0.02), np.full(50, 0.02)],
            "c": np.zeros(100),
        },
        index=index,
    )

    report = probability_of_overfitting(panel, block_count=10)

    assert report["combinationCount"] > 0
    assert 0 <= report["pbo"] <= 1
    assert report["candidateCount"] == 3


def test_stationary_bootstrap_is_seeded_and_detects_an_edge() -> None:
    rng = np.random.default_rng(3)
    panel = pd.DataFrame(
        {
            "edge": rng.normal(0.003, 0.002, 160),
            "null": rng.normal(0.0, 0.002, 160),
        }
    )

    first = stationary_bootstrap_test(
        panel, bootstrap_count=500, mean_block_length=8, seed=17
    )
    second = stationary_bootstrap_test(
        panel, bootstrap_count=500, mean_block_length=8, seed=17
    )

    assert first == second
    assert first["whiteRealityCheck"]["pValue"] < 0.1
    assert first["spa"]["pValue"] < 0.1
    assert first["bootstrapCount"] == 500
