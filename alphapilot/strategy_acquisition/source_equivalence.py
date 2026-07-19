"""Source-fidelity labels used by acquisition and candidate reports."""

from __future__ import annotations

from dataclasses import dataclass


SOURCE_EQUIVALENCE_CLASSES = frozenset(
    {
        "exact_executable_source",
        "source_faithful_reproduction",
        "clean_room_normalized_variant",
        "mechanism_only",
        "insufficient_source_evidence",
    }
)


@dataclass(frozen=True)
class SourceEquivalenceDecision:
    classification: str
    currentImplementationProves: str
    doesNotProve: str


def decide_source_equivalence(
    *, readable_executable_source: bool, exact_formula: bool, clean_room: bool
) -> SourceEquivalenceDecision:
    if readable_executable_source and not clean_room:
        classification = "exact_executable_source"
    elif exact_formula:
        classification = "source_faithful_reproduction"
    elif clean_room:
        classification = "clean_room_normalized_variant"
    else:
        classification = "insufficient_source_evidence"
    return SourceEquivalenceDecision(
        classification=classification,
        currentImplementationProves="the registered AlphaPilot implementation only",
        doesNotProve="the original author's unobserved implementation or performance",
    )
