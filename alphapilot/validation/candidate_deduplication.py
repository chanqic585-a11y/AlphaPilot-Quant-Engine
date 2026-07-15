from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable

from .models import CandidateDeduplicationReport, CandidateVersion


def _identity(candidate: CandidateVersion) -> tuple[str, str, str]:
    if candidate.source_signal_hash:
        return candidate.strategy_family, "signal", candidate.source_signal_hash
    definition_hash = candidate.source_definition_hash or candidate.strategy_version_id
    return candidate.strategy_family, "definition", definition_hash


def deduplicate_candidates(
    candidates: Iterable[CandidateVersion],
) -> CandidateDeduplicationReport:
    versions = sorted(candidates, key=lambda item: item.strategy_version_id)
    grouped: dict[tuple[str, str, str], list[CandidateVersion]] = defaultdict(list)
    family_hashes: dict[str, set[str]] = defaultdict(set)
    for candidate in versions:
        grouped[_identity(candidate)].append(candidate)
        family_hashes[candidate.strategy_family].add(
            candidate.source_signal_hash
            or candidate.source_definition_hash
            or candidate.strategy_version_id
        )

    representatives: list[CandidateVersion] = []
    mapping: dict[str, str] = {}
    for key in sorted(grouped):
        members = grouped[key]
        representative = members[0]
        representatives.append(representative)
        for member in members:
            mapping[member.strategy_version_id] = representative.strategy_version_id

    conflicts = {
        family: sorted(hashes)
        for family, hashes in sorted(family_hashes.items())
        if len(hashes) > 1
    }
    return CandidateDeduplicationReport(
        candidate_version_count=len(versions),
        candidate_family_count=len({item.strategy_family for item in versions}),
        canonical_representative_count=len(representatives),
        duplicate_version_count=len(versions) - len(representatives),
        canonical_candidates=representatives,
        version_to_representative=mapping,
        family_definition_conflicts=conflicts,
    )
