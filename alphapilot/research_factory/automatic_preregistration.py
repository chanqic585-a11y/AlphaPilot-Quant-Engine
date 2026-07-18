"""Identity-complete preregistration builders for V21 survivors."""

from __future__ import annotations

from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash


REQUIRED_BINDING_HASHES = (
    "dataProfileHash",
    "dataSnapshotHash",
    "universeHash",
    "splitHash",
    "costHash",
    "capitalPolicyHash",
    "benchmarkHash",
    "statisticalPolicyHash",
    "gateHash",
    "runtimeHash",
    "ioGuardHash",
    "candidatePanelHash",
)


def build_candidate_preregistration(
    *,
    parent_campaign_id: str,
    candidate: Mapping[str, Any],
    implementation_commit: str,
    generated_at: str,
    bindings: Mapping[str, str],
) -> dict[str, Any]:
    missing = [key for key in REQUIRED_BINDING_HASHES if not bindings.get(key)]
    if missing:
        raise ValueError("preregistration_bindings_missing:" + ",".join(missing))
    candidate_id = str(candidate["candidateId"])
    core = {
        "schemaVersion": "automatic_formal_preregistration_v1",
        "campaignId": f"{parent_campaign_id}__{candidate_id}",
        "parentCampaignId": parent_campaign_id,
        "sourceCandidateId": candidate_id,
        "candidateHash": str(candidate["candidateSpecHash"]),
        "strategyDefinitionHash": str(candidate["strategyDefinitionHash"]),
        "exitPolicyHash": str(candidate["exitPolicyHash"]),
        "candidateSpec": dict(candidate),
        "implementationCommit": implementation_commit,
        "generatedAt": generated_at,
        **{key: str(bindings[key]) for key in REQUIRED_BINDING_HASHES},
        "formalRunBudget": 1,
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "resultDrivenMutationAllowed": False,
        "targetRGateMode": "advisory",
        "universalTwoRHardGate": False,
    }
    return {
        **core,
        "preregistrationHash": stable_hash(
            core, prefix="automatic_formal_preregistration"
        ),
    }


def verify_candidate_preregistration(payload: Mapping[str, Any]) -> bool:
    core = {key: value for key, value in payload.items() if key != "preregistrationHash"}
    return payload.get("preregistrationHash") == stable_hash(
        core, prefix="automatic_formal_preregistration"
    )


__all__ = [
    "REQUIRED_BINDING_HASHES",
    "build_candidate_preregistration",
    "verify_candidate_preregistration",
]
