from __future__ import annotations

from alphapilot.research_screening.cluster_bootstrap import cluster_bootstrap_event_metrics


def test_cluster_bootstrap_is_seeded_and_emits_formal_lower_bounds() -> None:
    events = [
        {"cluster": "2026-01", "netR": 1.0},
        {"cluster": "2026-01", "netR": -0.2},
        {"cluster": "2026-02", "netR": 0.8},
        {"cluster": "2026-02", "netR": 0.4},
        {"cluster": "2026-03", "netR": 0.6},
    ]

    first = cluster_bootstrap_event_metrics(events, cluster_field="cluster", draws=500, seed=17)
    second = cluster_bootstrap_event_metrics(events, cluster_field="cluster", draws=500, seed=17)

    assert first == second
    assert first["drawCount"] == 500
    assert set(first["confidenceIntervals"]) == {
        "profitFactor",
        "averageNetR",
        "totalNetR",
        "maximumDrawdownR",
    }
    assert first["formalLowerBounds"]["profitFactorLower90"] > 1.0
    assert first["formalLowerBounds"]["averageNetRLower90"] > 0

