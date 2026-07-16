from alphapilot.storage_governance.cleanup_planner import build_cleanup_plan


def test_planner_requires_all_safety_gates() -> None:
    graph = {
        "files": [
            {"path": "old", "sha256": "old-hash", "sizeBytes": 10, "referenceCount": 0, "immutableEvidence": False},
            {"path": "authority", "sha256": "authority-hash", "sizeBytes": 20, "referenceCount": 0, "immutableEvidence": False},
            {"path": "referenced", "sha256": "ref-hash", "sizeBytes": 30, "referenceCount": 1, "immutableEvidence": True},
        ]
    }
    duplicates = {
        "groups": [
            {
                "duplicateClass": "rolling_snapshot_superseded",
                "authoritativePath": "authority",
                "authoritativeSha256": "authority-hash",
                "members": ["old", "referenced"],
                "contentVerified": True,
            }
        ]
    }

    plan = build_cleanup_plan(graph, duplicates)

    assert [item["path"] for item in plan["candidates"]] == ["old"]
    assert plan["reclaimableBytes"] == 10
    assert plan["blocked"][0]["path"] == "referenced"
