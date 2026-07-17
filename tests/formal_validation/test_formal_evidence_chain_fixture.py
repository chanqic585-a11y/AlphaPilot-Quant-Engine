from __future__ import annotations

from alphapilot.formal_validation.formal_evidence_chain_fixture import (
    run_formal_evidence_chain_fixture,
)


def _runtime() -> dict[str, object]:
    return {
        "runtimeLoaded": True,
        "strategyLoaded": True,
        "configLoaded": True,
        "dataRootValidated": True,
        "timerangeValidated": True,
        "timezone": "UTC",
        "networkAccessCount": 0,
        "lockedOosReadCount": 0,
        "fallbackUsed": False,
        "runtimeHash": "fixture-runtime-hash",
        "pythonVersion": "3.14.6",
        "freqtradeVersion": "2026.6",
        "ccxtVersion": "4.5.61",
        "pandasVersion": "3.0.3",
        "numpyVersion": "2.4.6",
        "pyarrowVersion": "24.0.0",
    }


def test_fixture_certifies_every_required_evidence_layer() -> None:
    report = run_formal_evidence_chain_fixture(runtime_report=_runtime())

    assert report["fixtureId"] == "formal_evidence_chain_fixture_v1"
    assert report["status"] == "certified"
    assert report["fixtureCertified"] is True
    assert report["certification"]["runtimeLoadedFixture"] is True
    assert report["certification"]["identityMappingCompletenessPct"] == 100.0
    assert report["certification"]["foldAssignmentFixtureCompletenessPct"] == 100.0
    assert report["certification"]["rankingEvidenceFixtureParityPct"] == 100.0
    assert report["certification"]["pitContextFixtureParityPct"] == 100.0
    assert report["certification"]["capitalAcceptanceFixtureParityPct"] == 100.0
    assert report["certification"]["positionSizeFixtureParityPct"] == 100.0
    assert report["certification"]["exitFixtureParityPct"] == 100.0


def test_fixture_covers_all_decision_and_exit_paths_without_formal_results() -> None:
    report = run_formal_evidence_chain_fixture(runtime_report=_runtime())

    assert set(report["coverage"]["capitalDecisionPaths"]) == {
        "accepted",
        "capacity_or_sizing_rejected",
        "missing_ranking_field",
        "correlation_cluster_risk_limit",
        "portfolio_beta_limit",
        "concurrent_position_limit",
    }
    assert set(report["coverage"]["exitPaths"]) == {
        "partial",
        "structure",
        "time",
        "stop",
    }
    assert report["coverage"]["foldIds"] == [
        "fold_1",
        "fold_2",
        "fold_3",
        "fold_4",
        "fold_5",
    ]
    assert report["formalResultCount"] == 0
    assert report["releaseCount"] == 0
    assert report["demoArm"] is False
    assert report["orderCount"] == 0
