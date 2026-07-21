from __future__ import annotations

from alphapilot.adaptive_learning.production_factor_registry import (
    build_production_factor_registry,
)


def test_production_registry_has_complete_point_in_time_metadata() -> None:
    payload = build_production_factor_registry()
    required = {
        "factorId",
        "name",
        "theme",
        "canonicalFormula",
        "requiredFields",
        "availableAtRule",
        "pointInTimeReady",
        "normalizationPolicy",
        "missingValuePolicy",
        "sourceArtifactId",
        "definitionHash",
        "implementationHash",
    }
    assert payload["schemaVersion"] == "production_factor_registry_v1"
    assert payload["factorRegistryHash"].startswith("production_factor_registry_")
    assert payload["factors"]
    assert all(required <= set(row) for row in payload["factors"])
    assert all(row["pointInTimeReady"] is True for row in payload["factors"])
    assert {row["sourceClass"] for row in payload["factors"]} == {
        "derivatives",
        "alpha101_style",
        "alpha191_compatibility",
        "crypto_native",
    }


def test_alpha191_compatibility_is_bounded_and_does_not_claim_all_191_validated() -> None:
    payload = build_production_factor_registry()
    audit = payload["alpha191Compatibility"]
    assert audit["catalogCount"] == 191
    assert 0 < audit["formulaReviewedCount"] < 191
    assert 0 < audit["numericCrossvalidatedCount"] < 191
    assert audit["productionValidatedCount"] == 0
    assert audit["allFactorsProductionValidated"] is False


def test_registry_covers_the_existing_demo_scanner_factor_contract() -> None:
    payload = build_production_factor_registry()
    factor_ids = {row["factorId"] for row in payload["factors"]}
    assert {
        "return_1",
        "return_6",
        "volatility_12",
        "volume_ratio_20",
        "ema_distance_20",
        "ema_distance_50",
        "rsi_14",
        "macd_histogram",
        "atr_pct_14",
        "bollinger_position",
    } <= factor_ids
    assert len(factor_ids) <= payload["boundedMaximum"]
