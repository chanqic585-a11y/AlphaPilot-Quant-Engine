import json
from pathlib import Path

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.advisory_r_campaign.preregistration import (
    build_prefilter_preregistration,
    freeze_prefilter_preregistration,
)


def test_preregistration_freezes_advisory_r_and_zero_side_effects() -> None:
    payload = build_prefilter_preregistration(
        candidates=build_candidate_inventory(),
        snapshot_id="snapshot-test",
        snapshot_hash="snapshot-hash",
        exit_policy_bounds_hash="bounds-hash",
    )

    assert payload["schemaVersion"] == "advisory_r_prefilter_preregistration_v2"
    assert payload["targetRGateMode"] == "advisory"
    assert payload["minimumTargetR"] is None
    assert payload["exitPolicyRequired"] is True
    assert payload["exitPolicyBoundsHash"] == "bounds-hash"
    assert len(payload["candidates"]) == 10
    assert all("exitPolicy" in row for row in payload["candidates"])
    assert payload["prefilterGates"]["minimumProfitFactor"] == 1.03
    assert "minimumTargetR" not in payload["prefilterGates"]
    assert payload["safetyBoundary"] == {
        "holdoutAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def test_freeze_preregistration_writes_stable_campaign_identity(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.json"
    bounds = tmp_path / "bounds.json"
    snapshot.write_text(
        json.dumps({"snapshotId": "snap", "snapshotHash": "snap-hash"}),
        encoding="utf-8",
    )
    bounds.write_text(
        json.dumps({"schemaVersion": "bounds", "minimumTargetR": None}),
        encoding="utf-8",
    )

    first = freeze_prefilter_preregistration(
        repo_root=tmp_path,
        snapshot_path=snapshot,
        bounds_path=bounds,
    )
    second = freeze_prefilter_preregistration(
        repo_root=tmp_path,
        snapshot_path=snapshot,
        bounds_path=bounds,
    )

    assert first == second
    assert first.name.endswith("_prefilter_v2.json")
    payload = json.loads(first.read_text(encoding="utf-8"))
    assert payload["campaignId"] in first.name
    assert payload["preregistrationHash"].startswith("advisory_r_prefilter_preregistration_")
