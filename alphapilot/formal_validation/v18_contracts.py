"""Pre-result V18 campaign contract correcting only V17 capital policy gaps."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash

from .capital_policy_conformance import verify_capital_policy_v2
from .executable_capital_policy import build_capital_policy_v2
from .policy_objects import build_v18_policy_objects


V17_PREREGISTRATION_PATH = Path(
    "research/preregistrations/advisory_r_v17_s01_formal_walk_forward.json"
)
V18_FROZEN_AT = "2026-07-17T08:00:00Z"


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _campaign_id(parent: Mapping[str, Any], policy: Mapping[str, Any]) -> str:
    seed = {
        "parentCampaignId": parent["campaignId"],
        "parentPreregistrationHash": parent["preregistrationHash"],
        "sourceCandidateId": parent["sourceCandidateId"],
        "strategyDefinitionHash": parent["strategyDefinitionHash"],
        "exitPolicyHash": parent["exitPolicyHash"],
        "splitPolicyHash": parent["splitPolicyHash"],
        "costModelHash": parent["costModelHash"],
        "capitalCompetitionPolicyHash": policy["capitalCompetitionPolicyHash"],
    }
    digest = stable_hash(seed)
    return f"advisory_r_v18_s01_capital_policy_correction_{digest[:16]}"


def build_v18_preregistration(
    repo_root: Path,
    *,
    implementation_commit: str | None = None,
) -> dict[str, Any]:
    """Build a deterministic correction campaign without opening result data."""

    repo_root = Path(repo_root).resolve()
    parent = _read_json(repo_root / V17_PREREGISTRATION_PATH)
    final_self_check = _read_json(
        repo_root / "reports/v13_27_1_17_evidence_delivery/final_self_check.json"
    )
    io_guard = _read_json(
        repo_root / "reports/v13_27_1_17_evidence_delivery/freqtrade_io_guard_audit.json"
    )
    policy = build_capital_policy_v2()
    if not verify_capital_policy_v2(policy):
        raise ValueError("Capital Policy V2 failed executable conformance")
    policy_objects = build_v18_policy_objects()
    campaign_id = _campaign_id(parent, policy)

    payload = deepcopy(parent)
    payload.pop("preregistrationHash", None)
    payload.update(
        {
            "schemaVersion": "s01_v18_formal_walk_forward_preregistration_v1",
            "campaignId": campaign_id,
            "frozenAt": V18_FROZEN_AT,
            "parentCampaignId": parent["campaignId"],
            "parentPreregistrationHash": parent["preregistrationHash"],
            "correctionOfCampaignId": parent["campaignId"],
            "correctionReason": "capital_policy_execution_contract_incomplete",
            "correctionScope": "capital_policy_executable_definitions_only",
            "capitalCompetitionPolicy": policy,
            "capitalCompetitionPolicyHash": policy[
                "capitalCompetitionPolicyHash"
            ],
            "capitalPolicyChanges": 1,
            "strategyParameterChanges": 0,
            "BearDefinitionChanges": 0,
            "parameterChanges": 0,
            "exitPolicyChanges": 0,
            "splitPolicyChanges": 0,
            "universeChanges": 0,
            "costChanges": 0,
            "GateChanges": 0,
            "formalPortfolioPolicyDefinitionChanges": 1,
            "capacityModelHash": policy["capacityModel"]["definitionHash"],
            "correlationClusterPolicyHash": policy["correlationClusterPolicy"][
                "definitionHash"
            ],
            "portfolioBetaPolicyHash": policy["portfolioBetaPolicy"][
                "definitionHash"
            ],
            "signalRankingPolicyHash": policy["rankingPolicy"]["definitionHash"],
            "capitalAcceptanceSequenceHash": stable_hash(
                policy["acceptanceSequence"],
                prefix="s01_v18_capital_acceptance_sequence",
            ),
            "formalPortfolioPolicyV2Hash": policy[
                "capitalCompetitionPolicyHash"
            ],
            "implementationCommit": implementation_commit,
            "candidateAdapter": {
                "adapterId": "s01_freqtrade_formal_adapter",
                "adapterVersion": "1",
                "candidateId": parent["sourceCandidateId"],
                "contractSchemaVersion": "formal_candidate_adapter_contract_v1",
            },
            "formalPolicyObjects": {
                key: {
                    "policyId": value.policy_id,
                    "version": value.version,
                    "schemaVersion": value.schema_version,
                    "definitionHash": value.definition_hash,
                }
                for key, value in policy_objects.items()
            },
            "runtimeHash": final_self_check["runtimeHash"],
            "ioGuardHash": io_guard["contractHash"],
        }
    )
    risk_config = deepcopy(payload["riskConfig"])
    risk_config["capitalCompetitionPolicyHash"] = policy[
        "capitalCompetitionPolicyHash"
    ]
    payload["riskConfig"] = risk_config
    payload["riskConfigHash"] = stable_hash(
        risk_config, prefix="s01_v18_formal_risk_config"
    )

    statistical_policy = deepcopy(payload["statisticalPolicy"])
    statistical_policy["comparableCandidatePanel"] = {
        "status": "unavailable_predeclared",
        "reason": (
            "Only S01 is a frozen formal candidate; no point-in-time daily-return "
            "panel for all ten selection-family trials was frozen before results."
        ),
        "retroactiveConstructionAllowed": False,
        "panelHash": None,
        "unavailableStatistics": [
            "campaign_benjamini_hochberg",
            "deflated_sharpe_ratio",
            "probability_of_backtest_overfitting",
            "spa_or_white_reality_check",
        ],
        "availableS01Statistic": "newey_west_one_sided_when_daily_return_panel_exists",
        "decisionPolicy": "route_to_walk_forward_research_pass_statistics_unavailable",
    }
    statistical_policy["multipleTestingResultsMayBeReconstructedAfterRun"] = False
    payload["statisticalPolicy"] = statistical_policy

    payload["formalRunPolicy"] = {
        "researchOnly": True,
        "maximumRunClaims": 1,
        "scenarios": [
            "base",
            "cost_1_5x",
            "cost_2_0x",
            "conservative_funding_stress",
        ],
        "claimBoundary": "before_first_formal_input_content_read",
        "resumePolicy": (
            "same_run_id_only_with_identical_code_preregistration_and_input_hashes"
        ),
        "concurrentRunPolicy": "atomic_single_writer_claim",
        "postResultRerunAllowed": False,
        "resultArtifacts": "atomic_publish_after_run_completion",
    }
    payload["runLedgerPolicy"] = {
        "schemaVersion": "s01_v18_atomic_run_ledger_v1",
        "states": ["not_started", "running", "completed", "failed"],
        "attemptCountIncrementsAt": "first_formal_input_content_read",
        "resumeDoesNotCreateNewAttempt": True,
        "resumeRequiresDeterministicCheckpoint": True,
        "failedRunMayBeReclassifiedAsPass": False,
    }
    payload["remoteFreezePolicy"] = {
        "preregistrationMustExistOnUpstreamBeforeRun": True,
        "localOnlyCommitIsInsufficient": True,
        "tagRequiredBeforeRun": True,
        "blockedRoute": "blocked_remote_freeze",
    }
    locked_oos = deepcopy(payload["lockedOosPolicy"])
    locked_oos.update(
        {
            "contentRead": False,
            "accessCount": 0,
            "identityStatus": "pending_creation_after_remote_freeze",
            "identityCreationStage": "after_preregistration_remote_freeze_before_formal_run",
            "identityMetadataOnly": True,
            "identityMayContainPerformanceData": False,
        }
    )
    payload["lockedOosPolicy"] = locked_oos
    payload["stoppingRules"] = {
        "economicGateFailure": "archive_s01_current_version",
        "economicPassStatisticalFailure": "weak_or_selection_sensitive_edge",
        "statisticsUnavailable": "walk_forward_research_pass_statistics_unavailable",
        "walkForwardPassNoCleanHoldout": "walk_forward_research_pass_no_clean_holdout",
        "implementationInvalid": "implementation_invalid_requires_new_campaign",
        "remoteFreezeMissing": "blocked_remote_freeze",
        "sameFormalWindowRerunAllowed": False,
        "postResultParameterChangeAllowed": False,
        "allowedTerminalRoutes": [
            "archive_s01_current_version",
            "weak_or_selection_sensitive_edge",
            "walk_forward_research_pass_statistics_unavailable",
            "walk_forward_research_pass_no_clean_holdout",
            "implementation_invalid_requires_new_campaign",
            "blocked_remote_freeze",
        ],
    }
    payload["safetyBoundary"] = {
        "lockedOosAccessCount": 0,
        "formalEvidenceCount": 0,
        "formalRunClaimCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "withdrawIntegration": False,
        "liveTradingIntegration": False,
    }
    payload["preregistrationHash"] = stable_hash(
        payload, prefix="s01_v18_formal_walk_forward_preregistration"
    )
    return payload


def verify_v18_preregistration(payload: Mapping[str, Any]) -> bool:
    if not verify_capital_policy_v2(payload.get("capitalCompetitionPolicy", {})):
        return False
    core = {key: value for key, value in payload.items() if key != "preregistrationHash"}
    return payload.get("preregistrationHash") == stable_hash(
        core, prefix="s01_v18_formal_walk_forward_preregistration"
    )


def v18_preregistration_path(payload: Mapping[str, Any]) -> Path:
    campaign_id = str(payload["campaignId"])
    if not campaign_id.startswith("advisory_r_v18_s01_capital_policy_correction_"):
        raise ValueError("Unexpected V18 campaign id")
    return Path("research/preregistrations") / f"{campaign_id}.json"


def write_v18_preregistration(
    payload: Mapping[str, Any], repo_root: Path
) -> Path:
    if not verify_v18_preregistration(payload):
        raise ValueError("V18 preregistration hash or Capital Policy V2 is invalid")
    path = Path(repo_root).resolve() / v18_preregistration_path(payload)
    write_json_atomic(path, dict(payload))
    return path
