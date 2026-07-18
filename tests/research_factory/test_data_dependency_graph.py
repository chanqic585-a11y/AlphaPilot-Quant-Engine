from __future__ import annotations

from alphapilot.research_factory.data_dependency_graph import (
    build_capital_policy_data_dependencies,
    build_data_dependency_graph,
    evaluate_contract_readiness,
)
from alphapilot.research_factory.end_to_end_data_contract import (
    build_end_to_end_data_contract,
)


def _contract() -> dict:
    return build_end_to_end_data_contract(
        candidate_spec={
            "candidateId": "auto-trend_failure-reversal-4h-short-v2",
            "requiredFields": ["open", "high", "low", "close"],
        },
        capital_required_fields=["quote_turnover"],
        demo_execution_required_fields=["instrument_id", "tick_size"],
    )


def _evidence(*, include_turnover: bool, include_demo: bool) -> dict:
    fields = {
        name: {"semanticallyVerified": True, "coveragePct": 100.0}
        for name in ("open", "high", "low", "close")
    }
    if include_turnover:
        fields["quote_turnover"] = {
            "semanticallyVerified": True,
            "coveragePct": 99.0,
        }
    if include_demo:
        fields["instrument_id"] = {
            "semanticallyVerified": True,
            "coveragePct": 100.0,
        }
        fields["tick_size"] = {
            "semanticallyVerified": True,
            "coveragePct": 100.0,
        }
    return fields


def test_signal_formal_and_demo_readiness_are_distinct() -> None:
    contract = _contract()
    signal_only = evaluate_contract_readiness(
        contract,
        field_evidence=_evidence(include_turnover=False, include_demo=False),
        formal_profile_status="blocked",
        demo_profile_status="blocked",
    )
    formal = evaluate_contract_readiness(
        contract,
        field_evidence=_evidence(include_turnover=True, include_demo=False),
        formal_profile_status="ready",
        demo_profile_status="blocked",
    )
    demo = evaluate_contract_readiness(
        contract,
        field_evidence=_evidence(include_turnover=True, include_demo=True),
        formal_profile_status="ready",
        demo_profile_status="ready",
    )

    assert signal_only["signalReady"] is True
    assert signal_only["formalReady"] is False
    assert formal["formalReady"] is True
    assert formal["demoReady"] is False
    assert demo["demoReady"] is True


def test_dependency_graph_links_layers_to_fields() -> None:
    graph = build_data_dependency_graph(_contract())

    assert {edge["field"] for edge in graph["edges"] if edge["layer"] == "capital"} == {
        "quote_turnover"
    }
    assert graph["graphHash"].startswith("data_dependency_graph_")


def test_capital_policy_dependencies_are_machine_readable() -> None:
    dependencies = build_capital_policy_data_dependencies(
        {
            "capitalHash": "numeric-capital-hash",
            "definitionHash": "capacity-model-hash",
            "lookbackCompletedUtcDays": 30,
            "minimumCompletedUtcDays": 24,
            "missingDataPolicy": "reject_without_verified_quote_turnover_semantics",
        }
    )

    assert dependencies["policyHash"] == "numeric-capital-hash"
    assert dependencies["capacityModelHash"] == "capacity-model-hash"
    assert "quote_turnover" in dependencies["requiredFields"]
    assert dependencies["minimumLookback"] == 30
    assert dependencies["minimumValidObservations"] == 24
    assert dependencies["dependencyHash"].startswith("capital_policy_data_dependencies_")
