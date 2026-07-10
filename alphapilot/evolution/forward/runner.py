"""Restart-safe one-cycle runner for public-market local forward observation."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    ForwardEventRecord,
    ForwardReleaseRecord,
    ForwardSessionRecord,
    OutcomeLedgerRecord,
)

from .engine import process_completed_bar
from .rules import evaluate_frozen_policy
from .types import ForwardBar, ForwardRiskEnvelope, ForwardState


class ForwardPublicMarket(Protocol):
    def completed_candles(
        self, instrument_id: str, timeframe: str, *, limit: int = 300
    ) -> pd.DataFrame: ...


@dataclass(frozen=True)
class ForwardCycleResult:
    forwardReleaseId: str
    forwardSessionId: str
    status: str
    observedInstrumentCount: int
    eventCount: int
    closedOutcomeCount: int
    collectionFailureCount: int
    state: dict[str, Any]


def _iso_from_ms(timestamp_ms: int) -> str:
    return pd.Timestamp(timestamp_ms, unit="ms", tz="UTC").isoformat()


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _envelope(release: ForwardReleaseRecord) -> ForwardRiskEnvelope:
    allowed = set(ForwardRiskEnvelope.__dataclass_fields__)
    values = {key: value for key, value in release.riskEnvelope.items() if key in allowed}
    envelope = ForwardRiskEnvelope(**values)
    envelope.validate()
    return envelope


def _ensure_session(
    release: ForwardReleaseRecord,
    *,
    repository: RegistryRepository,
    account_id: str,
    started_at: str,
) -> ForwardSessionRecord:
    existing = repository.get_forward_session_by_release_account(
        release.forwardReleaseId, account_id
    )
    if existing is not None:
        return existing
    envelope = _envelope(release)
    payload = {
        "schemaVersion": "local_forward_session_v1",
        "forwardReleaseId": release.forwardReleaseId,
        "strategyCandidateId": release.strategyCandidateId,
        "accountId": account_id,
        "initialEquityUsdt": envelope.initialEquityUsdt,
        "publicMarketOnly": True,
        "virtualAccountOnly": True,
        "createsOrders": False,
    }
    session_id = stable_hash(
        {"forwardReleaseId": release.forwardReleaseId, "accountId": account_id},
        prefix="forward_session",
    )
    return repository.create_forward_session(
        ForwardSessionRecord(
            forwardSessionId=session_id,
            forwardReleaseId=release.forwardReleaseId,
            accountId=account_id,
            initialEquity=envelope.initialEquityUsdt,
            session=payload,
            contentHash=stable_hash(payload),
            startedAt=started_at,
        )
    )

def _load_state(
    session: ForwardSessionRecord,
    release: ForwardReleaseRecord,
    repository: RegistryRepository,
) -> ForwardState:
    checkpoint = repository.get_latest_forward_event(
        session.forwardSessionId, event_type="state_checkpoint"
    )
    if checkpoint is not None:
        return ForwardState.from_dict(checkpoint.payload["state"])
    return ForwardState(
        forwardSessionId=session.forwardSessionId,
        forwardReleaseId=release.forwardReleaseId,
        strategyCandidateId=release.strategyCandidateId,
        accountId=session.accountId,
        initialEquity=session.initialEquity,
        cashBalance=session.initialEquity,
        equity=session.initialEquity,
        peakEquity=session.initialEquity,
    )


def _persist_event(
    repository: RegistryRepository,
    *,
    session: ForwardSessionRecord,
    event_type: str,
    observed_at: str,
    instrument_id: str | None,
    payload: dict[str, Any],
) -> ForwardEventRecord:
    content = {
        "forwardSessionId": session.forwardSessionId,
        "forwardReleaseId": session.forwardReleaseId,
        "eventType": event_type,
        "observedAt": observed_at,
        "instrumentId": instrument_id,
        "payload": payload,
    }
    return repository.create_forward_event(
        ForwardEventRecord(
            forwardEventId=stable_hash(content, prefix="forward_event"),
            forwardSessionId=session.forwardSessionId,
            forwardReleaseId=session.forwardReleaseId,
            eventType=event_type,
            observedAt=observed_at,
            instrumentId=instrument_id,
            payload=payload,
            contentHash=stable_hash(content),
        )
    )


def _persist_outcome(
    repository: RegistryRepository,
    *,
    release: ForwardReleaseRecord,
    session: ForwardSessionRecord,
    outcome: dict[str, Any],
    code_commit: str,
) -> OutcomeLedgerRecord:
    payload = {
        **outcome,
        "forwardReleaseId": release.forwardReleaseId,
        "forwardReleaseHash": release.contentHash,
        "forwardSessionId": session.forwardSessionId,
        "codeCommit": code_commit,
        "formalPromotionEligible": False,
    }
    outcome_id = stable_hash(payload, prefix="forward_outcome")
    return repository.create_outcome(
        OutcomeLedgerRecord(
            outcomeId=outcome_id,
            evidenceClass="realtime_local_forward",
            sourceEntityType="local_forward_session",
            sourceEntityId=session.forwardSessionId,
            dataSnapshotId=str(release.release["trainingDataSnapshotId"]),
            strategyCandidateId=release.strategyCandidateId,
            instrumentId=str(outcome["instrumentId"]),
            timeframe=str(outcome["timeframe"]),
            direction=str(outcome["direction"]),
            decisionAt=_iso_from_ms(int(outcome["decisionTimestampMs"])),
            entryAt=_iso_from_ms(int(outcome["entryTimestampMs"])),
            exitAt=_iso_from_ms(int(outcome["exitTimestampMs"])),
            status="closed",
            outcome=payload,
            contentHash=stable_hash(payload),
        )
    )


def run_forward_cycle(
    release: ForwardReleaseRecord,
    *,
    repository: RegistryRepository,
    market_data: ForwardPublicMarket,
    code_commit: str,
    account_id: str = "default_forward_account",
    cycle_observed_at: str | None = None,
) -> ForwardCycleResult:
    if release.status not in {"forward_eligible", "forward_active"}:
        raise ValueError("Forward runner requires an eligible or active release")
    if not code_commit.strip():
        raise ValueError("Forward runner requires a code commit")
    now = cycle_observed_at or _utc_now()
    session = _ensure_session(
        release, repository=repository, account_id=account_id, started_at=now
    )
    state = _load_state(session, release, repository)
    envelope = _envelope(release)
    market = release.release.get("marketDefinition", {})
    instruments = market.get("eligibleInstruments")
    timeframe = str(market.get("timeframe", ""))
    policy = release.release.get("signalPolicy")
    if not isinstance(instruments, list) or not instruments or not timeframe:
        raise ValueError("Forward release market definition is incomplete")
    if not isinstance(policy, dict):
        raise ValueError("Forward release signal policy is incomplete")
    event_count = 0
    closed_count = 0
    failures = 0
    observed = 0
    latest_observed_at = now
    for instrument in sorted({str(item).upper() for item in instruments}):
        try:
            frame = market_data.completed_candles(instrument, timeframe, limit=300)
            if frame.empty:
                raise RuntimeError("no_confirmed_public_candles")
            evaluation = evaluate_frozen_policy(
                frame,
                policy=policy,
                release_id=release.forwardReleaseId,
                instrument_id=instrument,
            )
            row = frame.sort_values("timestamp_ms").iloc[-1]
            bar = ForwardBar(
                instrumentId=instrument,
                timeframe=timeframe,
                timestampMs=int(row["timestamp_ms"]),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=float(row["volume"]),
            )
            transition = process_completed_bar(
                state,
                bar,
                envelope=envelope,
                decision=evaluation.decision,
            )
            state = transition.state
            observed += 1
            latest_observed_at = max(latest_observed_at, _iso_from_ms(bar.timestampMs))
            for event in transition.events:
                payload = {
                    **event["payload"],
                    "policyEvaluationStatus": evaluation.status,
                    "policyContext": evaluation.context,
                    "codeCommit": code_commit,
                }
                _persist_event(
                    repository,
                    session=session,
                    event_type=str(event["eventType"]),
                    observed_at=_iso_from_ms(int(event["observedAtMs"])),
                    instrument_id=instrument,
                    payload=payload,
                )
                event_count += 1
            for outcome in transition.closedOutcomes:
                _persist_outcome(
                    repository,
                    release=release,
                    session=session,
                    outcome=outcome,
                    code_commit=code_commit,
                )
                closed_count += 1
        except Exception as exc:  # noqa: BLE001 - isolate each public instrument.
            failures += 1
            _persist_event(
                repository,
                session=session,
                event_type="collection_failure",
                observed_at=now,
                instrument_id=instrument,
                payload={
                    "errorType": type(exc).__name__,
                    "error": str(exc),
                    "publicMarketOnly": True,
                    "forwardEvidenceCreated": False,
                    "codeCommit": code_commit,
                },
            )
            event_count += 1
    _persist_event(
        repository,
        session=session,
        event_type="state_checkpoint",
        observed_at=latest_observed_at,
        instrument_id=None,
        payload={
            "state": state.to_dict(),
            "cycleObservedAt": now,
            "collectionFailureCount": failures,
            "downtimeBackfilled": False,
            "codeCommit": code_commit,
        },
    )
    event_count += 1
    return ForwardCycleResult(
        forwardReleaseId=release.forwardReleaseId,
        forwardSessionId=session.forwardSessionId,
        status="observed" if failures == 0 else "observed_with_collection_failures",
        observedInstrumentCount=observed,
        eventCount=event_count,
        closedOutcomeCount=closed_count,
        collectionFailureCount=failures,
        state=state.to_dict(),
    )
