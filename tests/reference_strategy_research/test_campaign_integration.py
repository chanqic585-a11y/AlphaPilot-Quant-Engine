from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd

from alphapilot.reference_strategy_research.candidates import build_selected_candidates
from alphapilot.research_screening import campaign_runner


def test_source_hash_verification_accepts_repo_relative_paths(tmp_path: Path) -> None:
    source = tmp_path / "alphapilot" / "reference_strategy_research" / "signals.py"
    source.parent.mkdir(parents=True)
    source.write_text("frozen = True\n", encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()

    campaign_runner._verify_source_hashes(
        tmp_path,
        {"implementationSourceHashes": {"alphapilot/reference_strategy_research/signals.py": digest}},
    )


def test_reference_mechanism_uses_reference_replay(monkeypatch) -> None:
    candidate = build_selected_candidates(
        [{"candidateId": "ref_utc_session_range_breakout_1h_v1", "marketHypothesis": "x"}]
    )[0]
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2021-06-01", periods=3, freq="1h", tz="UTC"),
            "open": [100.0, 101.0, 102.0],
            "high": [101.0, 102.0, 103.0],
            "low": [99.0, 100.0, 101.0],
            "close": [100.5, 101.5, 102.5],
            "volume": [1000.0, 1000.0, 1000.0],
        }
    )
    monkeypatch.setattr(campaign_runner, "_read_verified_parquet", lambda row: frame.copy())
    calls = []

    def reference_replay(**kwargs):
        calls.append(kwargs["candidate"].candidateId)
        return []

    monkeypatch.setattr(campaign_runner, "replay_reference_candidate_events", reference_replay)
    monkeypatch.setattr(
        campaign_runner,
        "replay_candidate_events",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("legacy replay must not run")),
    )
    boundary = {
        "holdoutStart": "2022-01-01T00:00:00+00:00",
        "developmentStart": "2020-01-01T00:00:00+00:00",
        "developmentEnd": "2021-01-01T00:00:00+00:00",
        "walkForwardStart": "2021-01-01T00:00:00+00:00",
        "walkForwardEnd": "2022-01-01T00:00:00+00:00",
        "holdoutEnd": "2023-01-01T00:00:00+00:00",
        "walkForwardFolds": [],
    }
    row = {"contentHash": "a" * 64}

    events = campaign_runner._raw_events_for_candidate(
        candidate=candidate,
        candidate_row=candidate.to_dict(),
        instruments=["BTC-USDT-SWAP"],
        ohlcv_catalog={("BTC-USDT-SWAP", "1h"): row},
        funding_catalog={},
        costs={"feeBpsPerSide": 0.0, "slippageBpsPerSide": 0.0, "spreadProxyBpsPerSide": 0.0},
        boundary=boundary,
        include_holdout=False,
    )

    assert events == []
    assert calls == [candidate.candidateId]
