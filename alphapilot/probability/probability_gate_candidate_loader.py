"""Load and validate V13.4.20 research-only probability gate candidates."""

from __future__ import annotations

import json
from pathlib import Path

from alphapilot.probability.probability_gate_candidate_schema import ProbabilityGateCandidate
from alphapilot.probability.probability_gate_candidates import DEFAULT_CANDIDATE_CONFIG_DIR

FORBIDDEN_ALLOWED_BUCKET_TERMS = ("avoid", "unknown", "no_entry")


def _read_candidate(path: Path) -> ProbabilityGateCandidate:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return ProbabilityGateCandidate.from_dict(payload)


def _bucket_is_forbidden(bucket_id: str) -> bool:
    parts = bucket_id.split("_")
    if parts and parts[0] in {"avoid", "unknown"}:
        return True
    return any(term in bucket_id for term in FORBIDDEN_ALLOWED_BUCKET_TERMS)


def validate_probability_gate_candidate(candidate: ProbabilityGateCandidate) -> None:
    if candidate.status != "research_only":
        raise ValueError(f"{candidate.candidateGateId} must have status=research_only.")
    if candidate.useForTrading:
        raise ValueError(f"{candidate.candidateGateId} must not set useForTrading=true.")
    if candidate.useForDryRun:
        raise ValueError(f"{candidate.candidateGateId} must not set useForDryRun=true.")
    if not candidate.allowedBuckets:
        raise ValueError(f"{candidate.candidateGateId} must contain at least one allowed bucket.")
    if not candidate.sourceTables:
        raise ValueError(f"{candidate.candidateGateId} must define sourceTable or sourceTables.")
    for source_table in candidate.sourceTables:
        if not Path(source_table).exists():
            raise ValueError(f"{candidate.candidateGateId} source table does not exist: {source_table}")
    for bucket_id in candidate.allowedBuckets:
        if _bucket_is_forbidden(bucket_id):
            raise ValueError(f"{candidate.candidateGateId} cannot allow diagnostic bucket: {bucket_id}")


def load_probability_gate_candidate(
    candidate_id: str,
    config_dir: Path = DEFAULT_CANDIDATE_CONFIG_DIR,
) -> ProbabilityGateCandidate:
    path = config_dir / f"{candidate_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Probability gate candidate not found: {path}")
    candidate = _read_candidate(path)
    validate_probability_gate_candidate(candidate)
    return candidate


def list_probability_gate_candidates(
    config_dir: Path = DEFAULT_CANDIDATE_CONFIG_DIR,
) -> list[ProbabilityGateCandidate]:
    candidates = [_read_candidate(path) for path in sorted(config_dir.glob("*.json"))]
    for candidate in candidates:
        validate_probability_gate_candidate(candidate)
    return candidates
