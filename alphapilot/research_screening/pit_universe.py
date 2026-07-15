"""Point-in-time universe membership decisions with explicit exclusions."""

from __future__ import annotations

import pandas as pd


def build_pit_membership(
    snapshots: pd.DataFrame,
    *,
    minimum_listing_days: int,
    minimum_quote_volume: float = 0.0,
    maximum_spread_bps: float | None = None,
) -> pd.DataFrame:
    result = snapshots.copy()
    age_days = (result["snapshotTimeUtc"] - result["listedAt"]).dt.total_seconds() / 86400
    listed = result["listedAt"].notna() & (result["listedAt"] <= result["snapshotTimeUtc"])
    not_delisted = result["delistedAt"].isna() | (result["delistedAt"] > result["snapshotTimeUtc"])
    live = result["tradingState"].eq("live")
    seasoned = age_days >= minimum_listing_days
    liquid = result["quoteVolume24h"].fillna(-1) >= minimum_quote_volume
    spread_ok = True if maximum_spread_bps is None else result["spreadProxyBps"].fillna(float("inf")) <= maximum_spread_bps
    result["included"] = listed & not_delisted & live & seasoned & liquid & spread_ok

    def reason(row: pd.Series) -> str:
        if row["included"]:
            return "included"
        if pd.isna(row["listedAt"]) or row["listedAt"] > row["snapshotTimeUtc"]:
            return "not_listed_at_snapshot"
        if pd.notna(row["delistedAt"]) and row["delistedAt"] <= row["snapshotTimeUtc"]:
            return "delisted_at_snapshot"
        if row["tradingState"] != "live":
            return "not_live"
        if (row["snapshotTimeUtc"] - row["listedAt"]).total_seconds() / 86400 < minimum_listing_days:
            return "listing_age_below_minimum"
        if pd.isna(row["quoteVolume24h"]) or row["quoteVolume24h"] < minimum_quote_volume:
            return "liquidity_below_minimum"
        return "spread_above_maximum"

    result["reasonZh"] = result.apply(reason, axis=1)
    return result
