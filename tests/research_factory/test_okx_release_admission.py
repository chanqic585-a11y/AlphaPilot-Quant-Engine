from __future__ import annotations

import pytest

from alphapilot.research_factory.okx_release_admission import (
    build_immutable_release,
    build_okx_same_exchange_profile,
    build_release_approval_request,
    evaluate_portability_audit,
    validate_exact_release_approval,
)


def _okx_receipts() -> dict[str, dict[str, object]]:
    return {
        "ohlcv": {"verified": True, "availableAt": "candle_close", "hash": "o"},
        "quote_turnover": {
            "verified": True,
            "availableAt": "candle_close",
            "hash": "q",
        },
        "funding": {
            "verified": True,
            "availableAt": "funding_timestamp",
            "hash": "f",
        },
        "instrument_state": {
            "verified": True,
            "availableAt": "snapshot_timestamp",
            "hash": "s",
        },
        "exact_usdt_swap_identity": {
            "verified": True,
            "availableAt": "listing_snapshot",
            "hash": "i",
        },
    }


def test_okx_same_exchange_profile_requires_every_frozen_field() -> None:
    ready = build_okx_same_exchange_profile(
        candidate_id="candidate-1",
        instrument_ids=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
        field_receipts=_okx_receipts(),
        immutable_manifest_hash="manifest-1",
    )
    assert ready["status"] == "ready"
    assert ready["profileHash"]

    missing = _okx_receipts()
    del missing["funding"]
    blocked = build_okx_same_exchange_profile(
        candidate_id="candidate-1",
        instrument_ids=["BTC-USDT-SWAP"],
        field_receipts=missing,
        immutable_manifest_hash="manifest-1",
    )
    assert blocked["status"] == "blocked_okx_data"
    assert "missing:funding" in blocked["blockers"]


def test_portability_uses_frozen_thresholds_and_blocks_failed_metrics() -> None:
    thresholds = {
        "minimumSignalTimestampParityPct": 95.0,
        "minimumEventOverlapPct": 80.0,
        "minimumReturnCorrelation": 0.8,
        "minimumDirectionParityPct": 95.0,
        "maximumCapacityDifferencePct": 15.0,
        "maximumFundingDifferenceR": 0.1,
        "maximumCostDifferenceR": 0.1,
    }
    passed = evaluate_portability_audit(
        candidate_id="candidate-1",
        source_exchange="binance",
        target_exchange="okx",
        metrics={
            "signalTimestampParityPct": 99.0,
            "eventOverlapPct": 90.0,
            "returnCorrelation": 0.9,
            "directionParityPct": 100.0,
            "capacityDifferencePct": 5.0,
            "fundingDifferenceR": 0.02,
            "costDifferenceR": 0.03,
        },
        frozen_thresholds=thresholds,
        thresholds_frozen_before_results=True,
    )
    assert passed["status"] == "passed"
    assert passed["thresholdHash"]

    failed = evaluate_portability_audit(
        candidate_id="candidate-1",
        source_exchange="binance",
        target_exchange="okx",
        metrics={**passed["metrics"], "eventOverlapPct": 20.0},
        frozen_thresholds=thresholds,
        thresholds_frozen_before_results=True,
    )
    assert failed["status"] == "blocked_okx_portability"
    assert "minimumEventOverlapPct" in failed["failedThresholds"]


def test_release_requires_pass_and_okx_or_portability_evidence() -> None:
    with pytest.raises(ValueError, match="release_candidate_not_passed"):
        build_immutable_release(
            campaign_id="campaign-1",
            candidate={"candidateId": "candidate-1", "candidateHash": "hash-1"},
            result_class="formal_economic_failed",
            okx_profile={"status": "ready", "profileHash": "profile-1"},
            portability_audit=None,
            evidence_summary={"fiveFold": "passed"},
            risk_overlay={"riskOverlayHash": "risk-1"},
        )

    with pytest.raises(ValueError, match="release_okx_admission_not_passed"):
        build_immutable_release(
            campaign_id="campaign-1",
            candidate={"candidateId": "candidate-1", "candidateHash": "hash-1"},
            result_class="formal_pass",
            okx_profile={"status": "blocked_okx_data"},
            portability_audit={"status": "blocked_okx_portability"},
            evidence_summary={"fiveFold": "passed"},
            risk_overlay={"riskOverlayHash": "risk-1"},
        )


def test_immutable_release_stops_at_exact_hash_approval() -> None:
    release = build_immutable_release(
        campaign_id="campaign-1",
        candidate={"candidateId": "candidate-1", "candidateHash": "hash-1"},
        result_class="formal_pass",
        okx_profile={"status": "ready", "profileHash": "profile-1"},
        portability_audit=None,
        evidence_summary={
            "fiveFold": "passed",
            "costStress": "passed",
            "maximumDrawdownPct": 8.0,
            "benchmarkIncrementNetR": 2.0,
            "statistics": "passed",
        },
        risk_overlay={"riskOverlayHash": "risk-1"},
    )
    request = build_release_approval_request(release)

    assert release["approved"] is False
    assert release["demoArm"] is False
    assert release["orderCount"] == 0
    assert request["status"] == "blocked_waiting_exact_release_approval"
    assert request["releaseHash"] == release["releaseHash"]
    assert validate_exact_release_approval(
        release=release,
        supplied_release_hash="wrong-hash",
    ) is False
    assert validate_exact_release_approval(
        release=release,
        supplied_release_hash=release["releaseHash"],
    ) is True
