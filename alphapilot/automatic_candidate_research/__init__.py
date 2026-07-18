"""Bounded automatic candidate research for AlphaPilot V36."""

from .executor import AutomaticCandidateResearchExecutor
from .development_replay import build_development_evidence, load_development_frames
from .formal_routing import route_formal_outcomes
from .preregistration import build_preregistration
from .selection import project_development_evidence, select_stable_neighborhood

__all__ = [
    "AutomaticCandidateResearchExecutor",
    "build_development_evidence",
    "build_preregistration",
    "load_development_frames",
    "project_development_evidence",
    "route_formal_outcomes",
    "select_stable_neighborhood",
]
