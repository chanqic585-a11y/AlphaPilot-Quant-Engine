"""Fail-closed local sandbox for generated research candidates."""

from .resource_limits import ResourceLimits
from .runtime import SandboxResult, run_candidate

__all__ = ["ResourceLimits", "SandboxResult", "run_candidate"]
