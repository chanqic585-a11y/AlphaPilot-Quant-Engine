"""Build the bounded, point-in-time production feature registry.

Registry inclusion means a factor is safe to calculate at the declared
availability time. It does not claim predictive value; that requires a real
factor bench and locked validation evidence.
"""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.factor_lab.alpha191.manual_reference import REVIEWED_FORMULAS
from alphapilot.factor_lab.alpha191.registry import build_alpha191_registry
from alphapilot.factor_lab.registry import FactorDefinition, FactorRegistry


def _definition(
    *,
    factor_id: str,
    name: str,
    theme: str,
    formula: str,
    required_fields: tuple[str, ...],
    available_at_rule: str,
    normalization_policy: str,
    missing_value_policy: str,
    source_artifact_id: str,
) -> FactorDefinition:
    return FactorDefinition(
        factorId=factor_id,
        name=name,
        theme=theme,
        formula=formula,
        requiredFields=required_fields,
        pointInTimeReady=True,
        sourceArtifactId=source_artifact_id,
        availableAtRule=available_at_rule,
        normalizationPolicy=normalization_policy,
        missingValuePolicy=missing_value_policy,
        implementationHash=stable_hash(
            {
                "factorId": factor_id,
                "formula": formula,
                "availableAtRule": available_at_rule,
                "sourceArtifactId": source_artifact_id,
            },
            prefix="factor_implementation",
        ),
    )


def _base_definitions() -> tuple[tuple[FactorDefinition, str], ...]:
    definitions: list[tuple[FactorDefinition, str]] = [
        (
            _definition(
                factor_id="funding_rate_zscore_24",
                name="Funding rate z-score 24",
                theme="funding",
                formula="zscore(funding_rate,24)",
                required_fields=("funding_rate", "funding_available_at"),
                available_at_rule="funding_publication_time",
                normalization_policy="rolling_zscore_24",
                missing_value_policy="reject_signal",
                source_artifact_id="okx_public_funding_history",
            ),
            "derivatives",
        ),
        (
            _definition(
                factor_id="perp_basis_zscore_48",
                name="Perpetual basis z-score 48",
                theme="basis",
                formula="zscore(safe_div(mark_price-index_price,index_price),48)",
                required_fields=("mark_price", "index_price", "market_available_at"),
                available_at_rule="latest_confirmed_market_snapshot",
                normalization_policy="rolling_zscore_48",
                missing_value_policy="reject_signal",
                source_artifact_id="okx_public_mark_index_history",
            ),
            "derivatives",
        ),
        (
            _definition(
                factor_id="cross_sectional_return_rank_20",
                name="Cross-sectional return rank 20",
                theme="relative_momentum",
                formula="cs_rank(safe_div(close-delay(close,20),delay(close,20)))",
                required_fields=("close",),
                available_at_rule="confirmed_bar_close_cross_section",
                normalization_policy="cross_sectional_rank_0_1",
                missing_value_policy="exclude_symbol",
                source_artifact_id="alpha101_style_internal_context",
            ),
            "alpha101_style",
        ),
        (
            _definition(
                factor_id="volume_price_corr_20",
                name="Volume-price rolling correlation 20",
                theme="volume_price",
                formula="ts_corr(cs_rank(volume),cs_rank(close),20,20)",
                required_fields=("volume", "close"),
                available_at_rule="confirmed_bar_close_cross_section",
                normalization_policy="clip_minus1_plus1",
                missing_value_policy="exclude_symbol",
                source_artifact_id="alpha101_style_internal_context",
            ),
            "alpha101_style",
        ),
        (
            _definition(
                factor_id="btc_relative_strength_20",
                name="BTC-relative strength 20",
                theme="crypto_relative_strength",
                formula="return(close,20)-return(btc_close,20)",
                required_fields=("close", "btc_close"),
                available_at_rule="confirmed_bar_close_with_btc_context",
                normalization_policy="rolling_robust_zscore_60",
                missing_value_policy="reject_signal",
                source_artifact_id="alphapilot_crypto_native_context",
            ),
            "crypto_native",
        ),
        (
            _definition(
                factor_id="liquidity_spread_shock",
                name="Liquidity spread shock",
                theme="liquidity",
                formula="safe_div(spread_bps-ts_median(spread_bps,96),ts_mad(spread_bps,96))",
                required_fields=("best_bid", "best_ask", "book_available_at"),
                available_at_rule="order_book_snapshot_received_at",
                normalization_policy="rolling_robust_zscore_96",
                missing_value_policy="reject_signal",
                source_artifact_id="alphapilot_crypto_native_order_book",
            ),
            "crypto_native",
        ),
    ]
    scanner_factors = (
        ("return_1", "One-bar return", "momentum", "safe_div(close-delay(close,1),delay(close,1))", ("close",)),
        ("return_6", "Six-bar return", "momentum", "safe_div(close-delay(close,6),delay(close,6))", ("close",)),
        ("volatility_12", "Return volatility 12", "volatility", "ts_std(return_1,12)", ("close",)),
        ("volume_ratio_20", "Volume ratio 20", "liquidity", "safe_div(volume,ts_mean(volume,20))", ("volume",)),
        ("ema_distance_20", "EMA20 distance", "trend", "safe_div(close,ema(close,20))-1", ("close",)),
        ("ema_distance_50", "EMA50 distance", "trend", "safe_div(close,ema(close,50))-1", ("close",)),
        ("rsi_14", "RSI 14", "momentum", "rsi(close,14)", ("close",)),
        ("macd_histogram", "MACD histogram", "momentum", "ema(close,12)-ema(close,26)-ema(ema(close,12)-ema(close,26),9)", ("close",)),
        ("atr_pct_14", "ATR percent 14", "volatility", "safe_div(atr(high,low,close,14),close)", ("high", "low", "close")),
        ("bollinger_position", "Bollinger position 20", "mean_reversion", "safe_div(close-ts_mean(close,20),2*ts_std(close,20))", ("close",)),
    )
    definitions.extend(
        (
            _definition(
                factor_id=factor_id,
                name=name,
                theme=theme,
                formula=formula,
                required_fields=required_fields,
                available_at_rule="confirmed_bar_close",
                normalization_policy="as_computed_bounded_runtime_value",
                missing_value_policy="record_missing_flag",
                source_artifact_id="demo_release_scanner_factor_contract_v1",
            ),
            "crypto_native",
        )
        for factor_id, name, theme, formula, required_fields in scanner_factors
    )
    return tuple(definitions)


