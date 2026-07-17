"""Frozen split, fold assignment, and regime-causality evidence for S01."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.evolution.evaluation.purged_walk_forward import (
    build_purged_walk_forward,
)

from .formal_input import FormalInputError


_BOUNDARY_FIELDS = (
    "trainStart",
    "trainEndExclusive",
    "purgeStart",
    "purgeEndExclusive",
    "embargoStart",
    "embargoEndExclusive",
    "testStart",
    "testEndExclusive",
)


def _utc_iso(value: pd.Timestamp) -> str:
    value = value.tz_convert("UTC") if value.tzinfo else value.tz_localize("UTC")
    return value.isoformat().replace("+00:00", "Z")


def _timestamp_for_index(
    index: pd.DatetimeIndex, position: int, bar_hours: int
) -> pd.Timestamp:
    if position < 0 or position > len(index):
        raise FormalInputError(f"split_index_out_of_range:{position}")
    if position < len(index):
        return pd.Timestamp(index[position])
    if not len(index):
        raise FormalInputError("common_index_empty")
    return pd.Timestamp(index[-1]) + pd.Timedelta(hours=bar_hours)


def build_split_evidence(
    preregistration: Mapping[str, Any], common_index: pd.DatetimeIndex
) -> dict[str, Any]:
    split = preregistration.get("splitPolicy")
    if not isinstance(split, Mapping):
        raise FormalInputError("split_policy_missing")
    common_index = pd.DatetimeIndex(common_index)
    if len(common_index) != int(split.get("sampleCount", -1)):
        raise FormalInputError("split_sample_count_mismatch")
    if not common_index.is_monotonic_increasing or common_index.has_duplicates:
        raise FormalInputError("common_index_not_strictly_ordered")

    manifest = build_purged_walk_forward(
        sample_count=int(split["sampleCount"]),
        min_train_size=int(split["minimumTrainBars"]),
        test_size=int(split["testBarsPerFold"]),
        step_size=int(split["testBarsPerFold"]),
        label_horizon=int(split["purgeBars"]),
        embargo_size=int(split["embargoBars"]),
        max_holding_period=int(split["maximumHoldBars"]),
        min_folds=int(split["foldCount"]),
        mode=str(split["mode"]),
    )
    generated = [fold.to_dict() for fold in manifest.folds]
    frozen = list(split.get("folds", []))
    if len(generated) != len(frozen):
        raise FormalInputError("split_fold_count_mismatch")

    bar_hours = int(split["barHours"])
    timestamp_fields = {
        "trainStart": "trainStartTimestamp",
        "trainEndExclusive": "trainEndExclusiveTimestamp",
        "purgeStart": "purgeStartTimestamp",
        "purgeEndExclusive": "purgeEndExclusiveTimestamp",
        "embargoStart": "embargoStartTimestamp",
        "embargoEndExclusive": "embargoEndExclusiveTimestamp",
        "testStart": "testStartTimestamp",
        "testEndExclusive": "testEndExclusiveTimestamp",
    }
    boundary_mismatches: list[dict[str, Any]] = []
    fold_boundaries: list[dict[str, Any]] = []
    overlap_count = 0
    for generated_fold, frozen_fold in zip(generated, frozen, strict=True):
        row = dict(generated_fold)
        for field in _BOUNDARY_FIELDS:
            actual = int(generated_fold[field])
            expected = int(frozen_fold[field])
            if actual != expected:
                boundary_mismatches.append(
                    {
                        "foldId": generated_fold["foldId"],
                        "field": field,
                        "expected": expected,
                        "actual": actual,
                    }
                )
            timestamp_field = timestamp_fields[field]
            actual_timestamp = _utc_iso(
                _timestamp_for_index(common_index, actual, bar_hours)
            )
            expected_timestamp = str(frozen_fold[timestamp_field])
            row[timestamp_field] = actual_timestamp
            if actual_timestamp != expected_timestamp:
                boundary_mismatches.append(
                    {
                        "foldId": generated_fold["foldId"],
                        "field": timestamp_field,
                        "expected": expected_timestamp,
                        "actual": actual_timestamp,
                    }
                )
        if not (
            row["trainEndExclusive"] == row["purgeStart"]
            and row["purgeEndExclusive"] == row["embargoStart"]
            and row["embargoEndExclusive"] == row["testStart"]
            and row["trainEndExclusive"] <= row["testStart"]
        ):
            overlap_count += 1
        fold_boundaries.append(row)

    last_test_end = int(fold_boundaries[-1]["testEndExclusive"])
    unused_tail = len(common_index) - last_test_end
    if unused_tail != int(split.get("unusedTailBars", -1)):
        boundary_mismatches.append(
            {
                "foldId": "aggregate",
                "field": "unusedTailBars",
                "expected": split.get("unusedTailBars"),
                "actual": unused_tail,
            }
        )
    purge_audit = {
        "schemaVersion": "s01_formal_purge_audit_v1",
        "status": (
            "passed" if not boundary_mismatches and overlap_count == 0 else "failed"
        ),
        "purgeBars": int(split["purgeBars"]),
        "embargoBars": int(split["embargoBars"]),
        "maximumHoldBars": int(split["maximumHoldBars"]),
        "boundaryMismatchCount": len(boundary_mismatches),
        "overlapCount": overlap_count,
        "mismatches": boundary_mismatches,
    }
    if purge_audit["status"] != "passed":
        raise FormalInputError("frozen_split_boundary_mismatch")
    return {
        "schemaVersion": "s01_formal_split_evidence_v1",
        "status": "passed",
        "splitPolicyHash": preregistration.get("splitPolicyHash"),
        "generatedManifestHash": manifest.manifestHash,
        "foldCount": len(fold_boundaries),
        "sampleCount": len(common_index),
        "unusedTailBars": unused_tail,
        "folds": fold_boundaries,
        "purgeAudit": purge_audit,
    }


def assign_events_to_folds(
    events: Sequence[Mapping[str, Any]], split_policy: Mapping[str, Any]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    assigned: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    folds = list(split_policy.get("folds", []))
    for raw in events:
        event = dict(raw)
        signal_index = int(event["signalIndex"])
        entry_index = int(event["entryIndex"])
        exit_index = int(event["exitIndex"])
        containing = next(
            (
                fold
                for fold in folds
                if int(fold["testStart"])
                <= signal_index
                < int(fold["testEndExclusive"])
            ),
            None,
        )
        if containing is None:
            rejected.append({**event, "foldAssignmentReason": "outside_test_windows"})
            continue
        test_start = int(containing["testStart"])
        test_end = int(containing["testEndExclusive"])
        if not (
            test_start <= signal_index < test_end
            and test_start <= entry_index < test_end
            and test_start <= exit_index < test_end
        ):
            rejected.append(
                {**event, "foldAssignmentReason": "event_crosses_test_boundary"}
            )
            continue
        assigned.append(
            {**event, "foldId": str(containing["foldId"]), "split": "test"}
        )
    audit = {
        "schemaVersion": "s01_formal_fold_assignment_audit_v1",
        "inputEventCount": len(events),
        "acceptedEventCount": len(assigned),
        "rejectedEventCount": len(rejected),
        "boundaryRejectedEventCount": sum(
            row["foldAssignmentReason"] == "event_crosses_test_boundary"
            for row in rejected
        ),
        "outsideWindowEventCount": sum(
            row["foldAssignmentReason"] == "outside_test_windows"
            for row in rejected
        ),
        "eventMayCrossFoldBoundary": False,
    }
    return assigned, rejected, audit


def audit_bear_regime_causality(
    events: Sequence[Mapping[str, Any]],
    btc_frame: pd.DataFrame,
    *,
    ema_window: int = 200,
) -> dict[str, Any]:
    ordered = btc_frame.copy()
    ordered["date"] = pd.to_datetime(ordered["date"], utc=True)
    ordered = ordered.sort_values("date").drop_duplicates("date", keep="last")
    close = pd.to_numeric(ordered["close"], errors="coerce")
    ema = close.ewm(span=ema_window, adjust=False, min_periods=ema_window).mean()
    causal_count = 0
    warmup_count = 0
    failed: list[str] = []
    for event in events:
        position = int(event["signalIndex"])
        signal_id = str(event.get("signalId", position))
        if position < 0 or position >= len(ordered):
            failed.append(signal_id)
            continue
        if pd.isna(ema.iloc[position]):
            warmup_count += 1
            continue
        if float(close.iloc[position]) < float(ema.iloc[position]):
            causal_count += 1
        else:
            failed.append(signal_id)
    return {
        "schemaVersion": "s01_bear_regime_causality_v1",
        "status": "passed" if not failed else "failed",
        "emaWindow": ema_window,
        "eventCount": len(events),
        "causalBearEventCount": causal_count,
        "warmupInsufficientCount": warmup_count,
        "failedEventCount": len(failed),
        "failedSignalIds": failed,
        "futureBarReadCount": 0,
        "calculation": "btc_close_below_causal_ema_at_signal_index",
    }
