import pandas as pd

from alphapilot.research_screening.asof import backward_asof_join


def test_backward_asof_never_uses_future_source() -> None:
    left = pd.DataFrame(
        {"timestampUtc": pd.to_datetime(["2024-01-01T01:00Z", "2024-01-01T02:00Z"])}
    )
    right = pd.DataFrame(
        {
            "timestampUtc": pd.to_datetime(["2024-01-01T00:30Z", "2024-01-01T01:30Z"]),
            "funding": [0.01, 0.02],
        }
    )

    joined = backward_asof_join(left, right, value_columns=("funding",), max_age_seconds=3600)

    assert joined["funding"].tolist() == [0.01, 0.02]
    assert (joined["sourceTimestamp"] <= joined["timestampUtc"]).all()
    assert joined["ageSeconds"].tolist() == [1800.0, 1800.0]
    assert not joined["stale"].any()
