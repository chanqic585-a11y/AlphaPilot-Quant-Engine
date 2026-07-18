from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from alphapilot.research_factory.automatic_prefilter import (
    PREFILTER_GATE_POLICY,
    build_prefilter_route,
    evaluate_prefilter_events,
)
from alphapilot.research_factory.automatic_preregistration import (
    build_candidate_preregistration,
)
from alphapilot.research_factory.program_v20 import (
    build_candidate_specs,
    build_hypothesis_specs,
)
from alphapilot.research_factory.program_v21 import run_v21_prefilter_and_freeze


def _events(values: list[float]) -> list[dict[str, object]]:
    return [
        {
            "symbol": f"C{index % 4}-USDT-SWAP",
            "entryTimestamp": f"202{index % 3}-{(index % 12) + 1:02d}-01T00:00:00Z",
            "grossR": value + 0.05,
            "costR": 0.05,
            "netR": value,
            "mfeR": max(value, 0.0) + 0.2,
            "maeR": min(value, 0.0) - 0.1,
            "exitReason": "maximum_hold",
        }
        for index, value in enumerate(values)
    ]


def test_v21_prefilter_uses_advisory_r_and_frozen_economic_gates() -> None:
    assert PREFILTER_GATE_POLICY["targetRGateMode"] == "advisory"
    assert PREFILTER_GATE_POLICY["universalTwoRHardGate"] is False

    result = evaluate_prefilter_events(
        candidate_id="candidate-a",
        family_id="family-a",
        base_events=_events([0.4] * 30 + [-0.2] * 10),
        stress_events=_events([0.35] * 30 + [-0.2] * 10),
        benchmark_events=_events([0.1] * 30 + [-0.2] * 10),
    )

    assert result["targetRGateMode"] == "advisory"
    assert "minimumTargetR" not in result["gates"]
    assert result["metrics"]["averageMfeR"] > 0
    assert result["metrics"]["exitReasons"] == {"maximum_hold": 40}


def test_v21_route_caps_six_and_one_candidate_per_family() -> None:
    rows = [
        {
            "candidateId": f"candidate-{index}",
            "familyId": "family-a" if index < 2 else f"family-{index}",
            "passed": True,
            "metrics": {
                "stressProfitFactor": 1.2 + index / 100,
                "benchmarkIncrementNetR": 1.0,
                "maximumDrawdownPct": 10.0,
            },
        }
        for index in range(9)
    ]

    route = build_prefilter_route(rows)

    assert len(route["formalCandidateIds"]) == 6
    selected = [row for row in rows if row["candidateId"] in route["formalCandidateIds"]]
    assert len({row["familyId"] for row in selected}) == 6
    assert route["maximumFormalCandidates"] == 6
    assert route["maximumPerFamily"] == 1
    assert route["formalPassClaimCount"] == 0


def test_v21_zero_survivor_route_is_valid() -> None:
    route = build_prefilter_route(
        [{"candidateId": "failed", "familyId": "family", "passed": False}]
    )

    assert route["formalCandidateIds"] == []
    assert route["terminalRoute"] == "completed_zero_prefilter_survivors"
    assert route["formalRunCount"] == 0
    assert route["releaseCount"] == 0


def test_candidate_preregistration_binds_every_required_hash() -> None:
    candidate = {
        "candidateId": "candidate-a",
        "candidateSpecHash": "candidate-hash",
        "strategyDefinitionHash": "strategy-hash",
        "exitPolicyHash": "exit-hash",
    }
    bindings = {
        "dataProfileHash": "data-profile-hash",
        "dataSnapshotHash": "data-snapshot-hash",
        "universeHash": "universe-hash",
        "splitHash": "split-hash",
        "costHash": "cost-hash",
        "capitalPolicyHash": "capital-hash",
        "benchmarkHash": "benchmark-hash",
        "statisticalPolicyHash": "statistics-hash",
        "gateHash": "gate-hash",
        "runtimeHash": "runtime-hash",
        "ioGuardHash": "io-hash",
        "candidatePanelHash": "panel-hash",
    }

    preregistration = build_candidate_preregistration(
        parent_campaign_id="parent-campaign",
        candidate=candidate,
        implementation_commit="commit-a",
        generated_at="2026-07-18T00:00:00Z",
        bindings=bindings,
    )

    assert preregistration["sourceCandidateId"] == "candidate-a"
    assert preregistration["candidateHash"] == "candidate-hash"
    assert all(preregistration[key] == value for key, value in bindings.items())
    assert preregistration["formalRunCount"] == 0
    assert preregistration["resultReadCount"] == 0
    assert preregistration["preregistrationHash"]


