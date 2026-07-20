"""Pre-ARM readiness checks for an immutable provisional Demo release."""

from __future__ import annotations

from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash


_SMOKE_REQUIRED_STATUSES = (
    "smokeContract",
    "cancelAudit",
    "fillCloseAudit",
    "restartAudit",
    "reconciliationAudit",
)


def build_engineering_smoke_compatibility_audit(
    *,
    smoke_contract: Mapping[str, Any],
    cancel_audit: Mapping[str, Any],
    fill_close_audit: Mapping[str, Any],
    restart_audit: Mapping[str, Any],
    reconciliation_audit: Mapping[str, Any],
    evidence_isolation_audit: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    evidence = {
        "smokeContract": dict(smoke_contract),
        "cancelAudit": dict(cancel_audit),
        "fillCloseAudit": dict(fill_close_audit),
        "restartAudit": dict(restart_audit),
        "reconciliationAudit": dict(reconciliation_audit),
        "evidenceIsolationAudit": dict(evidence_isolation_audit),
    }
    status_by_check = {
        name: str(payload.get("status") or "missing")
        for name, payload in evidence.items()
    }
    lifecycle_complete = all(
        status_by_check[name] in {"passed", "completed", "verified"}
        for name in _SMOKE_REQUIRED_STATUSES
    )
    isolation_complete = (
        status_by_check["evidenceIsolationAudit"]
        in {"passed", "completed", "verified"}
        and evidence["evidenceIsolationAudit"].get("strategyEvidenceChanged") is False
    )
    ready = lifecycle_complete and isolation_complete
    evidence_hash = stable_hash(evidence, prefix="engineering_smoke_evidence")
    return {
        "schemaVersion": "provisional_demo_engineering_smoke_compatibility_audit_v1",
        "generatedAt": generated_at,
        "status": "compatible" if ready else "missing_compatible_smoke_evidence",
        "engineeringSmokeReady": ready,
        "statusByCheck": status_by_check,
        "lifecycleComplete": lifecycle_complete,
        "strategyEvidenceIsolationVerified": isolation_complete,
        "evidenceHash": evidence_hash,
        "separateApprovalRequired": not ready,
        "strategyReleaseApprovalAccepted": False,
        "orderRequestMade": False,
        "demoArm": False,
        "live": False,
        "withdraw": False,
    }


def build_engineering_smoke_approval_request(
    *, release: Mapping[str, Any], smoke_audit: Mapping[str, Any], generated_at: str
) -> dict[str, Any]:
    return {
        "schemaVersion": "provisional_demo_engineering_smoke_approval_request_v1",
        "generatedAt": generated_at,
        "requestType": "engineering_smoke_only",
        "releaseId": release.get("releaseId"),
        "releaseHash": release.get("releaseHash"),
        "riskOverlayHash": release.get("riskOverlayHash"),
        "reason": smoke_audit.get("status"),
        "evidenceHash": smoke_audit.get("evidenceHash"),
        "approvalGranted": False,
        "strategyReleaseApprovalAccepted": False,
        "demoArm": False,
        "orderCount": 0,
        "live": False,
        "withdraw": False,
        "route": "waiting_engineering_smoke_approval",
        "instruction": (
            "A later approval must explicitly authorize the isolated engineering "
            "smoke lifecycle. It must not be treated as strategy Release approval."
        ),
    }


def _test_exception_accepted(audit: Mapping[str, Any]) -> bool:
    return (
        audit.get("status") == "accepted_pre_existing_exception"
        and audit.get("introducedByThisPatch") is False
        and audit.get("executionPathImpact") is False
    )


def build_pre_arm_readiness(
    *,
    release: Mapping[str, Any],
    cooldown_audit: Mapping[str, Any],
    binding_audit: Mapping[str, Any],
    remote_freeze_receipt: Mapping[str, Any],
    targeted_test_summary: Mapping[str, Any],
    test_exception_audit: Mapping[str, Any],
    private_read_audit: Mapping[str, Any],
    engineering_smoke_audit: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    expected = sorted(str(row) for row in release.get("executionInstruments") or [])
    verified = sorted(
        str(row) for row in private_read_audit.get("verifiedInstruments") or []
    )
    checks = {
        "cooldownSemanticParity": cooldown_audit.get("status") == "passed",
        "releaseBindingComplete": (
            binding_audit.get("status") == "passed"
            and binding_audit.get("allRequiredBindingsPresent") is True
            and binding_audit.get("transitiveHashChainVerified") is True
        ),
        "remoteFreezePassed": (
            remote_freeze_receipt.get("status") == "verified"
            and remote_freeze_receipt.get("remoteVerified") is True
        ),
        "targetedTestsPassed": targeted_test_summary.get("status") == "passed",
        "preExistingTestExceptionAccepted": _test_exception_accepted(
            test_exception_audit
        ),
        "privateReadVerified": private_read_audit.get("privateReadVerified") is True,
        "executionUniverseFresh": (
            private_read_audit.get("executionIntersectionHashMatches") is True
            and verified == expected
        ),
        "engineeringSmokeReady": (
            engineering_smoke_audit.get("engineeringSmokeReady") is True
        ),
    }
    blockers = [name for name, passed in checks.items() if not passed]
    if blockers == ["engineeringSmokeReady"]:
        route = "waiting_engineering_smoke_approval"
    elif blockers:
        route = "blocked_pre_arm_readiness"
    else:
        route = "blocked_waiting_exact_release_approval"
    approval_ready = not blockers
    return {
        "schemaVersion": "provisional_demo_pre_arm_readiness_v1",
        "generatedAt": generated_at,
        **checks,
        "releaseId": release.get("releaseId"),
        "releaseHash": release.get("releaseHash"),
        "riskOverlayHash": release.get("riskOverlayHash"),
        "executionIntersectionHash": release.get("executionIntersectionHash"),
        "executionInstruments": expected,
        "blockers": blockers,
        "approvalReady": approval_ready,
        "approved": False,
        "demoArm": False,
        "orderCount": 0,
        "live": False,
        "withdraw": False,
        "route": route,
    }


def render_pre_arm_readiness_markdown(readiness: Mapping[str, Any]) -> str:
    checks = (
        "cooldownSemanticParity",
        "releaseBindingComplete",
        "remoteFreezePassed",
        "targetedTestsPassed",
        "preExistingTestExceptionAccepted",
        "privateReadVerified",
        "executionUniverseFresh",
        "engineeringSmokeReady",
    )
    lines = [
        "# V46 Provisional Demo Pre-ARM Readiness",
        "",
        f"- Release ID: `{readiness.get('releaseId')}`",
        f"- Release Hash: `{readiness.get('releaseHash')}`",
        f"- Risk Overlay Hash: `{readiness.get('riskOverlayHash')}`",
        f"- Approval ready: `{str(bool(readiness.get('approvalReady'))).lower()}`",
        f"- Route: `{readiness.get('route')}`",
        "- Approved: `false`",
        "- Demo ARM: `false`",
        "- Orders: `0`",
        "- Live: `false`",
        "- Withdraw: `false`",
        "",
        "## Hard Checks",
        "",
    ]
    lines.extend(
        f"- {name}: `{'passed' if readiness.get(name) else 'blocked'}`"
        for name in checks
    )
    blockers = list(readiness.get("blockers") or [])
    lines.extend(["", "## Blockers", ""])
    lines.extend(f"- `{name}`" for name in blockers)
    if not blockers:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)
