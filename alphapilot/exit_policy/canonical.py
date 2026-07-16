"""Canonical serialization and hashing for exit policies."""

from __future__ import annotations

from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash

from .models import ExitPolicy, ExitPolicyMode
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


def exit_policy_from_dict(payload: Any) -> ExitPolicy:
    if not isinstance(payload, dict):
        raise ValueError("exitPolicy must be an object")
    expected = {
        "version",
        "mode",
        "maximumHoldBars",
        "initialStopMayWiden",
        "parameters",
    }
    if set(payload) != expected:
        missing = expected - set(payload)
        unknown = set(payload) - expected
        raise ValueError(
            f"invalid exitPolicy fields; missing={sorted(missing)}, unknown={sorted(unknown)}"
        )
    if not isinstance(payload["maximumHoldBars"], int) or isinstance(
        payload["maximumHoldBars"], bool
    ):
        raise ValueError("maximumHoldBars must be an integer")
    if not isinstance(payload["initialStopMayWiden"], bool):
        raise ValueError("initialStopMayWiden must be a boolean")
    if not isinstance(payload["parameters"], Mapping):
        raise ValueError("parameters must be an object")
    try:
        mode = ExitPolicyMode(str(payload["mode"]))
    except ValueError as exc:
        raise ValueError(f"unsupported exit-policy mode: {payload['mode']}") from exc
    policy = ExitPolicy(
        version=str(payload["version"]),
        mode=mode,
        maximumHoldBars=payload["maximumHoldBars"],
        initialStopMayWiden=payload["initialStopMayWiden"],
        parameters=dict(payload["parameters"]),
    )
    return validate_exit_policy(policy)
