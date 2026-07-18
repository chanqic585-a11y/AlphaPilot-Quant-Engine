from __future__ import annotations

import pandas as pd
import pytest

from alphapilot.research_factory.data_readiness_layers import (
    READINESS_LAYER_ORDER,
    build_layered_data_readiness,
)
from alphapilot.research_factory.eligibility_window import (
    build_causal_eligibility_window,
    classify_event_dispositions,
)


def _timestamps(count: int = 8) -> list[str]:
    return [
        value.isoformat()
        for value in pd.date_range("2026-01-01", periods=count, freq="1h", tz="UTC")
    ]


def test_causal_window_uses_the_slowest_field_lookback() -> None:
    window = build_causal_eligibility_window(
        instrument_id="BTC-USDT-SWAP",
        timeframe="1h",
        data_profile_id="formal_profile_v1",
        candle_timestamps=_timestamps(),
        field_specs={
            "close": {
                "fieldFirstAvailableAt": _timestamps()[0],
                "requiredLookbackBars": 2,
                "semanticsVerified": True,
                "availableAtRule": "candle_close_timestamp",
            },
            "quoteTurnover": {
                "fieldFirstAvailableAt": _timestamps()[1],
                "requiredLookbackBars": 4,
                "semanticsVerified": True,
                "availableAtRule": "candle_close_timestamp",
            },
        },
    )

    assert window["schemaVersion"] == "causal_eligibility_window_v1"
    assert window["firstEligibleSignalTimestamp"] == _timestamps()[4]
    assert window["lastEligibleSignalTimestamp"] == _timestamps()[-1]
    assert window["windowHash"]


def test_event_dispositions_conserve_raw_events_and_cover_capacity() -> None:
    timestamps = _timestamps()
    window = build_causal_eligibility_window(
        instrument_id="BTC-USDT-SWAP",
        timeframe="1h",
        data_profile_id="formal_profile_v1",
        candle_timestamps=timestamps,
        field_specs={
            "close": {
                "fieldFirstAvailableAt": timestamps[0],
                "requiredLookbackBars": 2,
                "semanticsVerified": True,
                "availableAtRule": "candle_close_timestamp",
            }
        },
    )
    events = [
        {
            "eventId": "eligible",
            "instrumentId": "BTC-USDT-SWAP",
            "signalTimestamp": timestamps[2],
            "entryTimestamp": timestamps[3],
            "dataReadMaxTimestamp": timestamps[2],
            "semanticsVerified": True,
            "capacityInputsComplete": True,
        },
        {
            "eventId": "too-early",
            "instrumentId": "BTC-USDT-SWAP",
            "signalTimestamp": timestamps[0],
            "entryTimestamp": timestamps[1],
            "dataReadMaxTimestamp": timestamps[0],
            "semanticsVerified": True,
            "capacityInputsComplete": False,
        },
        {
            "eventId": "not-frozen",
            "instrumentId": "DOGE-USDT-SWAP",
            "signalTimestamp": timestamps[2],
            "entryTimestamp": timestamps[3],
            "dataReadMaxTimestamp": timestamps[2],
            "semanticsVerified": True,
            "capacityInputsComplete": True,
        },
        {
            "eventId": "after-cutoff",
            "instrumentId": "BTC-USDT-SWAP",
            "signalTimestamp": timestamps[7],
            "entryTimestamp": timestamps[7],
            "dataReadMaxTimestamp": timestamps[7],
            "semanticsVerified": True,
            "capacityInputsComplete": True,
        },
        {
            "eventId": "bad-semantics",
            "instrumentId": "BTC-USDT-SWAP",
            "signalTimestamp": timestamps[3],
            "entryTimestamp": timestamps[4],
            "dataReadMaxTimestamp": timestamps[3],
            "semanticsVerified": False,
            "capacityInputsComplete": True,
        },
    ]

    result = classify_event_dispositions(
        raw_events=events,
        eligibility_windows={"BTC-USDT-SWAP": window},
        frozen_universe={"BTC-USDT-SWAP"},
        common_cutoff=timestamps[6],
    )

    assert result["rawSignalCount"] == 5
    assert result["eligibleCandidateEventCount"] == 1
    assert sum(result["dispositionCounts"].values()) == 5
    assert result["eventConservationPassed"] is True
    assert result["eligibleCapacityCoveragePct"] == 100.0
    assert result["unclassifiedEventCount"] == 0
    assert result["postEntryReadCount"] == 0
    assert {row["disposition"] for row in result["events"]} == {
        "eligible_candidate_event",
        "excluded_before_capacity_history_ready",
        "excluded_after_common_cutoff",
        "excluded_missing_verified_semantics",
        "excluded_instrument_not_in_frozen_universe",
    }


