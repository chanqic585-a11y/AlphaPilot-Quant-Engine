"""Mechanical pre-run routing for the V17 formal validation campaign.

This module intentionally does not load market data.  It is the last guard
before formal execution and terminates the campaign when the frozen contract
does not define every result-affecting calculation.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

from alphapilot.data_foundation.checkpoint import write_json_atomic


TERMINAL_ROUTE = "implementation_invalid_requires_new_campaign"

_ISSUES = {
    "capacity_model_not_frozen": (
        "Capacity model and executable thresholds are not frozen.",
        "Freeze the capacity inputs, thresholds, missing-data policy, and derivation method in a new campaign.",
    ),
    "correlation_cluster_policy_not_frozen": (
        "Correlation-cluster assignment is not frozen.",
        "Freeze the return window, correlation method, threshold, clustering algorithm, and fallback policy in a new campaign.",
    ),
    "portfolio_beta_policy_not_frozen": (
        "Portfolio beta derivation is not frozen.",
        "Freeze the benchmark, lookback, estimator, alignment, and missing-data policy in a new campaign.",
    ),
    "ranking_field_definitions_not_frozen": (
        "The ranking order names fields whose executable definitions are not frozen.",
        "Freeze each ranking field derivation and null/tie policy in a new campaign.",
    ),
}


def _mapping(value: object) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _complete_definition(value: object, required: Sequence[str]) -> bool:
    definition = _mapping(value)
    return all(definition.get(key) not in (None, "", [], {}) for key in required)


def _issue(code: str) -> dict[str, Any]:
    description, action = _ISSUES[code]
    return {
        "code": code,
        "description": description,
        "issueType": "frozen_execution_contract_gap",
        "severity": "blocking",
        "affectsStrategyLogic": False,
        "affectsResultComputation": True,
        "affectsResultValidity": True,
        "requiresPatch": False,
        "requiresResultRerun": False,
        "requiresNewCampaign": True,
        "status": "requires_new_campaign",
        "recommendedAction": action,
    }


def audit_executable_formal_contract(
    preregistration: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return frozen-contract gaps without reading any performance input."""

    policy = _mapping(preregistration.get("capitalCompetitionPolicy"))
    issues: list[dict[str, Any]] = []
    if not _complete_definition(
        policy.get("capacityModel"),
        ("method", "inputs", "thresholds", "missingDataPolicy"),
    ):
        issues.append(_issue("capacity_model_not_frozen"))
    if not _complete_definition(
        policy.get("correlationClusterPolicy"),
        ("method", "lookbackBars", "threshold", "missingDataPolicy"),
    ):
        issues.append(_issue("correlation_cluster_policy_not_frozen"))
    if not _complete_definition(
        policy.get("portfolioBetaPolicy"),
        ("benchmark", "method", "lookbackBars", "missingDataPolicy"),
    ):
        issues.append(_issue("portfolio_beta_policy_not_frozen"))

    definitions = _mapping(policy.get("rankingFieldDefinitions"))
    expected = {
        "residual_z_more_extreme_first",
        "recovery_confirmation_stronger_first",
        "liquidity_higher_first",
        "symbol_id_ascending_tiebreak",
    }
    if not expected.issubset(definitions) or any(
        definitions.get(key) in (None, "", {}, []) for key in expected
    ):
        issues.append(_issue("ranking_field_definitions_not_frozen"))
    return issues