def test_v21_preregistration_fixture_round_trip(tmp_path: Path) -> None:
    payload = build_candidate_preregistration(
        parent_campaign_id="parent-campaign",
        candidate={
            "candidateId": "candidate-a",
            "candidateSpecHash": "candidate-hash",
            "strategyDefinitionHash": "strategy-hash",
            "exitPolicyHash": "exit-hash",
        },
        implementation_commit="commit-a",
        generated_at="2026-07-18T00:00:00Z",
        bindings={
            "dataProfileHash": "a",
            "dataSnapshotHash": "snapshot-a",
            "universeHash": "b",
            "splitHash": "c",
            "costHash": "d",
            "capitalPolicyHash": "e",
            "benchmarkHash": "f",
            "statisticalPolicyHash": "g",
            "gateHash": "h",
            "runtimeHash": "i",
            "ioGuardHash": "j",
            "candidatePanelHash": "k",
        },
    )
    path = tmp_path / "preregistration.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert json.loads(path.read_text(encoding="utf-8")) == payload


def _frames() -> dict[str, dict[str, pd.DataFrame]]:
    dates = pd.date_range("2020-01-01", "2020-06-30 23:00", freq="h", tz="UTC")
    result: dict[str, dict[str, pd.DataFrame]] = {"1h": {}, "4h": {}}
    for symbol_index, symbol in enumerate(("BTC-USDT-SWAP", "ETH-USDT-SWAP")):
        close = (
            100.0
            + symbol_index * 15.0
            + np.linspace(0.0, 45.0, len(dates))
            + np.sin(np.arange(len(dates)) / (11.0 + symbol_index)) * 4.0
        )
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": np.roll(close, 1),
                "high": close + 1.0,
                "low": close - 1.0,
                "close": close,
                "volume": 1_000.0,
            }
        )
        frame.loc[0, "open"] = close[0]
        result["1h"][symbol] = frame
        result["4h"][symbol] = frame.iloc[::4].reset_index(drop=True)
    return result


def test_v21_program_writes_prefilter_and_frozen_preregistrations(tmp_path: Path) -> None:
    reports_root = tmp_path / "reports"
    research_root = tmp_path / "research"
    program_id = "automatic_strategy_demo_test"
    campaign_id = f"{program_id}_campaign_01"
    program_root = reports_root / "automatic_research_program" / program_id
    program_root.mkdir(parents=True)
    (program_root / "program_state.json").write_text(
        json.dumps(
            {
                "schemaVersion": "automatic_strategy_demo_program_state_v1",
                "programId": program_id,
                "baselineCommit": "abc123",
                "programSpecHash": "spec123",
                "stage": "candidates_certified",
                "stageAttempt": 0,
                "activeCampaignIndex": 1,
                "activeCampaignId": campaign_id,
                "previousCheckpoint": "v19",
                "nextAllowedStage": "prefilter_completed",
                "oneShotClaimsConsumed": 0,
                "resultReadCount": 0,
                "terminalRoute": None,
                "humanGateStatus": "not_requested",
                "createdAt": "2026-07-18T00:00:00Z",
                "updatedAt": "2026-07-18T01:00:00Z",
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
                        "universeHash": "universe123",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (program_root / "baseline_identity.json").write_text(
        json.dumps({"dataSnapshotId": "snapshot123"}), encoding="utf-8"
    )
    hypotheses, _, _ = build_hypothesis_specs(
        historical_family_names=[], source_references=[]
    )
    candidates = build_candidate_specs(hypotheses)
    (program_root / "candidate_inventory.json").write_text(
        json.dumps({"candidates": candidates}), encoding="utf-8"
    )
    (program_root / "candidate_structural_certification.json").write_text(
        json.dumps(
            {
                "certifications": [
                    {"candidateId": row["candidateId"], "status": "certified"}
                    for row in candidates
                ]
            }
        ),
        encoding="utf-8",
    )

    result = run_v21_prefilter_and_freeze(
        reports_root=reports_root,
        research_root=research_root,
        program_id=program_id,
        generated_at="2026-07-18T02:00:00Z",
        implementation_commit="commit-v21",
        frames=_frames(),
    )

    campaign_root = program_root / "campaigns" / campaign_id
    assert result["status"] == "completed"
    assert result["candidateCount"] == 16
    assert result["formalRunCount"] == 0
    assert result["resultReadCount"] == 0
    assert (campaign_root / "prefilter_results.json").is_file()
    assert (campaign_root / "prefilter_metric_matrix.csv").is_file()
    assert (campaign_root / "candidate_daily_return_panel_plan.json").is_file()
    assert (campaign_root / "campaign_multiple_testing_scope.json").is_file()
    assert (campaign_root / "parent_campaign_preregistration.json").is_file()
    locked = json.loads(
        (campaign_root / "future_locked_oos_identity.json").read_text(encoding="utf-8")
    )
    assert locked["accessCount"] == 0
    preregistrations = list((research_root / "preregistrations").glob("*.json"))
    assert len(preregistrations) == result["formalCandidateCount"]
    state = json.loads((program_root / "program_state.json").read_text(encoding="utf-8"))
    assert state["stage"] == "prefilter_completed"
    assert state["resultReadCount"] == 0
