from alphapilot.storage_governance.retention_policy import choose_authoritative_record


def test_authority_prefers_immutable_evidence_over_size() -> None:
    records = [
        {"path": "small", "sizeBytes": 1, "immutableEvidence": True, "referenceCount": 1},
        {"path": "large", "sizeBytes": 10, "immutableEvidence": False, "referenceCount": 0},
    ]

    assert choose_authoritative_record(records)["path"] == "small"
