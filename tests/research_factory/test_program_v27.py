from __future__ import annotations

from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from alphapilot.formal_validation.candidate_ranking_contract import (
    validate_candidate_ranking_contract,
)
from alphapilot.formal_validation.candidate_ranking_evidence import (
    materialize_candidate_ranking_evidence,
)
from alphapilot.research_factory.generated_candidate_adapter import (
    GeneratedDirectionalEventAdapter,
)
from alphapilot.research_factory.program_v27 import (
    build_v27_candidate_specs,
    build_v27_fixed_universe_semantics_matrix,
    build_v27_data_readiness_receipt,
    build_v27_hypothesis_specs,
    certify_v27_capacity_completeness,
    materialize_v27_ranking_rows,
    run_v27_candidate_research,
)


def _matrix(timeframe: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for instrument in ("BTC-USDT-SWAP", "ETH-USDT-SWAP"):
        for field in ("open", "high", "low", "close"):
            rows.append(
                {
                    "instrumentId": instrument,
                    "timeframe": timeframe,
                    "field": field,
                    "status": "ready_proxy",
                    "coveragePct": 100.0,
                    "rowCount": 20_000,
                    "causal": True,
                    "pointInTime": True,
                    "availableAtRule": "candle_close_timestamp",
                    "hash": f"{instrument}-{timeframe}-{field}",
                }
            )
    return rows


def _capacity_profile(timeframe: str) -> dict[str, object]:
    instruments = ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    return {
        "profileId": f"verified-capacity-{timeframe}",
        "profileHash": f"capacity-{timeframe}",
        "status": "ready",
        "requiredTimeframes": [timeframe],
        "instrumentSet": instruments,
        "eligibleInstruments": instruments,
        "turnoverSemanticsByInstrument": {
            instrument: {
                timeframe: {
                    "semanticType": "exact_quote_turnover",
                    "route": "A",
                    "verificationHash": f"verify-{instrument}-{timeframe}",
                    "contentHash": f"content-{instrument}-{timeframe}",
                }
            }
            for instrument in instruments
        },
    }


def _frames() -> dict[str, pd.DataFrame]:
    count = 1_000
    dates = pd.date_range("2020-01-01", periods=count, freq="h", tz="UTC")
    result: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(("BTC-USDT-SWAP", "ETH-USDT-SWAP")):
        base = pd.Series(range(count), dtype=float) * 0.02 + 100.0 + offset * 10.0
        wave = pd.Series([((index % 31) - 15) * 0.18 for index in range(count)])
        close = base + wave
        close.iloc[220] -= 8.0
        close.iloc[221] += 6.0
        close.iloc[520] += 9.0
        close.iloc[521] -= 7.0
        open_ = close.shift(1).fillna(close.iloc[0])
        result[symbol] = pd.DataFrame(
            {
                "date": dates,
                "open": open_,
                "high": pd.concat([open_, close], axis=1).max(axis=1) + 0.8,
                "low": pd.concat([open_, close], axis=1).min(axis=1) - 0.8,
                "close": close,
                "volume": 1_000_000.0 + (pd.Series(range(count)) % 17) * 50_000.0,
            }
        )
    return result


def test_v27_data_readiness_blocks_before_candidate_identity() -> None:
    blocked_profile = deepcopy(_capacity_profile("1h"))
    blocked_profile["status"] = "blocked"

    receipt = build_v27_data_readiness_receipt(
        timeframe="1h",
        matrix=_matrix("1h"),
        capacity_profile=blocked_profile,
    )

    assert receipt["status"] == "data_blocked_before_candidate_creation"
    assert receipt["candidateIdCreationCount"] == 0
    assert receipt["candidateTrialBudgetConsumed"] == 0
    assert receipt["formalBudgetConsumed"] == 0
    assert "capacity_coverage_below_100_pct" in receipt["blockers"]

    hypotheses = build_v27_hypothesis_specs(source_references=[])
    with pytest.raises(ValueError, match="data_blocked_before_candidate_creation"):
        build_v27_candidate_specs(hypotheses, {"1h": receipt, "4h": receipt})


def test_v27_fixed_universe_semantics_preserve_source_pit_limitation() -> None:
    source = _matrix("1h")
    for row in source:
        row["pointInTime"] = False

    derived = build_v27_fixed_universe_semantics_matrix(
        timeframe="1h",
        source_matrix=source,
        frames=_frames(),
        start="2020-01-01T00:00:00Z",
        end_exclusive="2020-02-11T16:00:00Z",
    )

    assert len(derived) == 8
    assert all(row["pointInTime"] is True for row in derived)
    assert all(row["sourcePointInTime"] is False for row in derived)
    assert all(row["universeMembershipPIT"] == "not_applicable_fixed_universe" for row in derived)
    assert all(row["pointInTimeScope"] == "closed_candle_availability_only" for row in derived)


def test_v27_candidate_factory_is_bounded_and_uses_candidate_owned_ranking() -> None:
    receipts = {
        timeframe: build_v27_data_readiness_receipt(
            timeframe=timeframe,
            matrix=_matrix(timeframe),
            capacity_profile=_capacity_profile(timeframe),
        )
        for timeframe in ("1h", "4h")
    }
    hypotheses = build_v27_hypothesis_specs(
        source_references=["reports/full_archived_strategy_inventory.json"]
    )
    candidates = build_v27_candidate_specs(hypotheses, receipts)

    assert len(hypotheses) == 4
    assert len(candidates) == 8
    assert len({row["familyId"] for row in candidates}) == 4
    assert max(
        sum(row["familyId"] == family for row in candidates)
        for family in {row["familyId"] for row in candidates}
    ) == 2
    assert all(row["strategyType"] == "directional_event" for row in candidates)
    assert all(row["coreSetupCount"] == 1 for row in candidates)
    assert all(row["timeframe"] in {"1h", "4h"} for row in candidates)
    assert not {
        "trend_pullback_continuation",
        "trend_failure_reversal",
        "volatility_compression_release",
    } & {row["familyId"] for row in candidates}
    assert all(
        validate_candidate_ranking_contract(row["candidateRankingContract"])["status"]
        == "valid"
        for row in candidates
    )


def test_v27_new_setups_have_independent_translation_parity() -> None:
    receipts = {
        timeframe: build_v27_data_readiness_receipt(
            timeframe=timeframe,
            matrix=_matrix(timeframe),
            capacity_profile=_capacity_profile(timeframe),
        )
        for timeframe in ("1h", "4h")
    }
    candidates = build_v27_candidate_specs(
        build_v27_hypothesis_specs(source_references=[]), receipts
    )

    for candidate in candidates:
        adapter = GeneratedDirectionalEventAdapter(candidate_id=candidate["candidateId"])
        parity, reference, translated = adapter.run_fixture_parity(candidate=candidate)
        assert parity["status"] == "passed", candidate["candidateId"]
        assert reference, candidate["candidateId"]
        assert reference == translated
        assert all(row["instrumentId"] == row["symbol"] for row in reference)


def test_v27_ranking_and_capacity_certificates_are_complete() -> None:
    receipts = {
        timeframe: build_v27_data_readiness_receipt(
            timeframe=timeframe,
            matrix=_matrix(timeframe),
            capacity_profile=_capacity_profile(timeframe),
        )
        for timeframe in ("1h", "4h")
    }
    candidate = build_v27_candidate_specs(
        build_v27_hypothesis_specs(source_references=[]), receipts
    )[0]
    adapter = GeneratedDirectionalEventAdapter(candidate_id=candidate["candidateId"])
    signals = list(adapter.load_signals(candidate=candidate, frames=_frames()))
    ranking_rows = materialize_v27_ranking_rows(
        candidate=candidate,
        frames=_frames(),
        signals=signals,
    )
    records, ranking = materialize_candidate_ranking_evidence(
        signals=signals,
        ranking_rows=ranking_rows,
        contract=candidate["candidateRankingContract"],
    )

    assert signals
    assert len(records) == len(signals)
    assert ranking["status"] == "passed"
    assert ranking["requiredRankingAvailabilityPct"] >= 95.0
    assert ranking["postEntryReadCount"] == 0

    capacity = certify_v27_capacity_completeness(
        {
            "certificationStatus": "passed",
            "assignedEventCount": len(signals),
            "capacityInputAvailableCount": len(signals),
            "capacityInputUnavailableCount": 0,
            "economicResultReadCount": 0,
        }
    )
    assert capacity["status"] == "passed"

    incomplete = certify_v27_capacity_completeness(
        {
            "certificationStatus": "passed",
            "assignedEventCount": len(signals),
            "capacityInputAvailableCount": len(signals) - 1,
            "capacityInputUnavailableCount": 1,
            "economicResultReadCount": 0,
        }
    )
    assert incomplete["status"] == "failed"


def test_v27_runner_writes_bounded_evidence_and_keeps_formal_budget_zero(
    tmp_path: Path,
) -> None:
    frames = _frames()
    receipts = {
        timeframe: build_v27_data_readiness_receipt(
            timeframe=timeframe,
            matrix=_matrix(timeframe),
            capacity_profile=_capacity_profile(timeframe),
        )
        for timeframe in ("1h", "4h")
    }
    profiles = {
        timeframe: _capacity_profile(timeframe) for timeframe in ("1h", "4h")
    }

    summary = run_v27_candidate_research(
        reports_root=tmp_path,
        program_id="v27-test-program",
        generated_at="2026-07-18T00:00:00Z",
        implementation_commit="0123456789abcdef",
        frames={"1h": frames, "4h": frames},
        receipts=receipts,
        capacity_profiles=profiles,
        source_references=["docs/v27-hypothesis-source.md"],
        data_access_report={"lockedOosContentReadCount": 0},
        candidate_semantics_matrix=[],
    )

    assert summary["candidateCount"] == 8
    assert summary["formalRunCount"] == 0
    assert summary["resultReadCount"] == 0
    assert summary["lockedOosReadCount"] == 0
    assert summary["releaseCount"] == 0
    assert summary["nextStage"] in {
        "v28_formal_validation",
        "completed_zero_prefilter_survivors",
    }

    root = tmp_path / "automatic_strategy_to_demo" / "v27-test-program" / "v27"
    for name in (
        "data_readiness_receipts.json",
        "data_access_report.json",
        "candidate_semantics_matrix.json",
        "capacity_profiles.json",
        "hypothesis_inventory.json",
        "candidate_inventory.json",
        "candidate_structural_certification.json",
        "candidate_ranking_certification.json",
        "candidate_capacity_certification.json",
        "prefilter_results.json",
        "prefilter_route.json",
        "v27_summary.json",
        "artifact_manifest.json",
    ):
        assert (root / name).is_file(), name
