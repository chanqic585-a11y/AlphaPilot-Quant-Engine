from __future__ import annotations

import json
from pathlib import Path

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.formal_validation.capital_policy_conformance import (
    verify_capital_policy_v2,
)
from alphapilot.formal_validation.v18_contracts import (
    build_v18_preregistration,
    verify_v18_preregistration,
    v18_preregistration_path,
    write_v18_preregistration,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
V17_PATH = (
    REPO_ROOT
    / "research"
    / "preregistrations"
    / "advisory_r_v17_s01_formal_walk_forward.json"
)


def test_v18_changes_only_the_capital_policy_contract() -> None:
    before = V17_PATH.read_bytes()
    v17 = json.loads(before.decode("utf-8"))

    payload = build_v18_preregistration(REPO_ROOT)

    assert V17_PATH.read_bytes() == before
    assert payload["campaignId"].startswith(
        "advisory_r_v18_s01_capital_policy_correction_"
    )
    assert payload["parentCampaignId"] == v17["campaignId"]
    assert payload["parentPreregistrationHash"] == v17["preregistrationHash"]
    assert payload["correctionOfCampaignId"] == "advisory_r_v17"
    assert payload["correctionReason"] == (
        "capital_policy_execution_contract_incomplete"
    )
    assert payload["strategyDefinitionHash"] == v17["strategyDefinitionHash"]
    assert payload["exitPolicyHash"] == v17["exitPolicyHash"]
    assert payload["splitPolicyHash"] == v17["splitPolicyHash"]
    assert payload["costModelHash"] == v17["costModelHash"]
    assert payload["parameterChanges"] == 0
    assert payload["exitPolicyChanges"] == 0
    assert payload["universeChanges"] == 0
    assert payload["costChanges"] == 0
    assert payload["capitalPolicyChanges"] == 1
    assert payload["strategyParameterChanges"] == 0
    assert payload["BearDefinitionChanges"] == 0
    assert payload["splitPolicyChanges"] == 0
    assert payload["GateChanges"] == 0
    assert payload["formalPortfolioPolicyDefinitionChanges"] == 1
    assert payload["capacityModelHash"] == payload["capitalCompetitionPolicy"][
        "capacityModel"
    ]["definitionHash"]
    assert payload["correlationClusterPolicyHash"] == payload[
        "capitalCompetitionPolicy"
    ]["correlationClusterPolicy"]["definitionHash"]
    assert payload["portfolioBetaPolicyHash"] == payload[
        "capitalCompetitionPolicy"
    ]["portfolioBetaPolicy"]["definitionHash"]
    assert payload["signalRankingPolicyHash"] == payload[
        "capitalCompetitionPolicy"
    ]["rankingPolicy"]["definitionHash"]
    assert payload["capitalAcceptanceSequenceHash"]
    assert payload["formalPortfolioPolicyV2Hash"] == payload[
        "capitalCompetitionPolicyHash"
    ]
    assert payload["runtimeHash"]
    assert payload["ioGuardHash"]
    assert verify_capital_policy_v2(payload["capitalCompetitionPolicy"]) is True
    assert payload["lockedOosPolicy"]["contentRead"] is False
    assert payload["lockedOosPolicy"]["accessCount"] == 0
    assert payload["formalRunPolicy"]["maximumRunClaims"] == 1
    assert payload["formalRunPolicy"]["scenarios"] == [
        "base",
        "cost_1_5x",
        "cost_2_0x",
        "conservative_funding_stress",
    ]
    assert payload["statisticalPolicy"]["comparableCandidatePanel"]["status"] == (
        "unavailable_predeclared"
    )
    assert verify_v18_preregistration(payload) is True


def test_v18_campaign_and_hash_are_deterministic() -> None:
    first = build_v18_preregistration(REPO_ROOT)
    second = build_v18_preregistration(REPO_ROOT)

    assert first == second
    core = {key: value for key, value in first.items() if key != "preregistrationHash"}
    assert first["preregistrationHash"] == stable_hash(
        core, prefix="s01_v18_formal_walk_forward_preregistration"
    )


def test_v18_preregistration_freezes_adapter_policy_objects_and_code_commit() -> None:
    implementation_commit = "a" * 40

    payload = build_v18_preregistration(
        REPO_ROOT,
        implementation_commit=implementation_commit,
    )

    assert payload["implementationCommit"] == implementation_commit
    assert payload["candidateAdapter"] == {
        "adapterId": "s01_freqtrade_formal_adapter",
        "adapterVersion": "1",
        "candidateId": "s01_bear_idiosyncratic_selloff_recovery_4h",
        "contractSchemaVersion": "formal_candidate_adapter_contract_v1",
    }
    expected = {
        "capacity": ("capacity", "capacityModel", "capacityModelHash"),
        "cluster": (
            "cluster",
            "correlationClusterPolicy",
            "correlationClusterPolicyHash",
        ),
        "beta": ("beta", "portfolioBetaPolicy", "portfolioBetaPolicyHash"),
        "ranking": ("ranking", "rankingPolicy", "signalRankingPolicyHash"),
    }
    for key, (policy_id, definition_key, hash_key) in expected.items():
        metadata = payload["formalPolicyObjects"][key]
        assert metadata == {
            "policyId": policy_id,
            "version": "1",
            "schemaVersion": payload["capitalCompetitionPolicy"][definition_key][
                "schemaVersion"
            ],
            "definitionHash": payload[hash_key],
        }
    assert verify_v18_preregistration(payload) is True


def test_v18_writer_uses_campaign_specific_path(tmp_path: Path) -> None:
    payload = build_v18_preregistration(REPO_ROOT)

    path = write_v18_preregistration(payload, tmp_path)

    assert path == tmp_path / v18_preregistration_path(payload)
    assert json.loads(path.read_text(encoding="utf-8")) == payload
