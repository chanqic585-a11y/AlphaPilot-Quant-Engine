from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from alphapilot.factor_lab import operators
from alphapilot.factor_lab.registry import FactorDefinition, FactorRegistry
from alphapilot.factor_lab.reports import write_factor_lab_reports
from alphapilot.factor_lab.similarity import (
    ArtifactSimilarityPolicy,
    SimilarityEvidence,
    classify_similarity,
)


def test_delta_requires_strictly_positive_lag() -> None:
    values = pd.Series([1.0, 2.0, 3.0])

    with pytest.raises(ValueError, match="positive"):
        operators.delta(values, 0)


def test_vwap_propagates_nan_and_never_returns_inf() -> None:
    price = pd.Series([10.0, 11.0, np.nan, 13.0])
    volume = pd.Series([2.0, 1.0, 5.0, 0.0])

    result = operators.vwap(price, volume, window=2, min_periods=2)

    assert result.iloc[1] == pytest.approx((10.0 * 2.0 + 11.0) / 3.0)
    assert np.isnan(result.iloc[2])
    assert not np.isinf(result.to_numpy()).any()
    assert "vwap" in operators.OPERATOR_REGISTRY


def test_registry_is_bounded_and_requires_pit_ready_fields() -> None:
    registry = FactorRegistry(max_factors=2)
    registry.register(
        FactorDefinition(
            factorId="momentum-1",
            name="TS momentum",
            theme="ts_momentum",
            formula="delta(close, 20)",
            requiredFields=("close",),
            pointInTimeReady=True,
        )
    )
    registry.register(
        FactorDefinition(
            factorId="funding-1",
            name="Funding carry",
            theme="funding",
            formula="ts_mean(funding_rate, 3, 3)",
            requiredFields=("funding_rate", "funding_available_at"),
            pointInTimeReady=True,
        )
    )

    with pytest.raises(ValueError, match="bounded"):
        registry.register(
            FactorDefinition(
                factorId="third",
                name="Third",
                theme="basis",
                formula="close - index_price",
                requiredFields=("close", "index_price"),
                pointInTimeReady=True,
            )
        )


def test_similarity_policy_is_frozen_and_uses_multiple_strategy_dimensions() -> None:
    policy = ArtifactSimilarityPolicy.frozen_default("2026-07-20T00:00:00Z")
    evidence = SimilarityEvidence(
        sourceLineageMatch=False,
        canonicalFormulaMatch=False,
        semanticMechanismMatch=True,
        signalCorrelation=0.93,
        eventOverlap=0.82,
        dailyReturnCorrelation=0.91,
        holdingOverlap=0.80,
        parameterLineageMatch=True,
    )

    decision = classify_similarity(evidence, policy)

    assert policy.policyHash
    assert decision.classification == "same_family_variant"
    assert len(decision.supportingDimensions) >= 3


@pytest.mark.parametrize(
    "evidence,expected",
    [
        (
            SimilarityEvidence(True, True, True, 1.0, 1.0, 1.0, 1.0, True),
            "exact_duplicate",
        ),
        (
            SimilarityEvidence(False, False, True, 0.995, 0.97, 0.995, 0.96, False),
            "near_duplicate",
        ),
        (
            SimilarityEvidence(False, False, True, 0.93, 0.82, 0.91, 0.80, True),
            "same_family_variant",
        ),
        (
            SimilarityEvidence(False, False, True, 0.50, 0.40, 0.30, 0.20, False),
            "mechanism_related",
        ),
        (
            SimilarityEvidence(False, False, False, 0.20, 0.10, 0.10, 0.05, False),
            "independent",
        ),
    ],
)
def test_similarity_policy_emits_all_frozen_classes(
    evidence: SimilarityEvidence, expected: str
) -> None:
    policy = ArtifactSimilarityPolicy.frozen_default("2026-07-20T00:00:00Z")

    assert classify_similarity(evidence, policy).classification == expected


def test_reports_write_parquet_csv_and_json(tmp_path: Path) -> None:
    registry = FactorRegistry(max_factors=36)
    registry.register(
        FactorDefinition(
            factorId="range-1",
            name="Normalized range",
            theme="range_atr",
            formula="safe_div(high - low, close)",
            requiredFields=("high", "low", "close"),
            pointInTimeReady=True,
        )
    )

    outputs = write_factor_lab_reports(
        tmp_path,
        registry=registry,
        bench_rows=[{"factorId": "range-1", "ic": 0.02, "rankIc": 0.03}],
        similarity_rows=[
            {
                "leftArtifactId": "range-1",
                "rightArtifactId": "range-1",
                "classification": "exact_duplicate",
            }
        ],
        dedup_decisions=[{"candidateId": "range-1", "decision": "keep"}],
    )

    assert outputs["factorRegistry"].is_file()
    assert outputs["factorBenchMatrix"].is_file()
    assert outputs["artifactSimilarityMatrix"].is_file()
    assert outputs["candidateDedupDecision"].is_file()
