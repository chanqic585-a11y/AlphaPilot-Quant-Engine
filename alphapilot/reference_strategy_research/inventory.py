"""Deterministic inventory and semantic-deduplication decisions."""

from __future__ import annotations

from typing import Any, Iterable

from alphapilot.evolution.registry.hashing import stable_hash


_SELECTED = {
    "ref_utc_session_range_breakout_1h_v1",
    "ref_pa_breakout_failure_second_entry_4h_v1",
}
_DUPLICATES = {
    "ref_turtle_donchian_20_10_4h_v1": "crypto_tsmom_turtle_v1",
}
_FORWARD_ONLY_MARKERS = ("tick", "news", "basis", "orderbook", "order_book", "l2")
_RESEARCH_LATER_MARKERS = ("wedge", "spike", "fractal")


def _disposition(candidate_id: str, family_id: str) -> tuple[str, str | None, str]:
    if candidate_id in _SELECTED:
        return "selected_bounded_research", None, "incremental causal hypothesis"
    if candidate_id in _DUPLICATES:
        return "duplicate_existing", _DUPLICATES[candidate_id], "semantic family already registered"
    identity = f"{candidate_id} {family_id}".lower()
    if any(marker in identity for marker in _FORWARD_ONLY_MARKERS):
        return "forward_data_required", None, "requires unavailable point-in-time forward evidence"
    if any(marker in identity for marker in _RESEARCH_LATER_MARKERS):
        return "research_later", None, "requires a separate bounded hypothesis campaign"
    return "insufficient_evidence", None, "package metadata is not formal AlphaPilot evidence"


def build_candidate_inventory(candidates: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id = str(candidate.get("candidateId") or "")
        family_id = str(candidate.get("familyId") or "")
        disposition, overlap, reason = _disposition(candidate_id, family_id)
        fingerprint_core = {
            "familyId": family_id,
            "timeframe": candidate.get("timeframe"),
            "directions": candidate.get("directions"),
            "signal": candidate.get("signal"),
            "initialStop": candidate.get("initialStop"),
            "exitPolicy": candidate.get("exitPolicy"),
        }
        rows.append(
            {
                "candidateId": candidate_id,
                "familyId": family_id,
                "timeframe": candidate.get("timeframe"),
                "disposition": disposition,
                "overlapWith": overlap,
                "reason": reason,
                "semanticFingerprint": stable_hash(fingerprint_core, prefix="reference_semantic"),
                "sourceCandidateSpecHash": candidate.get("candidateSpecHash"),
            }
        )
    return rows
