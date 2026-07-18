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


def build_verified_capacity_profile(
    *,
    volume_audit: dict[str, Any],
    capacity_capability: list[dict[str, Any]],
    required_timeframes: list[str],
    minimum_history_rows: int,
    required_instruments: list[str] | None = None,
) -> dict[str, Any]:
    """Freeze a capacity profile using only semantic and coverage evidence."""

    required = sorted(set(str(value) for value in required_timeframes))
    discovered_instruments = sorted(
        {str(row.get("instrumentId") or "") for row in capacity_capability}
        - {""}
    )
    instruments = (
        sorted(set(str(value) for value in required_instruments))
        if required_instruments is not None
        else discovered_instruments
    )
    eligible: list[str] = []
    excluded: list[dict[str, Any]] = []
    semantics: dict[str, dict[str, dict[str, Any]]] = {}
    coverage: dict[str, dict[str, dict[str, Any]]] = {}
    for instrument in instruments:
        instrument_rows = [
            row for row in capacity_capability if row["instrumentId"] == instrument
        ]
        by_timeframe = {row["timeframe"]: row for row in instrument_rows}
        missing = [
            timeframe
            for timeframe in required
            if timeframe not in by_timeframe
            or by_timeframe[timeframe]["status"] != "ready"
            or int(by_timeframe[timeframe]["rowCount"]) < int(minimum_history_rows)
        ]
        if missing:
            excluded.append(
                {
                    "instrumentId": instrument,
                    "reason": "capacity_data_not_ready",
                    "missingOrInsufficientTimeframes": missing,
                }
            )
            continue
        eligible.append(instrument)
        semantics[instrument] = {
            timeframe: {
                "route": by_timeframe[timeframe]["semanticRoute"],
                "semanticType": by_timeframe[timeframe]["semanticType"],
                "verificationHash": by_timeframe[timeframe]["verificationHash"],
                "contentHash": by_timeframe[timeframe]["contentHash"],
            }
            for timeframe in required
        }
        coverage[instrument] = {
            timeframe: {
                "rowCount": int(by_timeframe[timeframe]["rowCount"]),
                "start": by_timeframe[timeframe].get("start"),
                "end": by_timeframe[timeframe].get("end"),
                "contentHash": str(
                    by_timeframe[timeframe].get("contentHash") or ""
                ),
            }
            for timeframe in required
        }

    selected_rows = [
        row
        for row in capacity_capability
        if row.get("instrumentId") in eligible and row.get("timeframe") in required
    ]
    exchanges = sorted(
        {str(row.get("sourceExchange") or "unknown") for row in selected_rows}
    )
    market_types = sorted(
        {str(row.get("marketType") or "unknown") for row in selected_rows}
    )
    turnover_fields = sorted(
        {str(row.get("selectedVolumeColumn") or "") for row in selected_rows}
        - {""}
    )
    turnover_units = sorted(
        {str(row.get("declaredVolumeUnit") or "unknown") for row in selected_rows}
    )
    available_at_rules = sorted(
        {str(row.get("availableAtRule") or "") for row in selected_rows} - {""}
    )
    starts = [str(row["start"]) for row in selected_rows if row.get("start")]
    ends = [str(row["end"]) for row in selected_rows if row.get("end")]
    all_required_eligible = bool(instruments) and set(eligible) == set(instruments)

    profile: dict[str, Any] = {
        "profileId": "ohlcv_verified_capacity_v2",
        "strategyType": "directional_event",
        "sourceExchange": exchanges[0] if len(exchanges) == 1 else "mixed",
        "marketType": market_types[0] if len(market_types) == 1 else "mixed",
        "instrumentSet": instruments,
        "universeSelectionPolicy": "explicit_frozen_instrument_set",
        "fieldSet": ["open", "high", "low", "close", "quote_turnover"],
        "timeframes": required,
        "requiredTimeframes": required,
        "minimumHistoryRows": int(minimum_history_rows),
        "minimumLookback": {"unit": "rows", "value": int(minimum_history_rows)},
        "commonCutoff": {
            "start": max(starts) if starts else None,
            "end": min(ends) if ends else None,
        },
        "ohlcCoverageByInstrument": coverage,
        "coverageByInstrument": coverage,
        "turnoverField": turnover_fields[0]
        if len(turnover_fields) == 1
        else "mixed",
        "turnoverUnit": turnover_units[0]
        if len(turnover_units) == 1
        else "mixed",
        "availableAt": available_at_rules[0]
        if len(available_at_rules) == 1
        else "mixed",
        "eligibleInstruments": eligible,
        "excludedInstruments": excluded,
        "turnoverSemanticsByInstrument": semantics,
        "volumeProvenanceAuditHash": str(volume_audit.get("auditHash") or ""),
        "selectionUsesEconomicResults": False,
        "selectionPolicy": "semantic_and_coverage_evidence_only",
        "status": "ready" if all_required_eligible else "blocked",
        "knownLimitations": [
            "Exchange portability is evaluated separately from turnover semantics.",
            "The source exchange identity remains unverified when the profile source is unverified_local_exchange.",
        ],
    }
    profile["profileHash"] = _profile_hash(profile)
    return profile
