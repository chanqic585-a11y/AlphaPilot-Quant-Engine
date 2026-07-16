from alphapilot.storage_governance.retention_policy import choose_authoritative_record, must_retain


def test_authority_prefers_immutable_evidence_over_size() -> None:
    records = [
        {"path": "small", "sizeBytes": 1, "immutableEvidence": True, "referenceCount": 1},
        {"path": "large", "sizeBytes": 10, "immutableEvidence": False, "referenceCount": 0},
    ]

    assert choose_authoritative_record(records)["path"] == "small"


def test_semantic_manifest_path_is_retained_even_without_explicit_reference() -> None:
    record = {
        "path": r"D:\Codex-Workspace\回测数据\_alphapilot\manifests\contract\walk-forward.json",
        "immutableEvidence": False,
        "referenceCount": 0,
    }

    assert must_retain(record) is True
