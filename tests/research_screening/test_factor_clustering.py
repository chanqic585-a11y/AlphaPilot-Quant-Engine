import numpy as np
import pandas as pd

from alphapilot.research_screening.factor_clustering import cluster_factors


def test_cluster_factors_groups_highly_correlated_values() -> None:
    index = pd.date_range("2024-01-01", periods=20, tz="UTC")
    base = pd.DataFrame(np.arange(60).reshape(20, 3), index=index)
    clusters = cluster_factors({"a": base, "b": base * 2, "c": -base}, threshold=0.9)

    assert len(clusters["clusters"]) == 1
    assert clusters["clusters"][0]["factorIds"] == ["a", "b", "c"]
    assert clusters["highlyDuplicatePairs"]
