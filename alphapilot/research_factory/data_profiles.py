"""Immutable data profiles frozen before hypothesis generation."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.research_factory.data_capability import candidate_data_gate


def _profile_hash(profile: dict[str, Any]) -> str:
    return stable_hash(profile, prefix="data_profile")


def build_data_profiles(
    matrix: list[dict[str, Any]],
    catalog: dict[str, Any],
) -> list[dict[str, Any]]:
    datasets = list(catalog.get("datasets") or [])
    instruments = sorted(
        {
            str((dataset.get("symbols") or [dataset.get("instrumentId")])[0])
            for dataset in datasets
            if dataset.get("dataType") == "ohlcv"
        }
    )
    universe_hash = stable_hash(instruments, prefix="universe")
    starts = [str(item["startTime"]) for item in datasets if item.get("dataType") == "ohlcv"]
    ends = [str(item["endTime"]) for item in datasets if item.get("dataType") == "ohlcv"]
    common_cutoff = {"start": max(starts) if starts else None, "end": min(ends) if ends else None}

    core_gate = candidate_data_gate(
        matrix,
        required_fields=["open", "high", "low", "close"],
        optional_fields=["reported_volume"],
        timeframes=["1h", "4h"],
        minimum_history_rows=10_000,
        data_profile_id="ohlcv_core_directional_v1",
    )
    core = {
        "profileId": "ohlcv_core_directional_v1",
        "strategyType": "directional_event",
        "universeHash": universe_hash,
        "fieldSet": ["open", "high", "low", "close"],
        "optionalFields": ["reported_volume"],
        "coverage": core_gate["coverageByRequiredField"],
        "timeframes": ["1h", "4h"],
        "commonCutoff": common_cutoff,
        "availableAt": "candle_close_timestamp",
        "knownLimitations": [
            "exchange provenance is unverified",
            "reported volume unit is not independently certified",
            "PIT listing history is incomplete",
        ],
        "status": "ready" if core_gate["status"] == "ready_for_candidate_creation" else "blocked",
    }
    core["profileHash"] = _profile_hash(core)

    turnover = {
        "profileId": "ohlcv_verified_turnover_v1",
        "strategyType": "directional_event",
        "universeHash": universe_hash,
        "fieldSet": ["open", "high", "low", "close", "quote_turnover"],
        "coverage": {},
        "timeframes": ["1h", "4h"],
        "commonCutoff": common_cutoff,
        "availableAt": "candle_close_timestamp",
        "knownLimitations": ["quote turnover semantics are not verified in the frozen catalog"],
        "status": "blocked",
    }
    turnover["profileHash"] = _profile_hash(turnover)

    derivatives = {
        "profileId": "future_derivatives_v1",
        "strategyType": "directional_event",
        "universeHash": universe_hash,
        "fieldSet": ["funding_rate", "open_interest", "basis", "liquidation", "orderbook"],
        "coverage": {},
        "timeframes": ["event"],
        "commonCutoff": common_cutoff,
        "availableAt": "source_timestamp_plus_publication_delay",
        "knownLimitations": [
            "open interest, basis, liquidation and orderbook are unavailable historically",
            "must not generate a formal historical candidate from this profile",
        ],
        "status": "forward_research_only",
    }
    derivatives["profileHash"] = _profile_hash(derivatives)
    return [core, turnover, derivatives]
