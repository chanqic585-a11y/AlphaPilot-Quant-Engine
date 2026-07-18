from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alphapilot.research_factory.generated_candidate_adapter import (
    GeneratedDirectionalEventAdapter,
)
from alphapilot.formal_validation.candidate_adapters import get_candidate_adapter
from alphapilot.research_factory.program_v20 import (
    build_candidate_specs,
    build_hypothesis_specs,
    run_v20_candidate_generation,
)


def _frames() -> dict[str, pd.DataFrame]:
    index = pd.date_range("2024-01-01", periods=500, freq="h", tz="UTC")
    base = pd.Series(range(500), dtype=float) * 0.05 + 100.0
    wave = pd.Series([(-1.0 if value % 17 == 0 else 0.2) for value in range(500)])
    btc = pd.DataFrame(
        {
            "date": index,
            "open": base,
            "high": base + 1.0,
            "low": base - 1.0,
            "close": base + wave,
            "volume": 1_000.0,
        }
    )
    eth = btc.copy()
    eth["close"] = btc["close"] * 0.55 + pd.Series(
        [(-3.0 if value % 29 == 0 else 0.0) for value in range(500)]
    )
    eth["open"] = eth["close"].shift(1).fillna(eth["close"])
    eth["high"] = eth[["open", "close"]].max(axis=1) + 0.5
    eth["low"] = eth[["open", "close"]].min(axis=1) - 0.5
    return {"BTC-USDT-SWAP": btc, "ETH-USDT-SWAP": eth}


def test_v20_builds_eight_materially_distinct_hypotheses() -> None:
    hypotheses, novelty, overlap = build_hypothesis_specs(
        historical_family_names=["EMA threshold trend", "RSI threshold rebound"],
        source_references=["reports/full_archived_strategy_inventory.json"],
    )

    assert len(hypotheses) == 8
    assert len({row["familyId"] for row in hypotheses}) == 8
    assert all(row["strategyType"] == "directional_event" for row in hypotheses)
    assert all(row["timeframe"] in {"1h", "4h"} for row in hypotheses)
    assert all(row["falsificationCondition"] for row in hypotheses)
    assert all(row["historicalOverlap"]["classification"] != "threshold_only_duplicate" for row in hypotheses)
    assert len(novelty) == 8
    assert overlap["historicalFamilySemanticDedupPassed"] is True


def test_v20_candidate_budget_and_advisory_r_contract() -> None:
    hypotheses, _, _ = build_hypothesis_specs(
        historical_family_names=[], source_references=[]
    )
    candidates = build_candidate_specs(hypotheses)

    assert len(candidates) == 16
    assert max(
        sum(row["familyId"] == family for row in candidates)
        for family in {row["familyId"] for row in candidates}
    ) == 2
    assert all(row["coreSetupCount"] == 1 for row in candidates)
    assert all(row["coreEngineChangedForCandidate"] is False for row in candidates)
    assert all(row["GatePolicy"]["universalTwoRHardGate"] is False for row in candidates)
    assert all(row["requiredDataProfile"] == "ohlcv_core_directional_v1" for row in candidates)


def test_generated_adapter_is_candidate_neutral_and_fixture_parity_passes() -> None:
    hypotheses, _, _ = build_hypothesis_specs(
        historical_family_names=[], source_references=[]
    )
    candidate = build_candidate_specs(hypotheses)[0]
    adapter = GeneratedDirectionalEventAdapter(candidate_id=candidate["candidateId"])

    signals = adapter.load_signals(candidate=candidate, frames=_frames())
    replay = adapter.replay(candidate=candidate, frames=_frames(), round_trip_cost_rate=0.001)
    parity, reference, translated = adapter.run_fixture_parity(candidate=candidate)

    assert adapter.adapter_id == "generated_directional_event_adapter"
    assert all(row["candidateId"] == candidate["candidateId"] for row in signals)
    assert all(row["structuralOnly"] is True for row in signals)
    assert all("netR" in row for row in replay)
    assert all("mfeR" in row and "maeR" in row for row in replay)
    assert parity["status"] == "passed"
    assert reference == translated
    assert isinstance(
        get_candidate_adapter(candidate["candidateId"]),
        GeneratedDirectionalEventAdapter,
    )


def test_every_generated_candidate_has_positive_fixture_events() -> None:
    hypotheses, _, _ = build_hypothesis_specs(
        historical_family_names=[], source_references=[]
    )

    for candidate in build_candidate_specs(hypotheses):
        adapter = GeneratedDirectionalEventAdapter(candidate_id=candidate["candidateId"])
        parity, reference, translated = adapter.run_fixture_parity(candidate=candidate)

        assert parity["status"] == "passed", candidate["candidateId"]
        assert parity["referenceEventCount"] > 0, candidate["candidateId"]
        assert reference == translated


def test_v20_program_writes_candidate_evidence_and_advances_state(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    program_id = "automatic_strategy_demo_test"
    program_root = reports_root / "automatic_research_program" / program_id
    program_root.mkdir(parents=True)
    (program_root / "program_state.json").write_text(
        json.dumps(
            {
                "schemaVersion": "automatic_strategy_demo_program_state_v1",
                "programId": program_id,
                "baselineCommit": "abc123",
                "programSpecHash": "spec123",
                "stage": "data_capability_ready",
                "stageAttempt": 0,
                "activeCampaignIndex": 0,
                "activeCampaignId": None,
                "previousCheckpoint": "baseline_frozen",
                "nextAllowedStage": "hypotheses_frozen",
                "oneShotClaimsConsumed": 0,
                "resultReadCount": 0,
                "terminalRoute": None,
                "humanGateStatus": "not_requested",
                "createdAt": "2026-07-18T00:00:00Z",
                "updatedAt": "2026-07-18T00:00:00Z",
            }
        ),
        encoding="utf-8",
    )
    (program_root / "data_profiles.json").write_text(
        json.dumps(
            {
                "profiles": [
                    {
                        "profileId": "ohlcv_core_directional_v1",
                        "status": "ready",
                        "profileHash": "profile123",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    inventory = tmp_path / "inventory.json"
    inventory.write_text(
        json.dumps(
            {
                "strategies": [
                    {"strategyFamily": "EMA threshold trend"},
                    {"strategyFamily": "RSI threshold rebound"},
                ]
            }
        ),
        encoding="utf-8",
    )
    negative_rules = tmp_path / "negative_rules.json"
    negative_rules.write_text(json.dumps({"rules": []}), encoding="utf-8")

    result = run_v20_candidate_generation(
        reports_root=reports_root,
        program_id=program_id,
        generated_at="2026-07-18T01:00:00Z",
        historical_inventory_path=inventory,
        negative_rules_path=negative_rules,
        frames=_frames(),
    )

    assert result["status"] == "completed"
    assert result["hypothesisCount"] == 8
    assert result["candidateCount"] == 16
    assert result["certifiedCandidateCount"] > 0
    state = json.loads((program_root / "program_state.json").read_text(encoding="utf-8"))
    assert state["stage"] == "candidates_certified"
    assert state["nextAllowedStage"] == "prefilter_completed"
    assert (program_root / "hypothesis_inventory.json").is_file()
    assert (program_root / "candidate_inventory.json").is_file()
    assert (program_root / "candidate_structural_certification.json").is_file()
