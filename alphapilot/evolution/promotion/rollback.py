"""Demo-only rollback decisions; live promotion and rollback are always forbidden."""

from __future__ import annotations

from dataclasses import dataclass

from .drift_monitor import DriftEvaluation


@dataclass(frozen=True)
class DemoRollbackDecision:
    action: str
    stopNewEntries: bool
    manageExistingByOriginalRelease: bool
    rollbackTargetId: str | None
    reasonCodes: tuple[str, ...]
    liveActionAllowed: bool = False


def decide_demo_rollback(
    drift: DriftEvaluation,
    *,
    previousStableReleaseId: str | None,
    previousReleaseStillValid: bool,
) -> DemoRollbackDecision:
    if not drift.pauseRequired:
        return DemoRollbackDecision(
            action="continue_demo_release",
            stopNewEntries=False,
            manageExistingByOriginalRelease=True,
            rollbackTargetId=None,
            reasonCodes=drift.reasonCodes,
        )
    can_rollback = bool(previousStableReleaseId and previousReleaseStillValid)
    return DemoRollbackDecision(
        action="rollback_demo_release" if can_rollback else "pause_demo_release",
        stopNewEntries=True,
        manageExistingByOriginalRelease=True,
        rollbackTargetId=previousStableReleaseId if can_rollback else None,
        reasonCodes=drift.reasonCodes,
    )
