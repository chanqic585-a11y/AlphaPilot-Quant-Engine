"""Audited, read-only references used by AlphaPilot research."""

from .adoption_matrix import AdoptionRecord, validate_adoption_matrix
from .reference_manifest import ExternalReference

__all__ = ["AdoptionRecord", "ExternalReference", "validate_adoption_matrix"]