def build_production_factor_registry() -> dict[str, Any]:
    registry = FactorRegistry(max_factors=36)
    source_classes: dict[str, str] = {}
    for definition, source_class in _base_definitions():
        registry.register(definition)
        source_classes[definition.factorId] = source_class

    alpha_records = {row.factor_id: row for row in build_alpha191_registry()}
    for number in sorted(REVIEWED_FORMULAS):
        factor_id = f"alpha191_{number:03d}"
        alpha = alpha_records[factor_id]
        definition = _definition(
            factor_id=factor_id,
            name=f"Alpha191 compatibility {number:03d}",
            theme="alpha191_compatibility",
            formula=str(alpha.canonical_formula),
            required_fields=tuple(alpha.required_columns),
            available_at_rule="confirmed_bar_close",
            normalization_policy="rolling_robust_zscore_120",
            missing_value_policy="exclude_symbol",
            source_artifact_id=f"alpha191_manual_sha256_reviewed_{number:03d}",
        )
        registry.register(definition)
        source_classes[definition.factorId] = "alpha191_compatibility"

    rows = [
        {**row, "sourceClass": source_classes[str(row["factorId"])]}
        for row in registry.to_rows()
    ]
    core = {
        "schemaVersion": "production_factor_registry_v1",
        "boundedMaximum": registry.max_factors,
        "factors": rows,
        "pointInTimeOnly": True,
        "predictiveValueClaimed": False,
        "alpha191Compatibility": {
            "catalogCount": 191,
            "formulaReviewedCount": len(REVIEWED_FORMULAS),
            "numericCrossvalidatedCount": len(REVIEWED_FORMULAS),
            "productionValidatedCount": 0,
            "validationScope": "formula_and_numeric_compatibility_only",
            "allFactorsProductionValidated": False,
        },
    }
    return {
        **core,
        "factorRegistryHash": stable_hash(core, prefix="production_factor_registry"),
    }
