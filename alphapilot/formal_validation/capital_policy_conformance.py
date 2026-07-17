"""Strict conformance checks for the frozen V18 Capital Policy V2."""
from __future__ import annotations

from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import canonical_json

from .executable_capital_policy import build_capital_policy_v2


def audit_capital_policy_v2(policy: Mapping[str, Any]) -> list[dict[str, Any]]:
    expected = build_capital_policy_v2()
    if canonical_json(dict(policy)) == canonical_json(expected):
        return []
    return [
        {
            "code": "capital_policy_contract_mismatch",
            "severity": "blocking",
            "description": (
                "Capital Policy V2 differs from the only executable frozen contract."
            ),
            "requiresNewCampaign": True,
            "resultExecutionAllowed": False,
        }
    ]


def verify_capital_policy_v2(policy: Mapping[str, Any]) -> bool:
    return not audit_capital_policy_v2(policy)
