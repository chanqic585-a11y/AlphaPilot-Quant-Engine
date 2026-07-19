from __future__ import annotations

import pytest

from alphapilot.reference_strategy_research.source_fidelity import (
    build_candidate_status_inventory,
    build_source_admission,
    classify_source_candidate,
)


def _source_row(
    *,
    candidate_id: str,
    equivalence_status: str,
    translation_class: str,
    gaps: list[str],
    suffix: str,
) -> dict[str, object]:
    return {
        "candidateId": candidate_id,
        "equivalenceStatus": equivalence_status,
        "translationClass": translation_class,
        "materialGaps": gaps,
        "sources": [
            {
                "path": f"references/{candidate_id}.{suffix}",
                "sha256": "a" * 64,
                "sizeBytes": 123,
            }
        ],
    }


def test_missing_material_requirements_cannot_be_source_faithful() -> None:
    row = _source_row(
        candidate_id="candidate-a",
        equivalence_status="not_source_equivalent",
        translation_class="clean_room_research_variant",
        gaps=["broker time is not frozen"],
        suffix="mq4",
    )

    result = classify_source_candidate(row)

    assert result["sourceStatus"] == "insufficient_source_evidence"
    assert result["sourceFaithfulReady"] is False
    assert result["missingRequirementCount"] > 0
    assert "broker time is not frozen" in result["materialGaps"]


def test_documentation_normalization_stays_normalization_only() -> None:
    row = _source_row(
        candidate_id="candidate-b",
        equivalence_status="deterministic_normalization_only",
        translation_class="documentation_normalization",
        gaps=["source is qualitative prose"],
        suffix="txt",
    )

    result = classify_source_candidate(row)

    assert result["sourceStatus"] == "normalization_only"
    assert result["sourceFaithfulReady"] is False
    assert result["sourceIdentityVerified"] is True


def test_source_admission_has_deterministic_counts_and_order() -> None:
    audit = {
        "archiveSha256": "f" * 64,
        "manifestHash": "e" * 64,
        "sourceArchiveSha256": "d" * 64,
        "candidates": [
            _source_row(
                candidate_id="z-normalized",
                equivalence_status="deterministic_normalization_only",
                translation_class="documentation_normalization",
                gaps=["qualitative source"],
                suffix="txt",
            ),
            _source_row(
                candidate_id="a-insufficient",
                equivalence_status="not_source_equivalent",
                translation_class="clean_room_research_variant",
                gaps=["pending order semantics missing"],
                suffix="mq4",
            ),
        ],
    }

    result = build_source_admission(audit)

    assert result["candidateCount"] == 2
    assert result["sourceFaithfulReadyCount"] == 0
    assert result["normalizationOnlyCount"] == 1
    assert result["insufficientSourceEvidenceCount"] == 1
    assert [row["candidateId"] for row in result["candidates"]] == [
        "a-insufficient",
        "z-normalized",
    ]


def test_unsupported_equivalence_status_fails_closed() -> None:
    row = _source_row(
        candidate_id="candidate-unknown",
        equivalence_status="maybe_equivalent",
        translation_class="unknown",
        gaps=[],
        suffix="py",
    )

    with pytest.raises(ValueError, match="unsupported equivalence status"):
        classify_source_candidate(row)


def test_candidate_inventory_does_not_call_research_candidates_formal_passes() -> None:
    result = build_candidate_status_inventory(
        v36_summary={
            "eligibleCandidateCount": 6,
            "stableSelectionCount": 2,
            "formalRunCount": 0,
            "releaseCount": 0,
        },
        v36_selection={
            "selections": [
                {"candidateId": "stable-a", "eligible": True},
                {"candidateId": "stable-b", "eligible": True},
                {"candidateId": "unstable-c", "eligible": False},
            ]
        },
        v37b_closeout={
            "directionalCandidateCount": 4,
            "demoReleaseCount": 0,
        },
        v37c_reassessment={
            "candidates": [
                {"candidateId": "ref-a", "formalPassed": False},
                {"candidateId": "ref-b", "formalPassed": False},
                {"candidateId": "ref-c", "formalPassed": False},
                {"candidateId": "ref-d", "formalPassed": False},
            ]
        },
    )

    assert result["researchEligibleCount"] == 6
    assert result["developmentStableCount"] == 2
    assert result["developmentStableCandidateIds"] == ["stable-a", "stable-b"]
    assert result["referenceDirectionalCandidateCount"] == 4
    assert result["formalPassCount"] == 0
    assert result["demoReadyCount"] == 0
    assert result["strictlyUsableStrategyCount"] == 0
