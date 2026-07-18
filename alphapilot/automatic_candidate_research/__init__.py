"""Bounded automatic candidate research for AlphaPilot V36."""

from .executor import AutomaticCandidateResearchExecutor
from .formal_routing import route_formal_outcomes
from .preregistration import build_preregistration
from .selection import project_development_evidence, select_stable_neighborhood

__all__ = [
    "AutomaticCandidateResearchExecutor",
    "build_preregistration",
    "project_development_evidence",
    "route_formal_outcomes",
    "select_stable_neighborhood",
]
