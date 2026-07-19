"""Normalize the approved reference hypotheses into immutable campaign candidates."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from alphapilot.exit_policy import ExitPolicy, ExitPolicyMode
from alphapilot.research_screening.campaign_contract import (
    ADVISORY_CANDIDATE_SCHEMA,
    CandidateSpec,
)


_SESSION_ID = "ref_utc_session_range_breakout_1h_v1"
_SECOND_ENTRY_ID = "ref_pa_breakout_failure_second_entry_4h_v1"


def _session_candidate(source: dict[str, Any], direction: str) -> CandidateSpec:
    maximum_hold = 12
    return CandidateSpec(
        candidateId=f"{_SESSION_ID}_{direction}",
        familyId="reference_utc_session_range_breakout",
        marketMechanismId="reference_utc_session_range_breakout",
        direction=direction,
        timeframe="1h",
        causalRationale=str(source.get("marketHypothesis") or "Frozen UTC range repricing."),
        eventDefinition={
            "sessionAnchorUtcHour": 0,
            "rangeBars": 4,
            "breakoutWindowBars": 12,
            "atrWindow": 20,
            "minimumRangeAtr": 0.5,
            "maximumRangeAtr": 2.5,
            "breakoutBufferAtr": 0.1,
            "maximumStopAtr": 2.0,
            "entryReference": "next_bar_open",
        },
        invalidation="Initial stop is frozen at the opposite session-range boundary or the preregistered ATR cap.",
        stopAtr=2.0,
        targetR=None,
        maximumHoldBars=maximum_hold,
        requiredData=("ohlcv",),
        expectedFailureRegimes=("range_reentry", "overnight_gap", "thin_liquidity"),
        schemaVersion=ADVISORY_CANDIDATE_SCHEMA,
        exitPolicy=ExitPolicy(
            mode=ExitPolicyMode.STRUCTURE_OR_TIME,
            maximumHoldBars=maximum_hold,
            parameters={"structureRule": {"kind": "frozen_range_midpoint"}},
        ),
    )


def _second_entry_candidate(source: dict[str, Any], direction: str) -> CandidateSpec:
    maximum_hold = 20
    return CandidateSpec(
        candidateId=f"{_SECOND_ENTRY_ID}_{direction}",
        familyId="reference_breakout_failure_second_entry",
        marketMechanismId="reference_breakout_failure_second_entry",
        direction=direction,
        timeframe="4h",
        causalRationale=str(
            source.get("marketHypothesis")
            or "A second failed breakout traps late participants and reprices through the range."
        ),
        eventDefinition={
            "boundaryWindowBars": 20,
            "atrWindow": 20,
            "maximumFirstBreakAtr": 0.5,
            "failureWindowBars": 2,
            "retestWindowBars": 6,
            "retestToleranceAtr": 0.1,
            "stopBufferAtr": 0.1,
            "maximumStopAtr": 2.5,
            "entryReference": "next_bar_open",
        },
        invalidation="Initial stop is frozen beyond the failed-test extreme plus the preregistered ATR buffer.",
        stopAtr=2.5,
        targetR=None,
        maximumHoldBars=maximum_hold,
        requiredData=("ohlcv",),
        expectedFailureRegimes=("persistent_breakout", "gap_through_stop", "thin_liquidity"),
        schemaVersion=ADVISORY_CANDIDATE_SCHEMA,
        exitPolicy=ExitPolicy(
            mode=ExitPolicyMode.HYBRID,
            maximumHoldBars=maximum_hold,
            parameters={
                "partialAtR": 1.0,
                "partialFraction": 0.5,
                "remainderMode": "trailing",
                "trailingAtrMultiple": 1.5,
            },
        ),
    )


def build_selected_candidates(package_candidates: Iterable[dict[str, Any]]) -> list[CandidateSpec]:
    """Expand only the two approved parents into long/short immutable specs."""

    normalized: list[CandidateSpec] = []
    for source in package_candidates:
        candidate_id = str(source.get("candidateId") or "")
        if candidate_id == _SESSION_ID:
            normalized.extend(_session_candidate(source, direction) for direction in ("long", "short"))
        elif candidate_id == _SECOND_ENTRY_ID:
            normalized.extend(
                _second_entry_candidate(source, direction) for direction in ("long", "short")
            )
    return normalized
