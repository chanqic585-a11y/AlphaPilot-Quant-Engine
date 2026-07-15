"""Performance-blind preregistration for the first curated crypto factor seed."""

from __future__ import annotations

from alphapilot.evolution.registry.hashing import stable_hash

from .registry import build_alpha191_registry


SEED_FACTOR_IDS = (
    "alpha191_014",
    "alpha191_015",
    "alpha191_018",
    "alpha191_020",
    "alpha191_058",
    "alpha191_088",
    "alpha191_145",
    "alpha191_191",
)


def _mapped_windows(windows: tuple[int, ...]) -> dict[str, list[int]]:
    return {
        "1d": list(windows),
        "4h": [window * 6 for window in windows],
        "1h": [window * 24 for window in windows],
    }


def build_seed_preregistration() -> dict[str, object]:
    registry = {item.factor_id: item for item in build_alpha191_registry()}
    seed_factors: list[dict[str, object]] = []
    for factor_id in SEED_FACTOR_IDS:
        factor = registry[factor_id]
        if not factor.canonical_formula or factor.formula_status == "待人工确认":
            raise ValueError(f"Seed factor is not executable: {factor_id}")
        seed_factors.append(
            {
                "factorId": factor.factor_id,
                "categoryZh": factor.category_zh,
                "canonicalFormula": factor.canonical_formula,
                "implementationHash": factor.implementation_hash,
                "requiredColumns": list(factor.required_columns),
                "requiredOperators": list(factor.required_operators),
                "economicWindowDays": list(factor.windows),
                "periodsByTimeframe": _mapped_windows(factor.windows),
                "selectionBasis": [
                    "formula_unambiguous",
                    "required_fields_available",
                    "operators_tested",
                    "no_stock_only_dependency",
                    "crypto_mapping_explicit",
                ],
            }
        )
    core = {
        "schemaVersion": "alpha191_seed_preregistration_v1",
        "selectionUsedPerformance": False,
        "allowedTimeframes": ["1h", "4h", "1d"],
        "disallowedTimeframes": ["5m", "15m"],
        "manualDailyWindowPolicy": "Map by economic duration, never by equal candle count.",
        "seedFactors": seed_factors,
    }
    return {**core, "preregistrationHash": stable_hash(core, prefix="factor_seed")}
