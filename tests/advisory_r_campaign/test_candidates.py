from collections import Counter

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.advisory_r_campaign.trial_ledger import build_trial_ledger


REQUIRED_FIELDS = {
    "candidateId",
    "familyId",
    "variantId",
    "humanHypothesisZh",
    "falsificationCriteriaZh",
    "featureDefinition",
    "entryDefinition",
    "initialStopDefinition",
    "exitPolicy",
    "exitPolicyRationaleZh",
    "maximumHold",
    "simpleBenchmark",
    "complexityScore",
    "semanticFingerprint",
    "strategyDefinitionHash",
    "exitPolicyHash",
    "originLineage",
    "diagnosticOnly",
}

RESULT_FIELDS = {
    "profitFactor",
    "averageNetR",
    "totalNetR",
    "maximumDrawdown",
    "passed",
    "survived",
}


def test_inventory_is_bounded_deterministic_and_mechanism_complete() -> None:
    first = build_candidate_inventory()
    second = build_candidate_inventory()

    assert first == second
    assert len(first) == 10
    assert {row["variantId"] for row in first} == {f"S{value:02d}" for value in range(1, 11)}
    families = Counter(row["familyId"] for row in first)
    assert 6 <= len(families) <= 8
    assert max(families.values()) <= 2
    assert all(REQUIRED_FIELDS <= set(row) for row in first)
    assert all(not RESULT_FIELDS.intersection(row) for row in first)
    assert all(row["humanHypothesisZh"].strip() for row in first)
    assert all(row["falsificationCriteriaZh"].strip() for row in first)
    assert all(row["initialStopDefinition"]["mayWiden"] is False for row in first)
    assert len({row["semanticFingerprint"] for row in first}) == len(first)
    assert len({row["strategyDefinitionHash"] for row in first}) == len(first)
    assert len({row["exitPolicyHash"] for row in first}) == len(first)


def test_inventory_freezes_one_primary_exit_policy_per_candidate() -> None:
    by_variant = {row["variantId"]: row for row in build_candidate_inventory()}

    assert by_variant["S01"]["exitPolicy"]["mode"] == "hybrid"
    assert by_variant["S02"]["exitPolicy"]["mode"] == "partial_then_trailing"
    assert by_variant["S03"]["exitPolicy"]["mode"] == "structure_or_time"
    assert by_variant["S04"]["exitPolicy"]["mode"] == "structure_or_time"
    assert by_variant["S05"]["exitPolicy"]["mode"] == "hybrid"
    assert by_variant["S06"]["exitPolicy"]["mode"] == "partial_then_trailing"
    assert by_variant["S07"]["exitPolicy"]["mode"] in {"partial_then_trailing", "hybrid"}
    assert by_variant["S08"]["exitPolicy"]["mode"] == "fixed_r"
    assert by_variant["S08"]["exitPolicy"]["parameters"]["targetR"] < 2
    assert by_variant["S09"]["exitPolicy"]["mode"] == "structure_or_time"
    assert by_variant["S10"]["diagnosticOnly"] is True
    assert all("exitPolicyVariants" not in row for row in by_variant.values())


def test_trial_ledger_counts_every_frozen_exit_policy_as_one_trial() -> None:
    candidates = build_candidate_inventory()
    ledger = build_trial_ledger(candidates)

    assert ledger["schemaVersion"] == "advisory_r_trial_ledger_v1"
    assert ledger["trialCount"] == len(candidates)
    assert len(ledger["trials"]) == len(candidates)
    assert len({row["trialId"] for row in ledger["trials"]}) == len(candidates)
    assert {row["exitPolicyHash"] for row in ledger["trials"]} == {
        row["exitPolicyHash"] for row in candidates
    }
    assert all(row["resultsRead"] is False for row in ledger["trials"])