def build_pre_run_terminal_route(
    preregistration: Mapping[str, Any],
    issues: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    if not issues:
        raise ValueError("A terminal pre-run route requires at least one blocker")
    return {
        "schemaVersion": "s01_formal_pre_run_route_v1",
        "campaignId": preregistration.get("campaignId"),
        "candidateId": preregistration.get("sourceCandidateId"),
        "preregistrationHash": preregistration.get("preregistrationHash"),
        "route": TERMINAL_ROUTE,
        "routeStage": "before_formal_performance_execution",
        "terminal": True,
        "formalPass": False,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "formalPerformanceArtifactCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "blockerCodes": [str(issue["code"]) for issue in issues],
        "requiresNewCampaign": True,
        "preserveOriginalCampaign": True,
    }


def _gate_matrix(route: Mapping[str, Any], issues: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "s01_formal_gate_matrix_v1",
        "campaignId": route.get("campaignId"),
        "route": route.get("route"),
        "gates": [
            {
                "gateId": "executable_frozen_contract",
                "status": "failed",
                "blocking": True,
                "reasonCodes": [str(issue["code"]) for issue in issues],
            },
            {
                "gateId": "formal_performance_execution",
                "status": "not_run",
                "blocking": False,
                "reasonCodes": [TERMINAL_ROUTE],
            },
            {
                "gateId": "locked_oos_admission",
                "status": "intentional_safety_block",
                "blocking": True,
                "reasonCodes": ["clean_locked_oos_unavailable"],
            },
            {
                "gateId": "release_demo_order",
                "status": "not_run",
                "blocking": True,
                "reasonCodes": ["zero_formal_pass_evidence"],
            },
        ],
    }


def _failure_attribution(
    route: Mapping[str, Any], issues: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    return {
        "schemaVersion": "s01_formal_failure_attribution_v1",
        "campaignId": route.get("campaignId"),
        "route": route.get("route"),
        "failureLayer": "implementation_contract",
        "performanceResultAvailable": False,
        "strategyEconomicFailureClaimed": False,
        "issues": [dict(issue) for issue in issues],
        "recommendedAction": (
            "Preserve V17 unchanged and create a new preregistered campaign "
            "with complete executable capital-policy definitions."
        ),
    }


def _summary(route: Mapping[str, Any], issues: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    return {
        "schemaVersion": "s01_formal_campaign_summary_v1",
        "campaignId": route.get("campaignId"),
        "candidateCount": 1,
        "formalPassCount": 0,
        "route": route.get("route"),
        "status": "completed_terminal_pre_run",
        "formalRunCount": 0,
        "resultReadCount": 0,
        "formalMetrics": None,
        "blockerCount": len(issues),
        "blockerCodes": [str(issue["code"]) for issue in issues],
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "requiresNewCampaign": True,
    }


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    blockers = "\n".join(f"- `{code}`" for code in summary["blockerCodes"])
    return (
        "# V13.27.1.17 Formal Validation Summary\n\n"
        f"- Campaign: `{summary['campaignId']}`\n"
        f"- Route: `{summary['route']}`\n"
        "- Formal performance run: not run\n"
        "- Locked OOS reads: 0\n"
        "- Release / Demo ARM / orders: 0 / false / 0\n\n"
        "## Blocking frozen-contract gaps\n\n"
        f"{blockers}\n\n"
        "No performance metric was computed or inferred. V17 is preserved and a new "
        "preregistered campaign is required before formal execution.\n"
    )


def _write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.tmp")
    temporary.write_text(content, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_pre_run_terminal_bundle(
    output_root: Path,
    preregistration: Mapping[str, Any],
    issues: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Write the terminal evidence bundle without creating formal results."""

    route = build_pre_run_terminal_route(preregistration, issues)
    output_root.mkdir(parents=True, exist_ok=True)
    payloads = {
        "formal_execution_contract_audit.json": {
            "schemaVersion": "s01_formal_execution_contract_audit_v1",
            "campaignId": route["campaignId"],
            "status": "failed",
            "prePerformanceRead": True,
            "marketDataReadCount": 0,
            "resultReadCount": 0,
            "lockedOosAccessCount": 0,
            "issues": [dict(issue) for issue in issues],
        },
        "route_decision.json": route,
        "gate_matrix.json": _gate_matrix(route, issues),
        "failure_attribution.json": _failure_attribution(route, issues),
        "campaign_summary.json": _summary(route, issues),
    }
    for name, payload in payloads.items():
        write_json_atomic(output_root / name, payload)
    _write_text_atomic(
        output_root / "campaign_summary.md",
        _summary_markdown(payloads["campaign_summary.json"]),
    )

    artifacts = []
    for path in sorted(output_root.iterdir(), key=lambda item: item.name):
        if path.is_file() and path.name != "artifact_manifest.json":
            artifacts.append(
                {
                    "path": path.name,
                    "sizeBytes": path.stat().st_size,
                    "sha256": _sha256(path),
                }
            )
    manifest = {
        "schemaVersion": "s01_formal_terminal_artifact_manifest_v1",
        "campaignId": route["campaignId"],
        "route": route["route"],
        "artifacts": artifacts,
        "formalPerformanceArtifactCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    write_json_atomic(output_root / "artifact_manifest.json", manifest)
    return route
