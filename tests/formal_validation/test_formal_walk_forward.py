from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alphapilot.formal_validation.formal_walk_forward import (
    assign_events_to_folds,
    audit_bear_regime_causality,
    build_split_evidence,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
PREREGISTRATION_PATH = (
    REPO_ROOT
    / "research"
    / "preregistrations"
    / "advisory_r_v17_s01_formal_walk_forward.json"
)


def _preregistration() -> dict[str, object]:
    return json.loads(PREREGISTRATION_PATH.read_text(encoding="utf-8"))


def test_build_split_evidence_matches_all_frozen_boundaries() -> None:
    preregistration = _preregistration()
    split = preregistration["splitPolicy"]
    common_index = pd.date_range(
        split["commonStart"], periods=split["sampleCount"], freq="4h", tz="UTC"
    )

    evidence = build_split_evidence(preregistration, common_index)

    assert evidence["status"] == "passed"
    assert evidence["foldCount"] == 5
    assert evidence["splitPolicyHash"] == preregistration["splitPolicyHash"]
    assert evidence["generatedManifestHash"]
    assert evidence["purgeAudit"]["status"] == "passed"
    assert evidence["purgeAudit"]["boundaryMismatchCount"] == 0
    assert evidence["purgeAudit"]["overlapCount"] == 0
    assert evidence["unusedTailBars"] == 3


def test_assign_events_rejects_positions_that_cross_test_boundary() -> None:
    split = _preregistration()["splitPolicy"]
    fold = split["folds"][0]
    accepted_event = {
        "signalId": "accepted",
        "signalIndex": fold["testStart"],
        "entryIndex": fold["testStart"] + 1,
        "exitIndex": fold["testStart"] + 4,
    }
    crossing_event = {
        "signalId": "crossing",
        "signalIndex": fold["testEndExclusive"] - 2,
        "entryIndex": fold["testEndExclusive"] - 1,
        "exitIndex": fold["testEndExclusive"],
    }

    assigned, rejected, audit = assign_events_to_folds(
        [accepted_event, crossing_event], split
    )

    assert assigned == [{**accepted_event, "foldId": "fold_001", "split": "test"}]
    assert rejected[0]["signalId"] == "crossing"
    assert rejected[0]["foldAssignmentReason"] == "event_crosses_test_boundary"
    assert audit["acceptedEventCount"] == 1
    assert audit["boundaryRejectedEventCount"] == 1


def test_bear_regime_audit_uses_only_information_available_at_signal() -> None:
    dates = pd.date_range("2024-01-01", periods=260, freq="4h", tz="UTC")
    descending = pd.Series([400.0 - index for index in range(260)])
    btc_frame = pd.DataFrame({"date": dates, "close": descending})
    events = [
        {"signalId": "bear", "signalIndex": 220},
        {"signalId": "warmup", "signalIndex": 100},
    ]

    audit = audit_bear_regime_causality(events, btc_frame, ema_window=200)

    assert audit["status"] == "passed"
    assert audit["causalBearEventCount"] == 1
    assert audit["warmupInsufficientCount"] == 1
    assert audit["futureBarReadCount"] == 0
    assert audit["failedEventCount"] == 0
