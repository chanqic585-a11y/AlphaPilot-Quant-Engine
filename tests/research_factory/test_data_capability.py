from __future__ import annotations

from alphapilot.research_factory.available_at import available_at_rule
from alphapilot.research_factory.data_capability import (
    build_data_capability_matrix,
    candidate_data_gate,
    summarize_data_capabilities,
)
from alphapilot.research_factory.data_profiles import build_data_profiles
from alphapilot.research_factory.field_semantics import build_field_semantics_registry


def _catalog() -> dict:
    datasets = []
    for instrument in ("BTC-USDT-SWAP", "ETH-USDT-SWAP"):
        for timeframe, rows in (("1h", 50_000), ("4h", 12_500)):
            datasets.append(
                {
                    "datasetId": f"local_{instrument}_{timeframe}",
                    "dataType": "ohlcv",
                    "exchange": "unverified_local_exchange",
                    "marketType": "swap",
                    "symbols": [instrument],
                    "timeframe": timeframe,
                    "startTime": "2020-01-01T00:00:00+00:00",
                    "endTime": "2026-05-01T00:00:00+00:00",
                    "rowCount": rows,
                    "provider": "user_confirmed_local_history",
                    "contentHash": f"hash-{instrument}-{timeframe}",
                    "isPointInTime": False,
                    "isProxy": True,
                }
            )
    return {
        "dataManifestHash": "data_manifest_fixture",
        "datasets": datasets,
        "verified": True,
    }


def _audit() -> dict:
    return {
        "sources": [
            {
                "dataType": "OHLCV",
                "realOrProxy": "proxy",
                "status": "ready_proxy",
                "reason": "fixture",
            },
            {
                "dataType": "Open Interest",
                "realOrProxy": "unavailable",
                "status": "unavailable",
                "reason": "not frozen",
            },
        ]
    }


def test_field_semantics_do_not_mislabel_unverified_volume() -> None:
    registry = build_field_semantics_registry()
    assert registry["close"]["unit"] == "quote_currency_per_base_currency"
    assert registry["reported_volume"]["unit"] == "source_reported_unknown"
    assert registry["quote_turnover"]["status"] == "unavailable_without_verified_semantics"
    assert registry["funding_rate"]["availableAtRule"] == "source_timestamp_plus_publication_delay"


def test_available_at_rules_are_causal() -> None:
    assert available_at_rule("close")["causal"] is True
    assert available_at_rule("close")["rule"] == "candle_close_timestamp"
    assert available_at_rule("orderbook")["historicalStatus"] == "unavailable"


def test_capability_matrix_marks_ready_derived_and_unavailable_fields() -> None:
    matrix = build_data_capability_matrix(_catalog(), _audit())
    fields = {(row["instrumentId"], row["timeframe"], row["field"]): row for row in matrix}

    assert fields[("BTC-USDT-SWAP", "1h", "close")]["status"] == "ready_proxy"
    assert fields[("ETH-USDT-SWAP", "4h", "btc_returns")]["status"] == "derived_proxy"
    assert fields[("BTC-USDT-SWAP", "1h", "open_interest")]["status"] == "unavailable"
    assert fields[("BTC-USDT-SWAP", "1h", "quote_turnover")]["status"] == "unavailable"
    assert all("availableAtRule" in row and "pointInTime" in row for row in matrix)


def test_core_directional_profile_is_ready_without_derivatives_profile() -> None:
    matrix = build_data_capability_matrix(_catalog(), _audit())
    profiles = build_data_profiles(matrix, _catalog())
    by_id = {profile["profileId"]: profile for profile in profiles}

    assert by_id["ohlcv_core_directional_v1"]["status"] == "ready"
    assert by_id["ohlcv_core_directional_v1"]["timeframes"] == ["1h", "4h"]
    assert by_id["future_derivatives_v1"]["status"] == "forward_research_only"
    assert by_id["ohlcv_core_directional_v1"]["profileHash"].startswith("data_profile_")


def test_candidate_gate_blocks_before_candidate_creation_when_required_data_missing() -> None:
    matrix = build_data_capability_matrix(_catalog(), _audit())
    ready = candidate_data_gate(
        matrix,
        required_fields=["open", "high", "low", "close"],
        optional_fields=["reported_volume"],
        timeframes=["1h", "4h"],
        minimum_history_rows=10_000,
        data_profile_id="ohlcv_core_directional_v1",
    )
    blocked = candidate_data_gate(
        matrix,
        required_fields=["open", "high", "low", "close", "open_interest"],
        optional_fields=[],
        timeframes=["1h"],
        minimum_history_rows=10_000,
        data_profile_id="future_derivatives_v1",
    )

    assert ready["status"] == "ready_for_candidate_creation"
    assert ready["minimumCoveragePct"] >= 95.0
    assert blocked["status"] == "data_blocked_before_candidate_creation"
    assert "open_interest" in blocked["missingRequiredFields"]


def test_summary_exposes_machine_readable_gaps() -> None:
    summary = summarize_data_capabilities(
        build_data_capability_matrix(_catalog(), _audit())
    )
    assert summary["directionalEventReady"] is True
    assert "open_interest" in summary["unavailableFields"]
    assert summary["instrumentCount"] == 2
