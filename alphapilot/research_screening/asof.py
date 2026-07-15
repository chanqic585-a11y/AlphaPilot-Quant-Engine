"""Backward-only point-in-time joins with source-age evidence."""

from __future__ import annotations

from collections.abc import Sequence

import pandas as pd


def backward_asof_join(
    left: pd.DataFrame,
    right: pd.DataFrame,
    *,
    value_columns: Sequence[str],
    max_age_seconds: float,
    timestamp_column: str = "timestampUtc",
) -> pd.DataFrame:
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be non-negative")
    source = right[[timestamp_column, *value_columns]].copy()
    source = source.rename(columns={timestamp_column: "sourceTimestamp"})
    result = pd.merge_asof(
        left.sort_values(timestamp_column),
        source.sort_values("sourceTimestamp"),
        left_on=timestamp_column,
        right_on="sourceTimestamp",
        direction="backward",
        allow_exact_matches=True,
    )
    if (result["sourceTimestamp"].dropna() > result.loc[result["sourceTimestamp"].notna(), timestamp_column]).any():
        raise AssertionError("future source timestamp detected")
    result["ageSeconds"] = (
        result[timestamp_column] - result["sourceTimestamp"]
    ).dt.total_seconds()
    result["stale"] = result["sourceTimestamp"].isna() | (result["ageSeconds"] > max_age_seconds)
    return result
