"""Immutable contracts for a provisional research-only Demo release."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta
from typing import Any, Iterable, Mapping

from alphapilot.evolution.registry.hashing import stable_hash


_PROHIBITED_MECHANIC_KEYS = (
    "martingale",
    "grid",
    "recoveryenabled",
    "recoverymode",
    "averaging",
    "addtoposition",
    "stopmaywiden",
    "widenstop",
)


def build_cooldown_semantics(
    *,
    pair_cooldown_days: int,
    implementation_path: str,
    implementation_sha256: str,
) -> dict[str, Any]:
    if pair_cooldown_days <= 0:
        raise ValueError("pair_cooldown_must_be_positive")
    core = {
        "schemaVersion": "portfolio_cooldown_semantics_v2",
        "cooldownScope": "canonical_instrument_id",
        "cooldownAnchor": "previous_accepted_closed_trade_exit_timestamp",
        "cooldownDurationSeconds": int(pair_cooldown_days) * 24 * 60 * 60,
        "timezone": "UTC",
        "boundaryRule": (
            "entry_timestamp_greater_than_or_equal_to_cooldown_end_is_allowed"
        ),
        "crossComponentScope": "all_three_portfolio_components",
        "pairCooldownDays": int(pair_cooldown_days),
        "durationSeconds": int(pair_cooldown_days) * 24 * 60 * 60,
        "anchorEvent": "previous_accepted_closed_trade_exit_timestamp",
        "clock": "utc_elapsed_time",
        "boundaryEqualityAllowed": True,
        "candidateOrder": ["entry_timestamp", "candidate_id", "instrument_id"],
        "completedTradeRule": "accepted_exit_timestamp_lte_candidate_entry_timestamp",
        "rejectionRule": "candidate_entry_lt_latest_same_pair_accepted_exit_plus_duration",
        "implementationPath": implementation_path,
        "implementationSha256": implementation_sha256,
        "notAWaitingPeriod": True,
    }
    return {
        **core,
        "cooldownSemanticsHash": stable_hash(
            core, prefix="portfolio_cooldown_semantics"
        ),
    }


def cooldown_is_blocked(
    semantics: Mapping[str, Any], previous_exit: datetime, candidate_entry: datetime
) -> bool:
    if previous_exit.tzinfo is None or candidate_entry.tzinfo is None:
        raise ValueError("cooldown_timestamps_must_be_timezone_aware")
    end = previous_exit + timedelta(seconds=int(semantics["durationSeconds"]))
    return candidate_entry < end


def _enabled(value: Any) -> bool:
    if value in (None, False, 0, 0.0, "", "false", "off", "none", "disabled"):
        return False
    return True


def _prohibited_mechanics(value: Any, path: str = "strategyDefinition") -> list[str]:
    found: list[str] = []
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = "".join(character for character in str(key).lower() if character.isalnum())
            current = f"{path}.{key}"
            if any(token in normalized for token in _PROHIBITED_MECHANIC_KEYS) and _enabled(item):
                found.append(current)
            found.extend(_prohibited_mechanics(item, current))
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            found.extend(_prohibited_mechanics(item, f"{path}[{index}]"))
    return found


def build_portfolio_definition(
    *,
    candidate_id: str,
    source_candidate_hash: str,
    source_campaign_hash: str,
    components: Iterable[Mapping[str, Any]],
    selected_policy: Mapping[str, Any],
    cooldown_semantics: Mapping[str, Any],
    allocation_semantics: str,
    cost_model: Mapping[str, Any],
) -> dict[str, Any]:
    frozen_components = [deepcopy(dict(row)) for row in components]
    ids = [str(row.get("candidateId") or "") for row in frozen_components]
    if len(frozen_components) != 3 or len(set(ids)) != 3 or any(not value for value in ids):
        raise ValueError("provisional_portfolio_requires_three_unique_components")
    required = {"strategyDefinitionHash", "direction", "timeframe", "family"}
    if any(not required <= set(row) for row in frozen_components):
        raise ValueError("component_identity_incomplete")
    prohibited = sorted(
        {
            path
            for row in frozen_components
            for path in _prohibited_mechanics(row.get("strategyDefinition"))
        }
    )
    if prohibited:
        raise PermissionError("prohibited_position_mechanic:" + ",".join(prohibited))

    core = {
        "schemaVersion": "portfolio_provisional_definition_v1",
        "candidateId": candidate_id,
        "sourceCandidateHash": source_candidate_hash,
        "sourceCampaignHash": source_campaign_hash,
        "components": frozen_components,
        "selectedPolicy": deepcopy(dict(selected_policy)),
        "cooldownSemantics": deepcopy(dict(cooldown_semantics)),
        "allocationSemantics": allocation_semantics,
        "componentWeightSemantics": "no_explicit_weights",
        "componentWeights": None,
        "conflictResolution": "chronological_entry_then_candidate_id_then_instrument_id",
        "exitPolicy": "component_native_frozen_forward_signal_policy",
        "costModel": deepcopy(dict(cost_model)),
        "historicalEvidenceClass": "development_selected_result",
        "mechanicsAudit": {
            "noMartingale": True,
            "noGrid": True,
            "noRecoveryPositionSizing": True,
            "noAveraging": True,
            "noAdding": True,
            "prohibitedPaths": [],
        },
    }
    return {
        **core,
        "portfolioDefinitionHash": stable_hash(
            core, prefix="portfolio_provisional_definition"
        ),
    }


def _positive(value: Any, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return fallback
    return number if number > 0 else fallback


def build_risk_overlay(existing: Mapping[str, Any]) -> dict[str, Any]:
    existing_per_trade = _positive(existing.get("riskPerTradePercent"), 0.10)
    existing_open = _positive(
        existing.get("maximumPortfolioOpenRiskPercent", existing.get("maxOpenRiskPercent")),
        0.30,
    )
    existing_positions = int(_positive(existing.get("maxConcurrentPositions"), 3))
    core = {
        "schemaVersion": "provisional_portfolio_risk_overlay_v1",
        "environment": "okx_demo_only",
        "riskPerTradePercent": min(existing_per_trade, 0.10),
        "maximumPortfolioOpenRiskPercent": min(existing_open, 0.30),
        "maximumConcurrentPositions": min(existing_positions, 3),
        "noAdding": True,
        "noAveraging": True,
        "noMartingale": True,
        "initialStopMayWiden": False,
        "marginMode": existing.get("marginMode", "isolated"),
        "maxLeverage": min(int(_positive(existing.get("maxLeverage"), 2)), 2),
        "feeRate": float(existing.get("feeRate", 0.0005)),
        "slippageRate": float(existing.get("slippageRate", 0.0002)),
        "sourceRiskProfileHash": existing.get("riskProfileHash"),
        "tighteningRule": "minimum_of_existing_limit_and_provisional_cap",
    }
    return {**core, "riskOverlayHash": stable_hash(core, prefix="risk_overlay")}


def _required_text(value: Any, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name}_missing")
    return text


def build_execution_identity(
    *,
    portfolio_definition: Mapping[str, Any],
    risk_overlay: Mapping[str, Any],
    universe_audit: Mapping[str, Any],
    quant_implementation_commit: str,
    console_execution_commit: str,
    quant_runtime_implementation_hash: str,
    console_runtime_implementation_hash: str,
) -> dict[str, Any]:
    components = list(portfolio_definition.get("components") or [])
    if len(components) != 3:
        raise ValueError("execution_identity_requires_three_components")
    component_identities = [
        {
            "candidateId": _required_text(row.get("candidateId"), "component_id"),
            "strategyDefinitionHash": _required_text(
                row.get("strategyDefinitionHash"), "strategy_definition_hash"
            ),
            "sourceContractHash": _required_text(
                row.get("sourceContractHash") or row.get("strategyDefinitionHash"),
                "source_contract_hash",
            ),
            "sourceReleaseHash": _required_text(
                row.get("sourceReleaseHash") or row.get("strategyDefinitionHash"),
                "source_release_hash",
            ),
        }
        for row in components
    ]
    exit_policies = [
        {
            "candidateId": row["candidateId"],
            "forwardSignalPolicy": deepcopy(
                dict((row.get("strategyDefinition") or {}).get("forwardSignalPolicy") or {})
            ),
        }
        for row in components
    ]
    risk_sources = [
        {
            "candidateId": row["candidateId"],
            "sourceRiskEnvelopeHash": str(row.get("sourceRiskEnvelopeHash") or ""),
        }
        for row in components
    ]
    core = {
        "schemaVersion": "provisional_demo_execution_identity_v1",
        "componentIdentities": component_identities,
        "portfolioDefinitionHash": _required_text(
            portfolio_definition.get("portfolioDefinitionHash"),
            "portfolio_definition_hash",
        ),
        "cooldownSemanticsHash": _required_text(
            (portfolio_definition.get("cooldownSemantics") or {}).get(
                "cooldownSemanticsHash"
            ),
            "cooldown_semantics_hash",
        ),
        "quantImplementationCommit": _required_text(
            quant_implementation_commit, "quant_implementation_commit"
        ),
        "consoleExecutionCommit": _required_text(
            console_execution_commit, "console_execution_commit"
        ),
        "quantRuntimeImplementationHash": _required_text(
            quant_runtime_implementation_hash, "quant_runtime_implementation_hash"
        ),
        "consoleRuntimeImplementationHash": _required_text(
            console_runtime_implementation_hash, "console_runtime_implementation_hash"
        ),
        "candidatePortfolioRuntimeHash": stable_hash(
            {
                "portfolioDefinitionHash": portfolio_definition[
                    "portfolioDefinitionHash"
                ],
                "components": component_identities,
            },
            prefix="candidate_portfolio_runtime",
        ),
        "exitPolicyHash": stable_hash(
            exit_policies, prefix="portfolio_exit_policy"
        ),
        "riskProfileHash": stable_hash(
            {
                "componentRiskSources": risk_sources,
                "riskOverlayHash": risk_overlay["riskOverlayHash"],
            },
            prefix="portfolio_risk_profile",
        ),
        "riskOverlayHash": _required_text(
            risk_overlay.get("riskOverlayHash"), "risk_overlay_hash"
        ),
        "researchUniverseHash": _required_text(
            universe_audit.get("researchUniverseHash"), "research_universe_hash"
        ),
        "publicUniverseSnapshotHash": _required_text(
            universe_audit.get("publicUniverseSnapshotHash"),
            "public_universe_snapshot_hash",
        ),
        "authenticatedDemoUniverseHash": _required_text(
            universe_audit.get("authenticatedDemoUniverseHash"),
            "authenticated_demo_universe_hash",
        ),
        "confirmedRuntimeUniverseHash": _required_text(
            universe_audit.get("confirmedRuntimeUniverseHash"),
            "confirmed_runtime_universe_hash",
        ),
        "executionIntersectionHash": _required_text(
            universe_audit.get("executionIntersectionHash"),
            "execution_intersection_hash",
        ),
        "costModelHash": stable_hash(
            portfolio_definition.get("costModel") or {}, prefix="cost_model"
        ),
        "evidenceClassification": {
            "historicalEvidenceClass": "development_selected_result",
            "strategyQualification": "provisional_research_only",
            "formalPass": False,
        },
    }
    return {
        **core,
        "executionIdentityHash": stable_hash(
            core, prefix="provisional_demo_execution_identity"
        ),
    }


def _normalized_instruments(values: Iterable[str]) -> list[str]:
    return sorted({str(value).upper().strip() for value in values if str(value).strip()})


def build_universe_audit(
    *,
    research_instruments: Iterable[str],
    public_snapshot_hash: str,
    public_count: int,
    authenticated_hash: str,
    authenticated_count: int,
    authenticated_exact_list_retained: bool,
    runtime_snapshot_hash: str,
    runtime_instruments: Iterable[str],
) -> dict[str, Any]:
    research = _normalized_instruments(research_instruments)
    runtime = _normalized_instruments(runtime_instruments)
    intersection = sorted(set(research) & set(runtime))
    core = {
        "schemaVersion": "demo_execution_universe_audit_v1",
        "researchUniverse": research,
        "researchUniverseHash": stable_hash(research, prefix="research_universe"),
        "researchEligibleCount": len(research),
        "publicUniverseSnapshotHash": public_snapshot_hash,
        "publicLiveCount": int(public_count),
        "publicExactInstrumentListRetained": False,
        "authenticatedDemoUniverse": None,
        "authenticatedDemoUniverseHash": authenticated_hash,
        "authenticatedDemoCount": int(authenticated_count),
        "authenticatedExactInstrumentListRetained": bool(
            authenticated_exact_list_retained
        ),
        "confirmedRuntimeUniverse": runtime,
        "confirmedRuntimeUniverseHash": runtime_snapshot_hash,
        "confirmedRuntimeCount": len(runtime),
        "executionIntersection": intersection,
        "executionIntersectionCount": len(intersection),
        "coverageRatio": len(intersection) / len(research) if research else 0.0,
        "intersectionComputation": (
            "research_universe_intersect_prevalidated_public_authenticated_runtime_universe"
        ),
        "forwardCollectionStatement": (
            "Demo execution universe is a frozen forward-collection universe; "
            "it does not retroactively change V46 historical evidence."
        ),
    }
    core["executionIntersectionHash"] = stable_hash(
        intersection, prefix="demo_execution_intersection"
    )
    core["status"] = "ready" if intersection else "blocked_demo_universe_empty"
    return core


def build_provisional_release(
    *,
    release_id: str,
    portfolio_definition: Mapping[str, Any],
    risk_overlay: Mapping[str, Any],
    universe_audit: Mapping[str, Any],
    historical_metrics: Mapping[str, Any],
    cost_stress_metrics: Mapping[str, Any],
    replay_parity_percent: float,
    execution_identity: Mapping[str, Any],
    generated_at: str,
) -> dict[str, Any]:
    if float(replay_parity_percent) != 100.0:
        raise ValueError("v46_replay_parity_incomplete")
    if float(historical_metrics.get("profitFactor") or 0) <= 1:
        raise ValueError("base_profit_factor_not_positive")
    if float(historical_metrics.get("expectancyR") or 0) <= 0:
        raise ValueError("average_net_r_not_positive")
    if float(cost_stress_metrics.get("profitFactor") or 0) <= 1:
        raise ValueError("cost_stress_profit_factor_not_positive")
    if universe_audit.get("status") != "ready":
        raise ValueError("blocked_demo_universe_empty")
    core = {
        "schemaVersion": "provisional_research_demo_v1",
        "releaseId": release_id,
        "releasePurpose": "provisional_research_demo",
        "evidenceClass": "historical_selected_forward_collection",
        "historicalEvidenceClass": "development_selected_result",
        "forwardEvidenceStatus": "collecting",
        "strategyQualification": "provisional_research_only",
        "formalPass": False,
        "cleanHistoricalOosPass": False,
        "livePromotionEligible": False,
        "automaticLivePromotionAllowed": False,
        "approvalRequired": True,
        "approved": False,
        "demoArm": False,
        "route": "blocked_waiting_exact_release_approval",
        "portfolioCandidateId": portfolio_definition["candidateId"],
        "portfolioDefinitionHash": portfolio_definition["portfolioDefinitionHash"],
        "componentIds": [
            row["candidateId"] for row in portfolio_definition["components"]
        ],
        "riskOverlayHash": risk_overlay["riskOverlayHash"],
        "executionIntersectionHash": universe_audit["executionIntersectionHash"],
        "executionInstruments": list(universe_audit["executionIntersection"]),
        "executionIdentity": deepcopy(dict(execution_identity)),
        "executionIdentityHash": execution_identity["executionIdentityHash"],
        "historicalMetrics": deepcopy(dict(historical_metrics)),
        "additionalCostStress0_10R": deepcopy(dict(cost_stress_metrics)),
        "replayParityPercent": float(replay_parity_percent),
        "generatedAt": generated_at,
    }
    release = {**core, "releaseHash": stable_hash(core, prefix="provisional_demo_release")}
    validate_provisional_release(release)
    return release


def validate_provisional_release(release: Mapping[str, Any]) -> None:
    if release.get("schemaVersion") != "provisional_research_demo_v1":
        raise ValueError("unsupported_provisional_release")
    forbidden_true = (
        "formalPass",
        "cleanHistoricalOosPass",
        "livePromotionEligible",
        "automaticLivePromotionAllowed",
        "approved",
        "demoArm",
    )
    if any(release.get(key) is not False for key in forbidden_true):
        raise PermissionError("provisional_release_claims_forbidden_qualification")
    if release.get("route") != "blocked_waiting_exact_release_approval":
        raise PermissionError("provisional_release_must_wait_for_exact_approval")
    identity = dict(release.get("executionIdentity") or {})
    identity_hash = str(identity.pop("executionIdentityHash", ""))
    if not identity_hash or release.get("executionIdentityHash") != identity_hash:
        raise ValueError("execution_identity_hash_missing")
    if stable_hash(identity, prefix="provisional_demo_execution_identity") != identity_hash:
        raise ValueError("execution_identity_hash_mismatch")


def build_release_binding_audit(
    *,
    release: Mapping[str, Any],
    portfolio_definition: Mapping[str, Any],
    risk_overlay: Mapping[str, Any],
    universe_audit: Mapping[str, Any],
) -> dict[str, Any]:
    identity = dict(release.get("executionIdentity") or {})
    component_rows = list(identity.get("componentIdentities") or [])
    required_checks = {
        "threeComponentIds": len(component_rows) == 3
        and all(str(row.get("candidateId") or "") for row in component_rows),
        "threeComponentDefinitionHashes": len(component_rows) == 3
        and all(str(row.get("strategyDefinitionHash") or "") for row in component_rows),
        "portfolioDefinitionHash": bool(identity.get("portfolioDefinitionHash")),
        "cooldownSemanticsHash": bool(identity.get("cooldownSemanticsHash")),
        "quantImplementationCommit": bool(identity.get("quantImplementationCommit")),
        "consoleExecutionCommit": bool(identity.get("consoleExecutionCommit")),
        "candidatePortfolioRuntimeHash": bool(identity.get("candidatePortfolioRuntimeHash")),
        "exitPolicyHash": bool(identity.get("exitPolicyHash")),
        "riskProfileHash": bool(identity.get("riskProfileHash")),
        "riskOverlayHash": bool(identity.get("riskOverlayHash")),
        "researchUniverseHash": bool(identity.get("researchUniverseHash")),
        "publicUniverseSnapshotHash": bool(identity.get("publicUniverseSnapshotHash")),
        "authenticatedDemoUniverseHash": bool(identity.get("authenticatedDemoUniverseHash")),
        "confirmedRuntimeUniverseHash": bool(identity.get("confirmedRuntimeUniverseHash")),
        "executionIntersectionHash": bool(identity.get("executionIntersectionHash")),
        "costModelHash": bool(identity.get("costModelHash")),
        "evidenceClassification": bool(identity.get("evidenceClassification")),
    }
    identity_body = dict(identity)
    identity_hash = str(identity_body.pop("executionIdentityHash", ""))
    chain_checks = {
        "executionIdentityHash": bool(identity_hash)
        and stable_hash(identity_body, prefix="provisional_demo_execution_identity")
        == identity_hash
        and release.get("executionIdentityHash") == identity_hash,
        "portfolioDefinitionHash": identity.get("portfolioDefinitionHash")
        == portfolio_definition.get("portfolioDefinitionHash")
        == release.get("portfolioDefinitionHash"),
        "cooldownSemanticsHash": identity.get("cooldownSemanticsHash")
        == (portfolio_definition.get("cooldownSemantics") or {}).get(
            "cooldownSemanticsHash"
        ),
        "riskOverlayHash": identity.get("riskOverlayHash")
        == risk_overlay.get("riskOverlayHash")
        == release.get("riskOverlayHash"),
        "researchUniverseHash": identity.get("researchUniverseHash")
        == universe_audit.get("researchUniverseHash"),
        "publicUniverseSnapshotHash": identity.get("publicUniverseSnapshotHash")
        == universe_audit.get("publicUniverseSnapshotHash"),
        "authenticatedDemoUniverseHash": identity.get(
            "authenticatedDemoUniverseHash"
        )
        == universe_audit.get("authenticatedDemoUniverseHash"),
        "confirmedRuntimeUniverseHash": identity.get("confirmedRuntimeUniverseHash")
        == universe_audit.get("confirmedRuntimeUniverseHash"),
        "executionIntersectionHash": identity.get("executionIntersectionHash")
        == universe_audit.get("executionIntersectionHash")
        == release.get("executionIntersectionHash"),
    }
    all_present = all(required_checks.values())
    chain_verified = all(chain_checks.values())
    return {
        "schemaVersion": "provisional_release_binding_audit_v1",
        "releaseId": release.get("releaseId"),
        "releaseHash": release.get("releaseHash"),
        "requiredBindings": required_checks,
        "hashChainChecks": chain_checks,
        "allRequiredBindingsPresent": all_present,
        "transitiveHashChainVerified": chain_verified,
        "status": "passed" if all_present and chain_verified else "blocked",
    }


def validate_exact_approval(
    release: Mapping[str, Any],
    risk_overlay: Mapping[str, Any],
    approval: Mapping[str, Any],
) -> dict[str, Any]:
    validate_provisional_release(release)
    if approval.get("releaseHash") != release.get("releaseHash"):
        raise PermissionError("exact_release_hash_approval_required")
    if approval.get("riskOverlayHash") != risk_overlay.get("riskOverlayHash"):
        raise PermissionError("exact_risk_overlay_hash_approval_required")
    return {
        "status": "approved_not_armed",
        "releaseHash": release["releaseHash"],
        "riskOverlayHash": risk_overlay["riskOverlayHash"],
        "demoArm": False,
    }


def build_cooldown_rejection(
    *,
    signal_id: str,
    component_id: str,
    instrument_id: str,
    signal_timestamp: str,
    cooldown_start: str,
    cooldown_end: str,
    remaining_seconds: int,
) -> dict[str, Any]:
    return {
        "schemaVersion": "cooldown_rejected_signal_v1",
        "signalId": signal_id,
        "componentId": component_id,
        "instrumentId": instrument_id,
        "signalTimestamp": signal_timestamp,
        "cooldownStart": cooldown_start,
        "cooldownEnd": cooldown_end,
        "remainingCooldownSeconds": max(0, int(remaining_seconds)),
        "rejectionReason": "same_pair_14d_cooldown",
        "diagnosticOnly": True,
    }
