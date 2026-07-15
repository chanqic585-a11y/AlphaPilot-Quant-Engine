from alphapilot.research_screening.data_readiness import evaluate_data_readiness


def test_data_readiness_requires_three_mechanisms_and_non_ohlcv() -> None:
    ready = evaluate_data_readiness(
        [
            {"mechanismId": "trend", "ready": True, "usesNonOhlcv": False},
            {"mechanismId": "shock", "ready": True, "usesNonOhlcv": False},
            {"mechanismId": "funding", "ready": True, "usesNonOhlcv": True},
        ],
        manifest_verified=True,
        controls_verified=True,
        trial_ledger_complete=True,
        fdr_complete=True,
        clusters_complete=True,
        shortlist_frozen=True,
        pit_status="diagnostic_proxy",
    )
    blocked = evaluate_data_readiness(
        [
            {"mechanismId": "trend", "ready": True, "usesNonOhlcv": False},
            {"mechanismId": "shock", "ready": True, "usesNonOhlcv": False},
        ],
        manifest_verified=True,
        controls_verified=True,
        trial_ledger_complete=True,
        fdr_complete=True,
        clusters_complete=True,
        shortlist_frozen=True,
        pit_status="diagnostic_proxy",
    )

    assert ready["passed"]
    assert not blocked["passed"]
    assert "minimum_mechanism_families" in blocked["blockers"]
