import pandas as pd

from alphapilot.research_screening.pit_universe import build_pit_membership


def test_pit_membership_excludes_future_listing_and_delisted_asset() -> None:
    snapshots = pd.DataFrame(
        {
            "snapshotTimeUtc": pd.to_datetime(["2024-01-01T00:00Z"] * 3),
            "instrumentId": ["A", "B", "C"],
            "listedAt": pd.to_datetime(
                ["2023-01-01T00:00Z", "2024-01-02T00:00Z", "2022-01-01T00:00Z"]
            ),
            "delistedAt": pd.to_datetime([None, None, "2023-12-31T00:00Z"], utc=True),
            "tradingState": ["live", "live", "delisted"],
            "quoteVolume24h": [10_000.0, 10_000.0, 10_000.0],
            "openInterestQuote": [1_000.0, 1_000.0, 1_000.0],
            "spreadProxyBps": [5.0, 5.0, 5.0],
        }
    )

    result = build_pit_membership(snapshots, minimum_listing_days=30)

    assert result.set_index("instrumentId")["included"].to_dict() == {
        "A": True,
        "B": False,
        "C": False,
    }
