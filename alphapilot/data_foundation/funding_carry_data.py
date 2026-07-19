"""Causal same-exchange data contracts for funding-carry research."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Any

import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash


MILLISECONDS_PER_DAY = 86_400_000


@dataclass(frozen=True)
class FundingCarryDataPolicy:
    """Frozen data policy; it does not define or approve a strategy."""

    schema_version: str
    exchange: str
    assets: tuple[str, ...]
    quote_asset: str
    timeframe: str
    history_start: str
    maximum_lag_seconds: int
    minimum_aligned_rows: int
    minimum_coverage_days: int
    maximum_stale_fraction: float
    zero_fill_allowed: bool
    cross_exchange_substitution_allowed: bool

    @classmethod
    def default(
        cls,
        *,
        assets: tuple[str, ...] = ("BTC", "ETH", "SOL"),
        minimum_aligned_rows: int = 1_000,
        minimum_coverage_days: int = 730,
    ) -> "FundingCarryDataPolicy":
        normalized_assets = tuple(sorted({str(asset).upper() for asset in assets}))
        if not normalized_assets:
            raise ValueError("funding_carry_assets_must_not_be_empty")
        if minimum_aligned_rows <= 0:
            raise ValueError("minimum_aligned_rows_must_be_positive")
        if minimum_coverage_days < 0:
            raise ValueError("minimum_coverage_days_must_not_be_negative")
        return cls(
            schema_version="v37a_funding_carry_data_policy_v1",
            exchange="OKX",
            assets=normalized_assets,
            quote_asset="USDT",
            timeframe="1h",
            history_start="2022-03-01T00:00:00+00:00",
            maximum_lag_seconds=3_600,
            minimum_aligned_rows=int(minimum_aligned_rows),
            minimum_coverage_days=int(minimum_coverage_days),
            maximum_stale_fraction=0.01,
            zero_fill_allowed=False,
            cross_exchange_substitution_allowed=False,
        )

    @property
    def policy_hash(self) -> str:
        return stable_hash(asdict(self), prefix="v37a_funding_carry_data_policy")

    def with_assets(self, assets: tuple[str, ...]) -> "FundingCarryDataPolicy":
        normalized = tuple(sorted({str(asset).upper() for asset in assets}))
        if not normalized:
            raise ValueError("funding_carry_assets_must_not_be_empty")
        return replace(self, assets=normalized)


def _timestamp_series(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_datetime(frame[column], utc=True, errors="coerce")
    if values.isna().any():
        raise ValueError(f"invalid_timestamp_column:{column}")
    # Pandas may preserve microsecond precision for ISO strings. Timestamp.value
    # is always nanoseconds, so this conversion is stable across pandas versions.
    return values.map(lambda value: pd.Timestamp(value).value // 1_000_000).astype(
        "int64"
    )


def _prepare_candles(
    frame: pd.DataFrame,
    *,
    asset: str,
    instrument_id: str,
    prefix: str,
) -> pd.DataFrame:
    required = {
        "exchange",
        "instrumentId",
        "timestamp_ms",
        "availableAt",
        "close",
        "volCcyQuote",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{prefix}_candle_columns_missing:{','.join(missing)}")
    if set(frame["exchange"].dropna().astype(str)) != {"OKX"}:
        raise ValueError("funding_carry_requires_same_exchange_okx")
    if set(frame["instrumentId"].dropna().astype(str)) != {instrument_id}:
        raise ValueError(f"{prefix}_instrument_mismatch")

    prepared = pd.DataFrame(
        {
            f"{prefix}SourceTimestampMs": pd.to_numeric(
                frame["timestamp_ms"], errors="coerce"
            ),
            f"{prefix}AvailableAtMs": _timestamp_series(frame, "availableAt"),
            f"{prefix}Price": pd.to_numeric(frame["close"], errors="coerce"),
            f"{prefix}QuoteTurnover": pd.to_numeric(
                frame["volCcyQuote"], errors="coerce"
            ),
            f"{prefix}InstrumentId": frame["instrumentId"].astype(str),
            "asset": asset,
        }
    )
    numeric = [
        f"{prefix}SourceTimestampMs",
        f"{prefix}Price",
        f"{prefix}QuoteTurnover",
    ]
    if prepared[numeric].isna().any().any():
        raise ValueError(f"{prefix}_candle_values_invalid")
    if (prepared[f"{prefix}Price"] <= 0).any():
        raise ValueError(f"{prefix}_price_not_positive")
    if (prepared[f"{prefix}QuoteTurnover"] < 0).any():
        raise ValueError(f"{prefix}_quote_turnover_negative")
    prepared[f"{prefix}SourceTimestampMs"] = prepared[
        f"{prefix}SourceTimestampMs"
    ].astype("int64")
    prepared = prepared.sort_values(f"{prefix}AvailableAtMs").drop_duplicates(
        f"{prefix}AvailableAtMs", keep="last"
    )
    return prepared.reset_index(drop=True)


def _prepare_funding(frame: pd.DataFrame, *, instrument_id: str) -> pd.DataFrame:
    required = {"instrument_id", "timestamp_ms", "available_at", "funding_rate"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"funding_columns_missing:{','.join(missing)}")
    if set(frame["instrument_id"].dropna().astype(str)) != {instrument_id}:
        raise ValueError("funding_instrument_mismatch")
    prepared = pd.DataFrame(
        {
            "decisionTimestampMs": pd.to_numeric(
                frame["timestamp_ms"], errors="coerce"
            ),
            "decisionAvailableAtMs": _timestamp_series(frame, "available_at"),
            "fundingRate": pd.to_numeric(frame["funding_rate"], errors="coerce"),
            "fundingInstrumentId": frame["instrument_id"].astype(str),
        }
    )
    if prepared.isna().any().any():
        raise ValueError("funding_values_invalid")
    prepared["decisionTimestampMs"] = prepared["decisionTimestampMs"].astype(
        "int64"
    )
    if (prepared["decisionAvailableAtMs"] < prepared["decisionTimestampMs"]).any():
        raise ValueError("funding_available_before_funding_time")
    return prepared.sort_values("decisionAvailableAtMs").drop_duplicates(
        "decisionTimestampMs", keep="last"
    ).reset_index(drop=True)


def build_causal_funding_carry_panel(
    *,
    asset: str,
    spot: pd.DataFrame,
    perpetual: pd.DataFrame,
    funding: pd.DataFrame,
    maximum_lag_seconds: int,
) -> pd.DataFrame:
    """Align realized funding with data available at that decision timestamp."""

    if maximum_lag_seconds <= 0:
        raise ValueError("maximum_lag_seconds_must_be_positive")
    normalized_asset = str(asset).upper()
    spot_instrument = f"{normalized_asset}-USDT"
    perpetual_instrument = f"{normalized_asset}-USDT-SWAP"
    spot_ready = _prepare_candles(
        spot,
        asset=normalized_asset,
        instrument_id=spot_instrument,
        prefix="spot",
    )
    perpetual_ready = _prepare_candles(
        perpetual,
        asset=normalized_asset,
        instrument_id=perpetual_instrument,
        prefix="perpetual",
    )
    funding_ready = _prepare_funding(funding, instrument_id=perpetual_instrument)

    aligned = pd.merge_asof(
        funding_ready,
        spot_ready,
        left_on="decisionAvailableAtMs",
        right_on="spotAvailableAtMs",
        direction="backward",
        allow_exact_matches=True,
    )
    aligned = pd.merge_asof(
        aligned.sort_values("decisionAvailableAtMs"),
        perpetual_ready.drop(columns=["asset"]),
        left_on="decisionAvailableAtMs",
        right_on="perpetualAvailableAtMs",
        direction="backward",
        allow_exact_matches=True,
    )
    aligned = aligned.dropna(
        subset=[
            "spotSourceTimestampMs",
            "perpetualSourceTimestampMs",
            "spotPrice",
            "perpetualPrice",
        ]
    ).copy()
    if aligned.empty:
        return aligned

    for column in (
        "spotSourceTimestampMs",
        "spotAvailableAtMs",
        "perpetualSourceTimestampMs",
        "perpetualAvailableAtMs",
    ):
        aligned[column] = aligned[column].astype("int64")
    if (
        aligned["spotAvailableAtMs"] > aligned["decisionAvailableAtMs"]
    ).any() or (
        aligned["perpetualAvailableAtMs"] > aligned["decisionAvailableAtMs"]
    ).any():
        raise AssertionError("funding_carry_forward_join_detected")

    aligned["basisPct"] = (
        aligned["perpetualPrice"] / aligned["spotPrice"] - 1.0
    ) * 100.0
    aligned["spotLagSeconds"] = (
        aligned["decisionAvailableAtMs"] - aligned["spotAvailableAtMs"]
    ) / 1_000.0
    aligned["perpetualLagSeconds"] = (
        aligned["decisionAvailableAtMs"] - aligned["perpetualAvailableAtMs"]
    ) / 1_000.0
    aligned["stale"] = (
        aligned[["spotLagSeconds", "perpetualLagSeconds"]].max(axis=1)
        > maximum_lag_seconds
    )
    aligned["dualLegQuoteTurnoverProxy"] = aligned[
        ["spotQuoteTurnover", "perpetualQuoteTurnover"]
    ].min(axis=1, skipna=False)
    aligned["joinDirection"] = "backward_asof"
    aligned["exchange"] = "OKX"
    aligned["zeroFillUsed"] = False
    aligned["crossExchangeSubstitution"] = False
    return aligned.sort_values("decisionTimestampMs").reset_index(drop=True)
