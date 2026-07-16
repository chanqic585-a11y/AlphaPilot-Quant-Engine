"""Trial accounting for every preregistered Advisory-R policy variant."""

from __future__ import annotations

from collections import Counter
from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


def build_trial_ledger(candidates: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    family_counts = Counter(str(row["familyId"]) for row in candidates)
    trials = []
    for row in sorted(candidates, key=lambda item: str(item["candidateId"])):
        parent = (
            stable_hash({"familyId": row["familyId"]}, prefix="advisory_r_family_trial")
            if family_counts[str(row["familyId"])] > 1
            else None
        )
        identity = {
            "candidateId": row["candidateId"],
            "strategyDefinitionHash": row["strategyDefinitionHash"],
            "exitPolicyHash": row["exitPolicyHash"],
        }
        trials.append(
            {
                "trialId": stable_hash(identity, prefix="advisory_r_trial"),
                "candidateId": row["candidateId"],
                "familyId": row["familyId"],
                "variantId": row["variantId"],
                "strategyDefinitionHash": row["strategyDefinitionHash"],
                "exitPolicyVersion": row["exitPolicy"]["version"],
                "exitPolicyMode": row["exitPolicy"]["mode"],
                "exitPolicyHash": row["exitPolicyHash"],
                "exitPolicyParentTrialId": parent,
                "resultsRead": False,
            }
        )
    core = {
        "schemaVersion": "advisory_r_trial_ledger_v1",
        "trialCount": len(trials),
        "trials": trials,
    }
    return {**core, "trialLedgerHash": stable_hash(core, prefix="advisory_r_trial_ledger")}

