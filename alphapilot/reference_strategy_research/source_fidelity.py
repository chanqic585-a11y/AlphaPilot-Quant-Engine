"""Fail-closed source fidelity and candidate lifecycle classification."""

from __future__ import annotations

from typing import Any


_SOURCE_FAITHFUL_EQUIVALENCE_STATUSES = {
    "source_equivalent",
    "source_faithful_verified",
}
_NORMALIZATION_EQUIVALENCE_STATUSES = {
    "deterministic_normalization_only",
}
_INSUFFICIENT_EQUIVALENCE_STATUSES = {
    "not_source_equivalent",
}
_SUPPORTED_EQUIVALENCE_STATUSES = (
    _SOURCE_FAITHFUL_EQUIVALENCE_STATUSES
    | _NORMALIZATION_EQUIVALENCE_STATUSES
    | _INSUFFICIENT_EQUIVALENCE_STATUSES
)


def _has_sha256(value: object) -> bool:
    text = str(value or "").lower()
    return len(text) == 64 and all(character in "0123456789abcdef" for character in text)


def _source_identity_verified(sources: object) -> bool:
    if not isinstance(sources, list) or not sources:
        return False
    return all(
        isinstance(source, dict)
        and bool(str(source.get("path") or "").strip())
        and _has_sha256(source.get("sha256"))
        for source in sources
    )


def classify_source_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    """Classify one candidate without promoting incomplete source evidence."""

    candidate_id = str(candidate.get("candidateId") or "").strip()
    if not candidate_id:
        raise ValueError("candidateId is required")

    equivalence_status = str(candidate.get("equivalenceStatus") or "").strip()
    if equivalence_status not in _SUPPORTED_EQUIVALENCE_STATUSES:
        raise ValueError(f"unsupported equivalence status: {equivalence_status or '<missing>'}")

    material_gaps = sorted({str(gap).strip() for gap in candidate.get("materialGaps") or [] if str(gap).strip()})
    identity_verified = _source_identity_verified(candidate.get("sources"))

    if equivalence_status in _SOURCE_FAITHFUL_EQUIVALENCE_STATUSES:
        source_status = (
            "source_faithful_ready"
            if identity_verified and not material_gaps
            else "insufficient_source_evidence"
        )
    elif equivalence_status in _NORMALIZATION_EQUIVALENCE_STATUSES:
        source_status = "normalization_only" if identity_verified else "insufficient_source_evidence"
    else:
        source_status = "insufficient_source_evidence"

    return {
        "candidateId": candidate_id,
        "equivalenceStatus": equivalence_status,
        "translationClass": str(candidate.get("translationClass") or ""),
        "sourceStatus": source_status,
        "sourceFaithfulReady": source_status == "source_faithful_ready",
        "sourceIdentityVerified": identity_verified,
        "missingRequirementCount": len(material_gaps) + (0 if identity_verified else 1),
        "materialGaps": material_gaps,
        "sources": [dict(source) for source in candidate.get("sources") or []],
    }


def build_source_admission(source_audit: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic admission summary from a source-lineage audit."""

    candidates = sorted(
        (classify_source_candidate(dict(candidate)) for candidate in source_audit.get("candidates") or []),
        key=lambda row: row["candidateId"],
    )
    counts = {
        "source_faithful_ready": 0,
        "normalization_only": 0,
        "insufficient_source_evidence": 0,
    }
    for candidate in candidates:
        counts[candidate["sourceStatus"]] += 1

    return {
        "schemaVersion": "reference_strategy_source_admission_v1",
        "archiveSha256": source_audit.get("archiveSha256"),
        "manifestHash": source_audit.get("manifestHash"),
        "sourceArchiveSha256": source_audit.get("sourceArchiveSha256"),
        "candidateCount": len(candidates),
        "sourceFaithfulReadyCount": counts["source_faithful_ready"],
        "normalizationOnlyCount": counts["normalization_only"],
        "insufficientSourceEvidenceCount": counts["insufficient_source_evidence"],
        "candidates": candidates,
    }


def build_candidate_status_inventory(
    *,
    v36_summary: dict[str, Any],
    v36_selection: dict[str, Any],
    v37b_closeout: dict[str, Any],
    v37c_reassessment: dict[str, Any],
) -> dict[str, Any]:
    """Separate research eligibility, development stability and formal usability."""

    stable_ids = sorted(
        str(selection.get("candidateId"))
        for selection in v36_selection.get("selections") or []
        if selection.get("eligible") is True and selection.get("candidateId")
    )
    reassessment_rows = list(v37c_reassessment.get("candidates") or [])
    formal_pass_ids = sorted(
        str(candidate.get("candidateId"))
        for candidate in reassessment_rows
        if candidate.get("formalPassed") is True and candidate.get("candidateId")
    )
    formal_pass_count = max(int(v36_summary.get("formalRunCount") or 0), len(formal_pass_ids))
    demo_ready_count = max(
        int(v36_summary.get("releaseCount") or 0),
        int(v37b_closeout.get("demoReleaseCount") or 0),
    )

    return {
        "schemaVersion": "reference_strategy_candidate_status_inventory_v1",
        "researchEligibleCount": int(v36_summary.get("eligibleCandidateCount") or 0),
        "developmentStableCount": len(stable_ids),
        "developmentStableCandidateIds": stable_ids,
        "referenceDirectionalCandidateCount": int(v37b_closeout.get("directionalCandidateCount") or len(reassessment_rows)),
        "formalPassCount": formal_pass_count,
        "formalPassCandidateIds": formal_pass_ids,
        "demoReadyCount": demo_ready_count,
        "strictlyUsableStrategyCount": min(formal_pass_count, demo_ready_count),
        "interpretation": {
            "researchEligible": "Eligible for bounded research recheck only.",
            "developmentStable": "Stable in the development neighborhood; locked OOS not yet read.",
            "formalPass": "Passed the frozen formal validation workflow.",
            "demoReady": "Has an immutable approved Demo Release.",
        },
    }
