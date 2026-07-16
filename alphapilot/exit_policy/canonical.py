"""Canonical serialization and hashing for exit policies."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash

from .models import ExitPolicy
from .validation import validate_exit_policy


def _canonical_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _canonical_value(item) for key, item in sorted(value.items())}
    if isinstance(value, (list, tuple)):
        return [_canonical_value(item) for item in value]
    return value


def canonical_exit_policy(policy: ExitPolicy) -> dict[str, Any]:
    validate_exit_policy(policy)
    return {
        "version": policy.version,
        "mode": policy.mode.value,
        "maximumHoldBars": policy.maximumHoldBars,
        "initialStopMayWiden": policy.initialStopMayWiden,
        "parameters": _canonical_value(dict(policy.parameters)),
    }


def exit_policy_hash(policy: ExitPolicy) -> str:
    return stable_hash(canonical_exit_policy(policy), prefix="exit_policy")

