from __future__ import annotations

import pytest

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.advisory_r_campaign.conformance import (
    ImplementationConformanceError,
    build_candidate_conformance,
    build_conformance_record,
)


def test_all_frozen_candidates_have_explicit_consumption_contracts() -> None:
    records = [build_candidate_conformance(row) for row in build_candidate_inventory()]

    assert len(records) == 10
    assert all(row["implementationConformancePassed"] for row in records)
    assert all(row["unusedFrozenKeys"] == [] for row in records)
    assert all(row["unsupportedFrozenKeys"] == [] for row in records)
    assert len({row["implementationConformanceHash"] for row in records}) == 10


def test_unused_frozen_field_fails_candidate_conformance() -> None:
    candidate = build_candidate_inventory()[0]

    record = build_conformance_record(candidate, consumed_keys=set())

    assert record["implementationConformancePassed"] is False
    assert "featureDefinition.marketRegime" in record["unusedFrozenKeys"]


def test_hardcoded_value_mismatch_fails_closed() -> None:
    candidate = build_candidate_inventory()[1]

    with pytest.raises(ImplementationConformanceError, match="hard-coded value mismatch"):
        build_conformance_record(
            candidate,
            consumed_keys={"featureDefinition.betaWindow"},
            hardcoded_values={"featureDefinition.betaWindow": 120},
        )


def test_unsupported_fallback_fails_the_campaign() -> None:
    candidate = build_candidate_inventory()[2]

    with pytest.raises(ImplementationConformanceError, match="unsupported frozen rule"):
        build_conformance_record(
            candidate,
            consumed_keys=set(),
            unsupported_keys={"exitPolicy.parameters.structureRule.kind"},
        )

