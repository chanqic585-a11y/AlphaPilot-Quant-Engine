"""Build machine-readable data capability evidence from frozen catalogs."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from alphapilot.research_factory.available_at import available_at_rule
from alphapilot.research_factory.field_semantics import build_field_semantics_registry


_FIELDS = tuple(build_field_semantics_registry())
_READY = {"ready", "ready_proxy", "derived", "derived_proxy", "diagnostic_proxy"}


def _dataset_instrument(dataset: dict[str, Any]) -> str:
    symbols = dataset.get("symbols") or []
    return str(symbols[0] if symbols else dataset.get("instrumentId", "unknown"))


def _status_for_field(
    *,
    field: str,
    data_type: str,
    instrument: str,
    timeframe: str,
    btc_timeframes: set[str],
) -> tuple[str, str]:
    if data_type == "ohlcv":
        if field in {"open", "high", "low", "close", "reported_volume", "perpetual_price"}:
            return "ready_proxy", "frozen local OHLCV; exchange provenance unverified"
        if field in {"btc_returns", "residual_beta_inputs"} and timeframe in btc_timeframes:
            return "derived_proxy", "derived causally from synchronized frozen close series"
        if field in {"instrument_state", "pit_universe"}:
            return "diagnostic_proxy", "listing-state history is incomplete"
    if data_type == "funding" and field == "funding_rate":
        return "ready", "Binance public funding history with source timestamps"
    return "unavailable", "field is absent or its unit/provenance is not verified in the frozen catalog"


def build_data_capability_matrix(
    catalog: dict[str, Any],
    source_audit: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    del source_audit  # Catalog evidence remains authoritative; audit is reported separately.
    datasets = list(catalog.get("datasets") or [])
    maximum_rows: dict[tuple[str, str], int] = defaultdict(int)
    btc_timeframes: set[str] = set()
    for dataset in datasets:
        key = (str(dataset.get("dataType", "")), str(dataset.get("timeframe") or "event"))
        maximum_rows[key] = max(maximum_rows[key], int(dataset.get("rowCount") or 0))
        if _dataset_instrument(dataset).startswith("BTC-") and dataset.get("dataType") == "ohlcv":
            btc_timeframes.add(str(dataset.get("timeframe")))

    matrix: list[dict[str, Any]] = []
    semantics = build_field_semantics_registry()
    for dataset in datasets:
        data_type = str(dataset.get("dataType", ""))
        timeframe = str(dataset.get("timeframe") or "event")
        instrument = _dataset_instrument(dataset)
        row_count = int(dataset.get("rowCount") or 0)
        denominator = maximum_rows[(data_type, timeframe)] or row_count or 1
        coverage = round(min(100.0, row_count / denominator * 100.0), 6)
        for field in _FIELDS:
            status, reason = _status_for_field(
                field=field,
                data_type=data_type,
                instrument=instrument,
                timeframe=timeframe,
                btc_timeframes=btc_timeframes,
            )
            rule = available_at_rule(field)
            matrix.append(
                {
                    "exchange": str(dataset.get("exchange", "unknown")),
                    "marketType": str(dataset.get("marketType", "unknown")),
                    "instrumentId": instrument,
                    "timeframe": timeframe,
                    "field": field,
                    "start": dataset.get("startTime"),
                    "end": dataset.get("endTime"),
                    "rowCount": row_count if status in _READY else 0,
                    "coveragePct": coverage if status in _READY else 0.0,
                    "unit": semantics[field]["unit"],
                    "source": str(dataset.get("provider", "unknown")),
                    "availableAtRule": rule["rule"],
                    "causal": bool(rule["causal"]),
                    "pointInTime": bool(dataset.get("isPointInTime", False)),
                    "hash": str(dataset.get("contentHash", "")),
                    "datasetId": str(dataset.get("datasetId", "")),
                    "status": status,
                    "reason": reason,
                }
            )
    return matrix


def candidate_data_gate(
    matrix: list[dict[str, Any]],
    *,
    required_fields: Iterable[str],
    optional_fields: Iterable[str],
    timeframes: Iterable[str],
    minimum_history_rows: int,
    data_profile_id: str,
) -> dict[str, Any]:
    required = tuple(dict.fromkeys(str(field) for field in required_fields))
    optional = tuple(dict.fromkeys(str(field) for field in optional_fields))
    selected_timeframes = set(str(value) for value in timeframes)
    relevant = [row for row in matrix if row["timeframe"] in selected_timeframes]
    missing: list[str] = []
    coverage_by_field: dict[str, float] = {}
    for field in required:
        rows = [row for row in relevant if row["field"] == field]
        ready_rows = [row for row in rows if row["status"] in _READY]
        minimum_coverage = min((float(row["coveragePct"]) for row in ready_rows), default=0.0)
        minimum_rows = min((int(row["rowCount"]) for row in ready_rows), default=0)
        coverage_by_field[field] = minimum_coverage
        if not rows or len(ready_rows) != len(rows) or minimum_coverage < 95.0 or minimum_rows < minimum_history_rows:
            missing.append(field)
    return {
        "schemaVersion": "candidate_data_gate_v1",
        "status": "data_blocked_before_candidate_creation" if missing else "ready_for_candidate_creation",
        "dataProfileId": data_profile_id,
        "requiredFields": list(required),
        "optionalFields": list(optional),
        "timeframes": sorted(selected_timeframes),
        "minimumHistoryRows": int(minimum_history_rows),
        "minimumCoveragePct": min(coverage_by_field.values(), default=0.0),
        "coverageByRequiredField": coverage_by_field,
        "missingRequiredFields": missing,
        "missingDataPolicy": "block_before_candidate_id_and_do_not_consume_trial_budget",
    }


def summarize_data_capabilities(matrix: list[dict[str, Any]]) -> dict[str, Any]:
    instruments = sorted({row["instrumentId"] for row in matrix})
    timeframes = sorted({row["timeframe"] for row in matrix})
    unavailable = sorted(
        {
            field
            for field in _FIELDS
            if not any(row["field"] == field and row["status"] in _READY for row in matrix)
        }
    )
    gate = candidate_data_gate(
        matrix,
        required_fields=["open", "high", "low", "close"],
        optional_fields=["reported_volume"],
        timeframes=[value for value in ("1h", "4h") if value in timeframes],
        minimum_history_rows=10_000,
        data_profile_id="ohlcv_core_directional_v1",
    )
    return {
        "schemaVersion": "data_capability_summary_v1",
        "rowCount": len(matrix),
        "instrumentCount": len(instruments),
        "instruments": instruments,
        "timeframes": timeframes,
        "availableFields": sorted(set(_FIELDS) - set(unavailable)),
        "unavailableFields": unavailable,
        "directionalEventReady": gate["status"] == "ready_for_candidate_creation",
        "directionalEventGate": gate,
    }


def build_capacity_data_capability(volume_audit: dict[str, Any]) -> list[dict[str, Any]]:
    """Translate provenance evidence into data-only capacity capabilities."""

    rows: list[dict[str, Any]] = []
    for source in volume_audit.get("records") or []:
        verification = dict(source.get("volumeSemantics") or {})
        verified = verification.get("status") == "verified" and verification.get(
            "route"
        ) in {"A", "B", "C", "D"}
        rows.append(
            {
                "datasetId": str(source.get("datasetId") or ""),
                "instrumentId": str(source.get("instrumentId") or ""),
                "timeframe": str(source.get("timeframe") or ""),
                "field": "quote_turnover",
                "rowCount": int(source.get("rowCount") or 0),
                "contentHash": str(source.get("contentHash") or ""),
                "sourceFileHash": str(source.get("sourceFileHash") or ""),
                "sourceExchange": str(source.get("sourceExchange") or "unknown"),
                "marketType": str(source.get("marketType") or "unknown"),
                "selectedVolumeColumn": str(
                    source.get("selectedVolumeColumn") or ""
                ),
                "declaredVolumeUnit": str(
                    source.get("declaredVolumeUnit") or "unknown"
                ),
                "start": source.get("start"),
                "end": source.get("end"),
                "availableAtRule": str(
                    source.get("availableAtRule") or "candle_close_timestamp"
                ),
                "canonicalPath": source.get("canonicalPath"),
                "status": "ready" if verified else "capacity_semantics_unavailable",
                "semanticRoute": str(verification.get("route") or "E"),
                "semanticType": verification.get("semanticType"),
                "verificationHash": str(verification.get("verificationHash") or ""),
                "selectionUsesEconomicResults": False,
            }
        )
    return sorted(rows, key=lambda row: (row["instrumentId"], row["timeframe"]))
