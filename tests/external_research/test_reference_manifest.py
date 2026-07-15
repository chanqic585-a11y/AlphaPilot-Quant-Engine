from __future__ import annotations

from alphapilot.external_research.reference_manifest import ExternalReference


def test_reference_id_changes_when_frozen_content_changes() -> None:
    first = ExternalReference.create(
        source_type="git",
        repository_or_file="https://example.com/research.git",
        commit_or_hash="a" * 40,
        license_status="verified_mit",
        source_path="D:/external/research",
        retrieved_at="2026-07-16T00:00:00+00:00",
    )
    second = ExternalReference.create(
        source_type="git",
        repository_or_file="https://example.com/research.git",
        commit_or_hash="b" * 40,
        license_status="verified_mit",
        source_path="D:/external/research",
        retrieved_at="2026-07-16T00:00:00+00:00",
    )

    assert first.reference_id != second.reference_id
    assert first.read_only is True


def test_reference_id_does_not_depend_on_retrieval_time() -> None:
    common = {
        "source_type": "file",
        "repository_or_file": "Alpha191.pdf",
        "commit_or_hash": "c" * 64,
        "license_status": "review_required",
        "source_path": "D:/external/Alpha191.pdf",
    }

    first = ExternalReference.create(**common, retrieved_at="2026-07-15T00:00:00+00:00")
    second = ExternalReference.create(**common, retrieved_at="2026-07-16T00:00:00+00:00")

    assert first.reference_id == second.reference_id
    assert first.to_dict()["commitOrHash"] == "c" * 64