def test_event_disposition_rejects_post_entry_reads() -> None:
    timestamps = _timestamps()
    with pytest.raises(ValueError, match="post_entry_data_read"):
        classify_event_dispositions(
            raw_events=[
                {
                    "eventId": "leaky",
                    "instrumentId": "BTC-USDT-SWAP",
                    "signalTimestamp": timestamps[2],
                    "entryTimestamp": timestamps[3],
                    "dataReadMaxTimestamp": timestamps[4],
                    "semanticsVerified": True,
                    "capacityInputsComplete": True,
                }
            ],
            eligibility_windows={
                "BTC-USDT-SWAP": {
                    "firstEligibleSignalTimestamp": timestamps[1],
                    "lastEligibleSignalTimestamp": timestamps[-1],
                }
            },
            frozen_universe={"BTC-USDT-SWAP"},
            common_cutoff=timestamps[6],
        )


def test_layered_readiness_is_monotonic_and_formal_ready_is_explicit() -> None:
    fields = {
        name: {
            "semanticsVerified": True,
            "coveragePct": 100.0,
            "availableAtRule": "candle_close_timestamp",
            "firstEligibleSignalTimestamp": "2026-01-01T04:00:00+00:00",
        }
        for name in ("close", "rank", "turnover", "cost", "benchmark", "instrumentState")
    }
    layer_specs = {
        "signal_ready": {"requiredFields": ["close"]},
        "ranking_ready": {"requiredFields": ["rank"]},
        "capacity_ready": {"requiredFields": ["turnover"]},
        "prefilter_ready": {"requiredFields": ["cost"]},
        "formal_ready": {"requiredFields": ["benchmark"]},
        "release_ready": {"requiredFields": ["instrumentState"]},
        "demo_ready": {"requiredFields": ["instrumentState"]},
    }

    result = build_layered_data_readiness(
        candidate_id="candidate-1",
        layer_specs=layer_specs,
        field_receipts=fields,
        minimum_coverage_pct=100.0,
    )

    assert [row["layer"] for row in result["layers"]] == list(READINESS_LAYER_ORDER)
    assert all(row["ready"] for row in result["layers"])
    assert result["formalReady"] is True
    assert result["demoReady"] is True
    assert result["contractHash"]


def test_missing_ranking_semantics_blocks_every_later_layer() -> None:
    fields = {
        "close": {
            "semanticsVerified": True,
            "coveragePct": 100.0,
            "availableAtRule": "candle_close_timestamp",
            "firstEligibleSignalTimestamp": "2026-01-01T00:00:00+00:00",
        },
        "rank": {
            "semanticsVerified": False,
            "coveragePct": 100.0,
            "availableAtRule": "candle_close_timestamp",
            "firstEligibleSignalTimestamp": "2026-01-01T00:00:00+00:00",
        },
    }
    layer_specs = {
        layer: {"requiredFields": ["close" if layer == "signal_ready" else "rank"]}
        for layer in READINESS_LAYER_ORDER
    }

    result = build_layered_data_readiness(
        candidate_id="candidate-2",
        layer_specs=layer_specs,
        field_receipts=fields,
        minimum_coverage_pct=100.0,
    )

    readiness = {row["layer"]: row["ready"] for row in result["layers"]}
    assert readiness["signal_ready"] is True
    assert all(not readiness[layer] for layer in READINESS_LAYER_ORDER[1:])
    assert result["formalReady"] is False

