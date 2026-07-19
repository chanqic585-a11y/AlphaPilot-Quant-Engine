from __future__ import annotations

from types import SimpleNamespace
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from alphapilot.formal_validation.candidate_adapter import (
    CandidateAdapterIdentityError,
)
from alphapilot.formal_validation.candidate_adapters import get_candidate_adapter
from alphapilot.standard_replication.tsmom_engine import (
    SELECTED_TSMOM_TRIALS,
    build_tsmom_candidate_spec,
)


SELECTED_CANDIDATES = (
    "v35_tsmom_crypto_adaptation",
    "v35_tsmom_source_replication",
)


def _frames() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2021-01-01", periods=520, freq="1D", tz="UTC")
    close = np.concatenate(
        (
            100.0 + np.sin(np.arange(220) / 9.0),
            np.linspace(132.0, 185.0, 120),
            np.linspace(108.0, 68.0, 180),
        )
    )
    result: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(
        ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
    ):
        scaled = close * (1.0 + offset * 0.04)
        result[symbol] = pd.DataFrame(
            {
                "date": dates,
                "open": np.roll(scaled, 1),
                "high": scaled * 1.002,
                "low": scaled * 0.998,
                "close": scaled,
                "volume": np.full(len(dates), 10_000_000.0 + offset),
                "funding_rate": np.zeros(len(dates)),
            }
        )
        result[symbol].loc[0, "open"] = scaled[0]
    return result


def _preregistration(candidate_id: str) -> dict[str, object]:
    candidate = build_tsmom_candidate_spec(candidate_id)
    return {
        "sourceCandidateId": candidate_id,
        "selectedTrialId": SELECTED_TSMOM_TRIALS[candidate_id],
        "strategyDefinitionHash": candidate["strategyDefinitionHash"],
        "exitPolicyHash": candidate["exitPolicyHash"],
    }


@pytest.mark.parametrize("candidate_id", SELECTED_CANDIDATES)
def test_selected_tsmom_candidates_resolve_through_common_registry(
    candidate_id: str,
) -> None:
    adapter = get_candidate_adapter(candidate_id)

    candidate = adapter.resolve_candidate(
        repo_root=Path(__file__).resolve().parents[2],
        preregistration=_preregistration(candidate_id),
    )

    assert adapter.candidate_id == candidate_id
    assert candidate["candidateId"] == candidate_id
    assert candidate["selectedTrialId"] == SELECTED_TSMOM_TRIALS[candidate_id]
    assert candidate["strategyDefinitionHash"]
    assert candidate["exitPolicyHash"]


def test_non_selected_v35_candidate_remains_fail_closed() -> None:
    with pytest.raises(KeyError, match="candidate_adapter_not_registered"):
        get_candidate_adapter("v35_pair_rv_source_replication")


def test_selected_trial_binding_is_exact() -> None:
    candidate_id = "v35_tsmom_source_replication"
    adapter = get_candidate_adapter(candidate_id)
    preregistration = _preregistration(candidate_id)
    preregistration["selectedTrialId"] = "different-trial"

    with pytest.raises(CandidateAdapterIdentityError, match="selected_trial_mismatch"):
        adapter.resolve_candidate(
            repo_root=Path(__file__).resolve().parents[2],
            preregistration=preregistration,
        )


@pytest.mark.parametrize("candidate_id", SELECTED_CANDIDATES)
def test_tsmom_replay_and_parity_are_non_empty_exact_and_deterministic(
    candidate_id: str,
) -> None:
    adapter = get_candidate_adapter(candidate_id)
    candidate = adapter.resolve_candidate(
        repo_root=Path(__file__).resolve().parents[2],
        preregistration=_preregistration(candidate_id),
    )
    frames = _frames()

    first = list(
        adapter.replay(
            candidate=candidate,
            frames=frames,
            round_trip_cost_rate=0.001,
        )
    )
    second = list(
        adapter.replay(
            candidate=candidate,
            frames=frames,
            round_trip_cost_rate=0.001,
        )
    )
    parity, reference, translated = adapter.run_parity(
        bundle=SimpleNamespace(candidate=candidate, frames=frames),
        repo_root=Path(__file__).resolve().parents[2],
    )

    assert first
    assert first == second
    assert parity["passed"] is True
    assert parity["canonicalIdentityParityPct"] == 100.0
    assert reference == translated
    required = {
        "candidateId",
        "instrumentId",
        "symbol",
        "direction",
        "signalTimestamp",
        "entryTimestamp",
        "exitTimestamp",
        "signalId",
        "grossR",
        "costR",
        "netR",
        "mfeR",
        "maeR",
    }
    assert required.issubset(first[0])
