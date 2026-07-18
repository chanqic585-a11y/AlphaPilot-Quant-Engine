"""Fail-closed event and exit-leg parity for the frozen S01 translation."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


class DualEngineParityError(RuntimeError):
    """Raised when synthetic event parity is absent or incomplete."""


_PRIMARY_EVENT_FIELDS = ("candidateId", "signalId", "symbol", "direction")
_EXACT_EVENT_FIELDS = (
    "candidateId",
    "signalId",
    "symbol",
    "direction",
    "signalTimestamp",
    "entryTimestamp",
    "exitPolicyHash",
    "exitLegCount",
)
_NUMERIC_EVENT_FIELDS = ("entryPrice", "initialStop")
_EXACT_LEG_FIELDS = (
    "legIndex",
    "legFraction",
    "exitReason",
    "triggerTimestamp",
    "executionTimestamp",
    "isGapFill",
    "ambiguousPath",
)
_NUMERIC_LEG_FIELDS = (
    "price",
    "grossR",
    "feesR",
    "slippageR",
    "spreadProxyR",
    "fundingR",
    "netR",
)


def _primary_key(event: Mapping[str, Any]) -> tuple[str, ...]:
    return tuple(str(event.get(field, "")) for field in _PRIMARY_EVENT_FIELDS)


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _malformed_reasons(event: Mapping[str, Any], *, side: str, index: int) -> list[str]:
    reasons: list[str] = []
    for field in _EXACT_EVENT_FIELDS:
        if field not in event or event[field] is None:
            reasons.append(f"missing_exact_field:{side}:{index}:{field}")
    for field in _NUMERIC_EVENT_FIELDS:
        if not _finite_number(event.get(field)):
            reasons.append(f"invalid_numeric_value:{side}:{index}:{field}")
    legs = event.get("exitLegs")
    if not isinstance(legs, list):
        reasons.append(f"missing_exit_legs:{side}:{index}")
        return reasons
    if event.get("exitLegCount") != len(legs):
        reasons.append(f"exit_leg_count_mismatch:{side}:{index}")
    for leg_index, leg in enumerate(legs):
        if not isinstance(leg, Mapping):
            reasons.append(f"invalid_exit_leg:{side}:{index}:{leg_index}")
            continue
        for field in _EXACT_LEG_FIELDS:
            if field not in leg or leg[field] is None:
                reasons.append(
                    f"missing_exact_leg_field:{side}:{index}:{leg_index}:{field}"
                )
        for field in _NUMERIC_LEG_FIELDS:
            if not _finite_number(leg.get(field)):
                reasons.append(
                    f"invalid_numeric_value:{side}:{index}:{leg_index}:{field}"
                )
    return reasons


def _numeric_equal(left: Any, right: Any, *, tolerance: float) -> bool:
    return _finite_number(left) and _finite_number(right) and math.isclose(
        float(left),
        float(right),
        rel_tol=0.0,
        abs_tol=tolerance,
    )


def _compare_event(
    reference: Mapping[str, Any],
    implementation: Mapping[str, Any],
    *,
    tolerance: float,
) -> tuple[list[str], int]:
    mismatches: list[str] = []
    for field in _EXACT_EVENT_FIELDS:
        if reference.get(field) != implementation.get(field):
            mismatches.append(f"event_identity_mismatch:{field}")
    for field in _NUMERIC_EVENT_FIELDS:
        if not _numeric_equal(reference.get(field), implementation.get(field), tolerance=tolerance):
            mismatches.append(f"event_numeric_mismatch:{field}")

    reference_legs = list(reference.get("exitLegs") or [])
    implementation_legs = list(implementation.get("exitLegs") or [])
    matched_legs = 0
    if len(reference_legs) != len(implementation_legs):
        mismatches.append("exit_leg_count_mismatch")
        return mismatches, matched_legs
    for leg_index, (reference_leg, implementation_leg) in enumerate(
        zip(reference_legs, implementation_legs, strict=True)
    ):
        leg_matches = True
        for field in _EXACT_LEG_FIELDS:
            if reference_leg.get(field) != implementation_leg.get(field):
                mismatches.append(f"leg_identity_mismatch:{leg_index}:{field}")
                leg_matches = False
        for field in _NUMERIC_LEG_FIELDS:
            if not _numeric_equal(
                reference_leg.get(field),
                implementation_leg.get(field),
                tolerance=tolerance,
            ):
                mismatches.append(f"leg_numeric_mismatch:{leg_index}:{field}")
                leg_matches = False
        if leg_matches:
            matched_legs += 1
    return mismatches, matched_legs


def evaluate_dual_engine_parity(
    reference_events: Sequence[Mapping[str, Any]],
    implementation_events: Sequence[Mapping[str, Any]],
    *,
    numeric_tolerance: float = 1e-9,
) -> dict[str, Any]:
    """Compare event collections as multisets while preserving duplicate events."""

    if not _finite_number(numeric_tolerance) or float(numeric_tolerance) < 0:
        raise ValueError("numeric_tolerance must be finite and non-negative")

    blockers: list[str] = []
    malformed: list[str] = []
    for index, event in enumerate(reference_events):
        malformed.extend(_malformed_reasons(event, side="reference", index=index))
    for index, event in enumerate(implementation_events):
        malformed.extend(_malformed_reasons(event, side="implementation", index=index))
    if malformed:
        blockers.append("invalid_numeric_value" if any(
            reason.startswith("invalid_numeric_value") for reason in malformed
        ) else "malformed_event")

    if not reference_events and not implementation_events:
        blockers.append("zero_signal_fixture")

    reference_groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    implementation_groups: dict[tuple[str, ...], list[Mapping[str, Any]]] = defaultdict(list)
    for event in reference_events:
        reference_groups[_primary_key(event)].append(event)
    for event in implementation_events:
        implementation_groups[_primary_key(event)].append(event)

    missing_count = 0
    extra_count = 0
    matched_event_count = 0
    matched_leg_count = 0
    mismatch_details: list[dict[str, Any]] = []
    for key in sorted(set(reference_groups) | set(implementation_groups)):
        reference_group = reference_groups.get(key, [])
        implementation_group = implementation_groups.get(key, [])
        pair_count = min(len(reference_group), len(implementation_group))
        missing_count += max(0, len(reference_group) - pair_count)
        extra_count += max(0, len(implementation_group) - pair_count)
        for duplicate_index in range(pair_count):
            mismatches, event_matched_legs = _compare_event(
                reference_group[duplicate_index],
                implementation_group[duplicate_index],
                tolerance=float(numeric_tolerance),
            )
            matched_leg_count += event_matched_legs
            if mismatches:
                mismatch_details.append(
                    {
                        "primaryKey": list(key),
                        "duplicateIndex": duplicate_index,
                        "reasons": mismatches,
                    }
                )
            else:
                matched_event_count += 1

    if missing_count:
        blockers.append("missing_event")
    if extra_count:
        blockers.append("extra_event")
    if any(
        reason.startswith(("event_identity_mismatch", "leg_identity_mismatch"))
        for detail in mismatch_details
        for reason in detail["reasons"]
    ):
        blockers.append("event_identity_mismatch")
    if any(
        "numeric_mismatch" in reason
        for detail in mismatch_details
        for reason in detail["reasons"]
    ):
        blockers.append("numeric_mismatch")
    if mismatch_details and not any(
        blocker in blockers for blocker in ("event_identity_mismatch", "numeric_mismatch")
    ):
        blockers.append("exit_leg_mismatch")

    blockers = list(dict.fromkeys(blockers))
    status = "passed"
    if blockers:
        status = "blocked" if blockers == ["zero_signal_fixture"] else "failed"
    return {
        "schemaVersion": "alphapilot_dual_engine_readiness_parity_v1",
        "status": status,
        "passed": status == "passed",
        "numericTolerance": float(numeric_tolerance),
        "zeroSignalParityRejected": True,
        "referenceEventCount": len(reference_events),
        "implementationEventCount": len(implementation_events),
        "matchedEventCount": matched_event_count,
        "matchedLegCount": matched_leg_count,
        "missingEventCount": missing_count,
        "extraEventCount": extra_count,
        "mismatchedEventCount": len(mismatch_details),
        "blockers": blockers,
        "malformedReasons": malformed[:50],
        "mismatches": mismatch_details[:50],
    }


def assert_dual_engine_parity(
    reference_events: Sequence[Mapping[str, Any]],
    implementation_events: Sequence[Mapping[str, Any]],
    *,
    numeric_tolerance: float = 1e-9,
) -> dict[str, Any]:
    report = evaluate_dual_engine_parity(
        reference_events,
        implementation_events,
        numeric_tolerance=numeric_tolerance,
    )
    if not report["passed"]:
        raise DualEngineParityError(
            "dual-engine parity failed: " + ", ".join(report["blockers"])
        )
    return report


def write_dual_engine_parity_report(path: Path, report: Mapping[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(report), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)
    return path
