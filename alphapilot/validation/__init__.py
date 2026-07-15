"""Research-only candidate evidence closure validation."""

from .candidate_deduplication import deduplicate_candidates
from .candidate_selection import discover_candidates

__all__ = ["deduplicate_candidates", "discover_candidates"]

