"""Shared research artifacts for the Demo and Live adaptive-learning core."""

from .offline_evidence import build_offline_evidence
from .production_factor_registry import build_production_factor_registry

__all__ = ["build_offline_evidence", "build_production_factor_registry"]
