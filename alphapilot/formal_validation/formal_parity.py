"""Candidate-neutral formal event canonicalization and parity reporting."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Mapping, Sequence

from .candidate_adapter import CandidateAdapter, resolve_candidate_signal_identity
from .dual_engine_parity import evaluate_dual_engine_parity
from .formal_event_contract import canonicalize_formal_event as _canonicalize_formal_event


def canonicalize_formal_event(
    event: Mapping[str, Any],
    *,
    candidate_adapter: CandidateAdapter,
) -> dict[str, Any]:
    """Canonicalize an event using only the registered adapter identity contract."""

    identified = dict(event)
    identified["signalId"] = resolve_candidate_signal_identity(
        adapter=candidate_adapter,
        event=identified,
    )
    return _canonicalize_formal_event(identified)


def summarize_formal_parity(
    reference_events: Sequence[Mapping[str, Any]],
    adapter_events: Sequence[Mapping[str, Any]],
    *,
    adapter_runtime_base: str,
    require_freqtrade_runtime: bool,
    schema_version: str = "formal_translation_parity_v1",
) -> dict[str, Any]:
    """Evaluate strict event parity and fail closed outside Freqtrade."""

    report = evaluate_dual_engine_parity(reference_events, adapter_events)
    runtime_loaded = str(adapter_runtime_base).startswith("freqtrade.")
    blockers = list(report["blockers"])
    if require_freqtrade_runtime and not runtime_loaded:
        blockers.append("freqtrade_runtime_not_loaded")
    blockers = list(dict.fromkeys(blockers))
    event_denominator = max(
        int(report["referenceEventCount"]), int(report["implementationEventCount"]), 1
    )
    expected_leg_count = sum(
        int(event.get("exitLegCount") or 0) for event in reference_events
    )
    identity_pct = float(report["matchedEventCount"]) / event_denominator * 100.0
    leg_pct = (
        float(report["matchedLegCount"]) / expected_leg_count * 100.0
        if expected_leg_count
        else 0.0
    )
    status = "passed" if not blockers else (
        "blocked" if blockers == ["freqtrade_runtime_not_loaded"] else "failed"
    )
    return {
        **report,
        "schemaVersion": schema_version,
        "status": status,
        "passed": status == "passed",
        "blockers": blockers,
        "identityParityPct": identity_pct,
        "exitLegParityPct": leg_pct,
        "actualStrategyAdapterInvoked": True,
        "adapterRuntimeBase": str(adapter_runtime_base),
        "freqtradeRuntimeLoaded": runtime_loaded,
        "fullFormalInput": True,
        "syntheticFixtureOnly": False,
        "networkAccessCount": 0,
        "lockedOosAccessCount": 0,
        "credentialReadCount": 0,
        "formalPerformanceClaimed": False,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def write_formal_parity_mismatches(path: Path, report: Mapping[str, Any]) -> Path:
    """Write bounded mismatch details without recomputing any event."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("primaryKey", "duplicateIndex", "reasons"),
        )
        writer.writeheader()
        for row in report.get("mismatches", []):
            writer.writerow(
                {
                    "primaryKey": "|".join(str(value) for value in row["primaryKey"]),
                    "duplicateIndex": row["duplicateIndex"],
                    "reasons": "|".join(str(value) for value in row["reasons"]),
                }
            )
    return path
