"""Stable JSON mapping for Advisory-R execution evidence."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .canonical import canonical_exit_policy
from .exit_legs import ExitExecutionResult


def exit_execution_to_dict(result: ExitExecutionResult) -> dict[str, Any]:
    payload = asdict(result)
    payload["exitPolicy"] = canonical_exit_policy(result.exitPolicy)
    payload["legs"] = [asdict(leg) for leg in result.legs]
    payload["stopHistory"] = list(result.stopHistory)
    return payload

