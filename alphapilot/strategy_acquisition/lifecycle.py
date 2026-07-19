"""Bounded strategy-artifact lifecycle rules."""

from __future__ import annotations


class InvalidLifecycleTransition(ValueError):
    pass


LIFECYCLE_STATES = (
    "source_ingested",
    "mechanism_extracted",
    "data_blocked",
    "candidate_draft",
    "candidate_frozen",
    "prefilter_running",
    "prefilter_failed",
    "formal_running",
    "formal_failed",
    "research_pass",
    "formal_pass",
    "release_ready",
    "demo_monitoring",
    "decayed",
    "disabled",
    "archived",
)

_ALLOWED: dict[str, frozenset[str]] = {
    "source_ingested": frozenset({"mechanism_extracted", "data_blocked", "archived"}),
    "mechanism_extracted": frozenset({"data_blocked", "candidate_draft", "archived"}),
    "data_blocked": frozenset({"mechanism_extracted", "archived"}),
    "candidate_draft": frozenset({"candidate_frozen", "archived"}),
    "candidate_frozen": frozenset({"prefilter_running", "archived"}),
    "prefilter_running": frozenset({"prefilter_failed", "research_pass", "formal_running"}),
    "prefilter_failed": frozenset({"archived"}),
    "research_pass": frozenset({"formal_running", "release_ready", "archived"}),
    "formal_running": frozenset(
        {"formal_failed", "research_pass", "formal_pass", "data_blocked"}
    ),
    "formal_failed": frozenset({"archived"}),
    "formal_pass": frozenset({"release_ready"}),
    "release_ready": frozenset({"demo_monitoring", "disabled"}),
    "demo_monitoring": frozenset({"decayed", "disabled"}),
    "decayed": frozenset({"disabled", "archived"}),
    "disabled": frozenset({"archived"}),
    "archived": frozenset(),
}


def validate_transition(previous: str, next_status: str) -> None:
    if previous not in _ALLOWED or next_status not in LIFECYCLE_STATES:
        raise InvalidLifecycleTransition(f"unknown lifecycle state: {previous} -> {next_status}")
    if next_status not in _ALLOWED[previous]:
        raise InvalidLifecycleTransition(
            f"invalid lifecycle transition: {previous} -> {next_status}"
        )
