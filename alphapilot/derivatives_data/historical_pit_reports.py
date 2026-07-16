"""Audit existing derivatives partitions and report honest PIT readiness."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives_data.data_readiness_gate import evaluate_family_readiness


STRICT_CLOCK_FIELDS = {
    "eventTimestamp",
    "observedAt",
    "publishedAt",
    "availableAt",
    "sourceTimestamp",
    "publicationLagSeconds",
}
FAMILY_B_REQUIRED = {
    "perpetual_ohlcv",
    "funding",
    "open_interest",
    "spot_ohlcv",
    "basis",
    "instrument_state",
    "spread_slippage",
}
TIMESTAMP_COLUMNS = (
    "timestampUtc",
    "eventTimestamp",
    "sourceTimestamp",
    "timestamp",
    "datetime",
    "date",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_frame(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    if suffix == ".parquet":
        return pd.read_parquet(path)
    if suffix == ".csv":
        return pd.read_csv(path)
    if suffix in {".json", ".jsonl"}:
        return pd.read_json(path, lines=suffix == ".jsonl")
    raise ValueError(f"unsupported normalized partition: {path.name}")


def _canonical_data_type(relative: Path) -> str:
    parts = [part.lower().replace("-", "_") for part in relative.parts]
    market = parts[1] if len(parts) > 1 else "unknown"
    raw = parts[2] if len(parts) > 2 else "unknown"
    if raw in {"funding", "funding_rate", "funding_rates"}:
        return "funding"
    if raw in {"open_interest", "oi"}:
        return "open_interest"
    if raw in {"ohlcv", "candles", "kline", "klines"}:
        return "spot_ohlcv" if market == "spot" else "perpetual_ohlcv"
    if raw in {"basis", "spot_perpetual_basis"}:
        return "basis"
    if raw in {"instrument", "instruments", "instrument_state"}:
        return "instrument_state"
    if raw in {"spread", "slippage", "spread_slippage", "orderbook"}:
        return "spread_slippage"
    if raw in {"pit", "pit_universe", "historical_universe"}:
        return "pit_universe"
    if raw in {"liquidation", "liquidations"}:
        return "liquidation"
    return raw


def _timestamp_diagnostics(frame: pd.DataFrame) -> dict[str, Any]:
    column = next((name for name in TIMESTAMP_COLUMNS if name in frame.columns), None)
    if not column or frame.empty:
        return {
            "timestampColumn": column,
            "firstTimestampUtc": None,
            "lastTimestampUtc": None,
            "timeMonotonic": bool(column),
            "timezoneStatus": "unavailable" if not column else "empty",
            "duplicateTimestampCount": 0,
            "futureLeakCount": 0,
            "unexplainedGapCount": 0,
        }
    parsed = pd.to_datetime(frame[column], utc=True, errors="coerce")
    valid = parsed.dropna()
    duplicate_count = int(valid.duplicated().sum())
    monotonic = bool(valid.is_monotonic_increasing)
    future_leaks = 0
    if "availableAt" in frame.columns:
        available = pd.to_datetime(frame["availableAt"], utc=True, errors="coerce")
        future_leaks = int((available < parsed).fillna(False).sum())
    gap_count = 0
    ordered = valid.drop_duplicates().sort_values()
    if len(ordered) >= 3:
        deltas = ordered.diff().dropna().dt.total_seconds()
        typical = float(deltas.median()) if not deltas.empty else 0.0
        if typical > 0:
            gap_count = int((deltas > typical * 1.5).sum())
    return {
        "timestampColumn": column,
        "firstTimestampUtc": valid.min().isoformat() if not valid.empty else None,
        "lastTimestampUtc": valid.max().isoformat() if not valid.empty else None,
        "timeMonotonic": monotonic,
        "timezoneStatus": "utc_normalized" if len(valid) == len(frame) else "invalid_values",
        "duplicateTimestampCount": duplicate_count,
        "futureLeakCount": future_leaks,
        "unexplainedGapCount": gap_count,
    }


def _audit_partition(path: Path, normalized_root: Path) -> dict[str, Any]:
    relative = path.relative_to(normalized_root)
    exchange = relative.parts[0].lower() if relative.parts else "unknown"
    data_type = _canonical_data_type(relative)
    blockers: list[str] = []
    try:
        frame = _load_frame(path)
        load_error = None
    except (OSError, ValueError, ImportError) as exc:
        frame = pd.DataFrame()
        load_error = f"{type(exc).__name__}: {exc}"
        blockers.append("partition_load_failed")
    columns = {str(column) for column in frame.columns}
    clocks_complete = STRICT_CLOCK_FIELDS.issubset(columns)
    if not clocks_complete:
        blockers.append("missing_strict_availability_clocks")
    metadata_path = path.with_name(path.name + ".metadata.json")
    if not metadata_path.is_file():
        blockers.extend(["missing_source_metadata", "missing_license_metadata"])
    timestamps = _timestamp_diagnostics(frame)
    if not timestamps["timeMonotonic"]:
        blockers.append("non_monotonic_time")
    if timestamps["duplicateTimestampCount"]:
        blockers.append("duplicate_timestamps")
    if timestamps["futureLeakCount"]:
        blockers.append("future_data_leak")
    row_count = len(frame)
    cell_count = max(1, row_count * max(1, len(frame.columns)))
    missing_count = int(frame.isna().sum().sum()) if not frame.empty else 0
    instrument = path.stem
    if "instrumentId" in frame.columns and not frame["instrumentId"].dropna().empty:
        instrument = str(frame["instrumentId"].dropna().iloc[0])
    return {
        "path": str(relative).replace("\\", "/"),
        "exchange": exchange,
        "dataType": data_type,
        "instrumentId": instrument,
        "rowCount": row_count,
        "columnCount": len(frame.columns),
        "columns": sorted(columns),
        "schemaStatus": "readable" if load_error is None else "failed",
        "loadError": load_error,
        "strictAvailabilityClocksComplete": clocks_complete,
        "missingStrictClockFields": sorted(STRICT_CLOCK_FIELDS - columns),
        "missingValueCount": missing_count,
        "missingRate": missing_count / cell_count,
        "imputedZeroCount": 0,
        "zeroAnomalyCount": 0,
        "extremeValueCount": 0,
        "unitStatus": "requires_source_metadata",
        "staleStatus": "not_evaluated_without_registered_freshness_rule",
        "symbolMappingStatus": "present" if instrument else "missing",
        "listingStateStatus": "present" if "tradingState" in columns else "unavailable",
        "sourceStatus": "registered" if metadata_path.is_file() else "metadata_missing",
        "licenseStatus": "registered" if metadata_path.is_file() else "metadata_missing",
        "contentHash": _sha256(path),
        "fileBytes": path.stat().st_size,
        "formalEligible": not blockers,
        "blockers": sorted(set(blockers)),
        **timestamps,
    }


def _family_b_report(rows: list[dict[str, Any]]) -> dict[str, Any]:
    types_by_exchange: dict[str, set[str]] = defaultdict(set)
    for row in rows:
        types_by_exchange[str(row["exchange"])].add(str(row["dataType"]))
    eligible = [
        exchange
        for exchange, data_types in sorted(types_by_exchange.items())
        if FAMILY_B_REQUIRED.issubset(data_types)
    ]
    best_exchange = max(
        types_by_exchange,
        key=lambda exchange: len(types_by_exchange[exchange] & FAMILY_B_REQUIRED),
        default=None,
    )
    present = types_by_exchange.get(best_exchange, set())
    missing = sorted(FAMILY_B_REQUIRED - present)
    status = "formal_ready" if eligible else "diagnostic_ready" if rows else "unavailable"
    return {
        "schemaVersion": "v13_27_1_12_family_b_data_chain_v1",
        "qualificationId": "short_crowding_unwind_data_chain",
        "status": status,
        "sameExchangeCoreChain": bool(eligible),
        "formalEligibleExchanges": eligible,
        "bestAvailableExchange": best_exchange,
        "availableDataTypes": sorted(present),
        "missingDataTypes": missing,
        "historyMonths": 0,
        "eligibleContracts": 0,
        "coreCoverage": 0.0,
        "maximumInstrumentMissingRate": None,
        "unexplainedLongGapCount": sum(int(row["unexplainedGapCount"]) for row in rows),
        "futureLeakCount": sum(int(row["futureLeakCount"]) for row in rows),
        "qualityPassed": bool(rows) and not any(row["blockers"] for row in rows),
        "thresholdsChangedFromLockedSpec": False,
    }


def build_stage3_reports(*, data_root: Path, checked_at: str) -> dict[str, Any]:
    normalized_root = data_root / "normalized"
    paths = (
        sorted(
            path
            for path in normalized_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".parquet", ".csv", ".json", ".jsonl"}
        )
        if normalized_root.is_dir()
        else []
    )
    rows = [_audit_partition(path, normalized_root) for path in paths]
    family_b = _family_b_report(rows)
    source_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        source_groups[(str(row["exchange"]), str(row["dataType"]))].append(row)
    quality_by_source = [
        {
            "exchange": exchange,
            "dataType": data_type,
            "partitionCount": len(group),
            "formalEligiblePartitionCount": sum(1 for row in group if row["formalEligible"]),
            "qualityPassed": all(row["formalEligible"] for row in group),
            "blockers": sorted({blocker for row in group for blocker in row["blockers"]}),
        }
        for (exchange, data_type), group in sorted(source_groups.items())
    ]
    pit_rows = [row for row in rows if row["dataType"] == "pit_universe"]
    pit_audit = {
        "schemaVersion": "v13_27_1_12_pit_universe_audit_v1",
        "checkedAt": checked_at,
        "status": "formal_ready" if pit_rows and all(row["formalEligible"] for row in pit_rows) else "unavailable",
        "historicalFormalReady": bool(pit_rows) and all(row["formalEligible"] for row in pit_rows),
        "futureCollectionReady": True,
        "currentTopNBackfill": False,
        "pitSnapshotCount": 0,
        "pitSnapshotCoverage": 0.0,
        "medianInvestableContracts": 0,
        "majorityDatesAtLeast30": False,
        "researchSymbolCount": 0,
        "holdoutSymbolCount": 0,
        "reason": "no_historical_point_in_time_membership_source" if not pit_rows else "historical_pit_requires_snapshot_materialization",
    }
    pit_manifest = {
        "schemaVersion": "v13_27_1_12_pit_universe_manifest_v1",
        "checkedAt": checked_at,
        "status": "not_built" if not pit_rows else "source_detected_not_materialized",
        "sourceMode": "historical_point_in_time_only",
        "currentTopNBackfill": False,
        "preregisteredRule": {
            "instrumentType": "USDT perpetual",
            "tradingState": "live_at_snapshot",
            "minimumListingAgeDays": 90,
            "volumeAndOiThresholdMode": "pre_registered_quantiles",
            "spreadThresholdMode": "pre_registered_maximum",
            "coreOhlcvRequired": True,
        },
        "snapshotCount": 0,
        "sourceHashes": [row["contentHash"] for row in pit_rows],
    }
    evidence = {
        "A1": {
            "liquidationStatus": "unavailable",
            "coveragePassed": False,
            "qualityPassed": False,
        },
        "A2": {"proxyCoveragePassed": False},
        "B": {
            key: family_b[key]
            for key in (
                "historyMonths",
                "eligibleContracts",
                "coreCoverage",
                "maximumInstrumentMissingRate",
                "unexplainedLongGapCount",
                "futureLeakCount",
                "sameExchangeCoreChain",
                "qualityPassed",
            )
        },
        "C": {
            "historyMonths": 0,
            "pitSnapshotCoverage": pit_audit["pitSnapshotCoverage"],
            "medianInvestableContracts": pit_audit["medianInvestableContracts"],
            "majorityDatesAtLeast30": pit_audit["majorityDatesAtLeast30"],
            "researchSymbolCount": pit_audit["researchSymbolCount"],
            "holdoutSymbolCount": pit_audit["holdoutSymbolCount"],
            "currentTopNBackfill": pit_audit["currentTopNBackfill"],
            "qualityPassed": pit_audit["historicalFormalReady"],
        },
    }
    readiness = evaluate_family_readiness(evidence)
    return {
        "checkedAt": checked_at,
        "familyB": family_b,
        "pitAudit": pit_audit,
        "pitManifest": pit_manifest,
        "pitCoverage": [],
        "qualityBySource": quality_by_source,
        "qualityByInstrument": rows,
        "readinessEvidence": evidence,
        "readiness": readiness,
    }
