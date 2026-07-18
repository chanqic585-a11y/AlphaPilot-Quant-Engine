"""Immutable identity models for bounded exit policies."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

from .schema import POLICY_VERSION


class ExitPolicyMode(str, Enum):
    FIXED_R = "fixed_r"
    PARTIAL_THEN_TRAILING = "partial_then_trailing"
    STRUCTURE_OR_TIME = "structure_or_time"
    HYBRID = "hybrid"


@dataclass(frozen=True)
class ExitPolicy:
    mode: ExitPolicyMode
    maximumHoldBars: int
    parameters: Mapping[str, Any] = field(default_factory=dict)
    version: str = POLICY_VERSION
    initialStopMayWiden: bool = False

