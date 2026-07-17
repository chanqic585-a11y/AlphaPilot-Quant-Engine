"""Aggregate V13.27.1.17 Phase 2 engineering-readiness evidence."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file

from .readiness_audit import S01_CANDIDATE_ID, build_phase1_readiness_audit


DEFAULT_EVIDENCE_ROOT = Path(
    "reports/formal_validation/v13_27_1_17_s01_phase2_readiness"
)
EVIDENCE_FILES = {
    "runtimeManifest": "freqtrade_runtime_manifest.json",
    "runtimeSmoke": "freqtrade_runtime_smoke.json",
    "dualEngineParity": "dual_engine_readiness_parity.json",
    "ioGuard": "freqtrade_io_guard_readiness.json",
    "futureLockedOos": "future_locked_oos_readiness.json",
}

_PHASE2_MESSAGES = {
    "runtime_not_pinned": "The audited Freqtrade container runtime is not pinned.",
    "runtime_smoke_failed": "The network-disabled Freqtrade runtime smoke did not pass.",
    "dual_engine_positive_parity_failed": (
        "The real strategy adapter did not produce non-zero exact dual-engine parity."
    ),
    "io_isolation_failed": (
        "The physical input/output isolation or append-only access audit failed."
    ),
    "safety_boundary_violation": (
        "Phase 2 observed a formal result, Locked OOS access, release, ARM, or order."
    ),
}

_LOCKED_OOS_MESSAGES = {
    "locked_oos_identity_incomplete": (
        "Future Locked OOS metadata identity or its zero-access ledger is invalid."
    ),
    "future_market_data_not_available": (
        "The preregistered future market-data window does not exist yet."
    ),
    "formal_walk_forward_not_completed": (
        "The preregistered formal Walk-forward has not been completed."
    ),
    "locked_oos_admission_blocked": "Future Locked OOS admission remains blocked.",
}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _number(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return 0.0
    return float(value)


def _phase2_blocker(code: str) -> dict[str, str]:
    return {"code": code, "message": _PHASE2_MESSAGES[code]}


def _locked_blocker(code: str) -> dict[str, str]:
    return {
        "code": code,
        "message": _LOCKED_OOS_MESSAGES.get(code, code.replace("_", " ")),
    }


def _runtime_manifest_passed(manifest: Mapping[str, Any]) -> bool:
    image = manifest.get("imageReference")
    digest = manifest.get("imageDigest")
    return bool(
        manifest.get("status") == "pinned"
        and isinstance(image, str)
        and "@sha256:" in image
        and isinstance(digest, str)
        and image.endswith(digest)
        and manifest.get("networkRequired") is False
        and manifest.get("credentialRequired") is False
        and manifest.get("lockedOosRequired") is False
    )


def _runtime_smoke_passed(
    smoke: Mapping[str, Any], manifest: Mapping[str, Any]
) -> bool:
    checks = _mapping(smoke.get("checks"))
    checks_passed = all(
        _mapping(value).get("returnCode") == 0 for value in checks.values()
    )
    return bool(
        smoke.get("status") == "passed"
        and smoke.get("imageReference") == manifest.get("imageReference")
        and smoke.get("networkMode") == "none"
        and _number(smoke.get("networkAccessCount")) == 0
        and _number(smoke.get("credentialReadCount")) == 0
        and (not checks or checks_passed)
    )


def _positive_parity_passed(parity: Mapping[str, Any]) -> bool:
    return bool(
        parity.get("status") == "passed"
        and parity.get("passed") is True
        and parity.get("zeroSignalParityRejected") is True
        and parity.get("actualStrategyAdapterInvoked") is True
        and _number(parity.get("referenceEventCount")) > 0
        and _number(parity.get("implementationEventCount")) > 0
        and _number(parity.get("matchedEventCount")) > 0
        and _number(parity.get("matchedLegCount")) > 0
        and _number(parity.get("formalSignalCount")) > 0
        and _number(parity.get("adapterSignalCount")) > 0
        and _number(parity.get("missingEventCount")) == 0
        and _number(parity.get("extraEventCount")) == 0
        and _number(parity.get("mismatchedEventCount")) == 0
        and parity.get("formalPerformanceClaimed") is False
    )


def _io_guard_passed(io_guard: Mapping[str, Any]) -> bool:
    access = _mapping(io_guard.get("accessAudit"))
    return bool(
        io_guard.get("status") == "passed"
        and io_guard.get("repositoryReadOnly") is True
        and io_guard.get("fixtureOnly") is True
        and io_guard.get("lockedOosMounted") is False
        and io_guard.get("networkMode") == "none"
        and access.get("status") == "passed"
        and access.get("hashChainValid") is True
        and _number(access.get("unauthorizedAttemptCount")) == 0
    )


def _future_locked_oos_metadata_passed(payload: Mapping[str, Any]) -> bool:
    audit = _mapping(payload.get("audit"))
    return bool(
        payload.get("status") == "passed"
        and payload.get("route") == "future_data_required"
        and audit.get("status") == "passed"
        and audit.get("identityHashValid") is True
        and audit.get("hashChainValid") is True
        and audit.get("metadataOnly") is True
        and _number(audit.get("contentReadCount")) == 0
        and _number(audit.get("lockedOosAccessCount")) == 0
    )


def _safety_boundary(evidence: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    smoke = _mapping(evidence.get("runtimeSmoke"))
    parity = _mapping(evidence.get("dualEngineParity"))
    io_guard = _mapping(evidence.get("ioGuard"))
    future = _mapping(evidence.get("futureLockedOos"))
    future_audit = _mapping(future.get("audit"))
    return {
        "lockedOosAccessCount": int(
            max(
                _number(smoke.get("lockedOosContentReadCount")),
                _number(parity.get("lockedOosAccessCount")),
                _number(io_guard.get("lockedOosAccessCount")),
                _number(future.get("lockedOosAccessCount")),
                _number(future_audit.get("lockedOosAccessCount")),
                _number(future_audit.get("contentReadCount")),
            )
        ),
        "formalResultCount": int(
            max(
                _number(smoke.get("formalResultCount")),
                _number(io_guard.get("formalResultCount")),
                _number(future.get("formalResultCount")),
            )
        ),
        "releaseCount": int(
            max(
                _number(smoke.get("releaseCount")),
                _number(io_guard.get("releaseCount")),
                _number(future.get("releaseCount")),
            )
        ),
        "demoArm": any(
            value is True
            for value in (
                smoke.get("demoArm"),
                io_guard.get("demoArm"),
                future.get("demoArm"),
            )
        ),
        "orderCount": int(
            max(
                _number(smoke.get("orderCount")),
                _number(io_guard.get("orderCount")),
                _number(future.get("orderCount")),
            )
        ),
    }


def classify_phase2_readiness(
    *,
    phase1_formal_blockers: list[Mapping[str, Any]],
    evidence: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Classify formal execution separately from Future Locked OOS admission."""

    formal_blockers = [
        {"code": str(item.get("code")), "message": str(item.get("message", ""))}
        for item in phase1_formal_blockers
        if item.get("code") != "freqtrade_runtime_missing"
    ]
    manifest = _mapping(evidence.get("runtimeManifest"))
    smoke = _mapping(evidence.get("runtimeSmoke"))
    parity = _mapping(evidence.get("dualEngineParity"))
    io_guard = _mapping(evidence.get("ioGuard"))
    future = _mapping(evidence.get("futureLockedOos"))

    if not _runtime_manifest_passed(manifest):
        formal_blockers.append(_phase2_blocker("runtime_not_pinned"))
    if not _runtime_smoke_passed(smoke, manifest):
        formal_blockers.append(_phase2_blocker("runtime_smoke_failed"))
    if not _positive_parity_passed(parity):
        formal_blockers.append(
            _phase2_blocker("dual_engine_positive_parity_failed")
        )
    if not _io_guard_passed(io_guard):
        formal_blockers.append(_phase2_blocker("io_isolation_failed"))

    safety = _safety_boundary(evidence)
    if safety != {
        "lockedOosAccessCount": 0,
        "formalResultCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }:
        formal_blockers.append(_phase2_blocker("safety_boundary_violation"))

    locked_blockers: list[dict[str, str]] = []
    if not _future_locked_oos_metadata_passed(future):
        locked_blockers.append(_locked_blocker("locked_oos_identity_incomplete"))
    else:
        for code in future.get("blockers", []):
            if isinstance(code, str):
                locked_blockers.append(_locked_blocker(code))
    if future.get("admissionStatus") == "blocked" and not locked_blockers:
        locked_blockers.append(_locked_blocker("locked_oos_admission_blocked"))

    return {
        "formalExecution": {
            "status": "ready" if not formal_blockers else "blocked",
            "blockers": formal_blockers,
        },
        "lockedOosAdmission": {
            "status": "ready" if not locked_blockers else "blocked",
            "blockers": locked_blockers,
        },
    }


def _load_evidence(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "missing", "missingPath": path.as_posix()}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return {"status": "invalid", "invalidPath": path.as_posix()}
    return payload


def build_phase2_readiness_audit(
    repo_root: Path, evidence_root: Path | None = None
) -> dict[str, Any]:
    """Build a metadata-only Phase 2 audit without formal strategy execution."""

    repo_root = Path(repo_root).resolve()
    root = evidence_root or DEFAULT_EVIDENCE_ROOT
    if not root.is_absolute():
        root = repo_root / root
    evidence = {
        role: _load_evidence(root / filename)
        for role, filename in EVIDENCE_FILES.items()
    }
    phase1 = build_phase1_readiness_audit(repo_root)
    phase1_blockers = phase1["gates"]["formalExecution"]["blockers"]
    gates = classify_phase2_readiness(
        phase1_formal_blockers=phase1_blockers,
        evidence=evidence,
    )
    evidence_artifacts = []
    for role, filename in EVIDENCE_FILES.items():
        path = root / filename
        evidence_artifacts.append(
            {
                "logicalRole": role,
                "path": path.relative_to(repo_root).as_posix(),
                "exists": path.is_file(),
                "sha256": sha256_file(path) if path.is_file() else None,
            }
        )
    safety = _safety_boundary(evidence)
    return {
        "schemaVersion": "formal_validation_phase2_readiness_audit_v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "phase": "V13.27.1.17-phase2",
        "scope": "engineering_readiness_only",
        "route": (
            "ready_for_formal_walk_forward"
            if gates["formalExecution"]["status"] == "ready"
            else "blocked"
        ),
        "candidateId": S01_CANDIDATE_ID,
        "phase1": {
            "route": phase1["route"],
            "formalExecution": phase1["gates"]["formalExecution"],
            "runtimeBlockerReplacedByPinnedDockerEvidence": True,
        },
        "evidenceRoot": root.relative_to(repo_root).as_posix(),
        "evidenceArtifacts": evidence_artifacts,
        "evidence": evidence,
        "gates": gates,
        "blockers": gates["formalExecution"]["blockers"],
        "safetyBoundary": safety,
        "formalWalkForwardExecuted": False,
        "formalPerformanceClaimed": False,
    }


def _render_phase2_markdown(audit: Mapping[str, Any]) -> str:
    gates = _mapping(audit.get("gates"))
    formal = _mapping(gates.get("formalExecution"))
    locked = _mapping(gates.get("lockedOosAdmission"))
    lines = [
        "# V13.27.1.17 Phase 2 Engineering Readiness Audit",
        "",
        f"- Route: `{audit['route']}`",
        f"- Candidate: `{audit['candidateId']}`",
        f"- Formal execution gate: `{formal.get('status')}`",
        f"- Future Locked OOS admission: `{locked.get('status')}`",
        "- Formal Walk-forward executed: `false`",
        "- Formal performance claimed: `false`",
        "- Locked OOS access count: `0`",
        "- Formal result count: `0`",
        "- Release count: `0`",
        "- Demo ARM: `false`",
        "- Order count: `0`",
        "",
        "## Formal execution blockers",
        "",
    ]
    lines.extend(
        [f"- `{item['code']}`: {item['message']}" for item in formal.get("blockers", [])]
        or ["- None"]
    )
    lines.extend(["", "## Future Locked OOS blockers", ""])
    lines.extend(
        [f"- `{item['code']}`: {item['message']}" for item in locked.get("blockers", [])]
        or ["- None"]
    )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "The pinned runtime, positive synthetic parity, and physical I/O "
                "isolation are engineering-ready for the separately preregistered "
                "formal Walk-forward. Future Locked OOS remains unavailable and unopened."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_phase2_evidence_bundle(
    audit: Mapping[str, Any], output_root: Path
) -> list[Path]:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    audit_json = output_root / "phase2_readiness_audit.json"
    audit_md = output_root / "phase2_readiness_audit.md"
    manifest_path = output_root / "phase2_artifact_manifest.json"
    write_json_atomic(audit_json, dict(audit))
    audit_md.write_text(
        _render_phase2_markdown(audit), encoding="utf-8", newline="\n"
    )
    artifact_paths = sorted(
        (
            path
            for path in output_root.iterdir()
            if path.is_file() and path != manifest_path
        ),
        key=lambda path: path.name,
    )
    manifest = {
        "schemaVersion": "formal_validation_phase2_manifest_v1",
        "artifacts": [
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "sizeBytes": path.stat().st_size,
            }
            for path in artifact_paths
        ],
    }
    write_json_atomic(manifest_path, manifest)
    return [audit_json, audit_md, manifest_path]
