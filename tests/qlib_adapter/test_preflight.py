from __future__ import annotations

from alphapilot.qlib_adapter.preflight import QLIB_COMMIT, build_qlib_preflight


def _snapshot(*, verified: bool = True) -> dict[str, object]:
    return {
        "snapshotId": "data_snapshot_abc",
        "snapshotHash": "sha256:abc",
        "hashVerified": verified,
        "containsStrategyResults": False,
        "containsHoldoutResults": False,
    }


def test_qlib_preflight_blocks_when_c_is_not_formal() -> None:
    result = build_qlib_preflight(
        c_status="unavailable",
        pit_metrics={
            "medianInvestableContracts": 0,
            "freshHoldoutReady": False,
        },
        snapshot=_snapshot(),
        environment={"dockerDaemonAvailable": False, "dockerImageAvailable": False},
    )

    assert result["qlibCommit"] == QLIB_COMMIT
    assert result["license"] == "MIT"
    assert result["qlibCampaignMayRun"] is False
    assert result["modelCampaignRun"] is False
    assert result["dockerReproducibilityPassed"] is False
    assert "c_formal_ready" in result["blockers"]


def test_qlib_preflight_allows_only_complete_locked_inputs() -> None:
    result = build_qlib_preflight(
        c_status="formal_ready",
        pit_metrics={
            "medianInvestableContracts": 35,
            "freshHoldoutReady": True,
        },
        snapshot=_snapshot(),
        environment={"dockerDaemonAvailable": True, "dockerImageAvailable": True},
    )

    assert result["qlibCampaignMayRun"] is True
    assert result["blockers"] == []
    assert result["modelCampaignRun"] is False


def test_qlib_preflight_rejects_unverified_snapshot_hash() -> None:
    result = build_qlib_preflight(
        c_status="formal_ready",
        pit_metrics={
            "medianInvestableContracts": 35,
            "freshHoldoutReady": True,
        },
        snapshot=_snapshot(verified=False),
        environment={"dockerDaemonAvailable": True, "dockerImageAvailable": True},
    )

    assert result["qlibCampaignMayRun"] is False
    assert "snapshot_hash_verified" in result["blockers"]
