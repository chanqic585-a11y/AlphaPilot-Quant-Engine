from __future__ import annotations

from alphapilot.external_research.adoption_matrix import (
    AdoptionRecord,
    validate_adoption_matrix,
)


def test_adoption_matrix_rejects_copying_from_blocked_license() -> None:
    record = AdoptionRecord(
        source="alpha101",
        frozen_sha="a" * 40,
        source_module="alpha101.py",
        target_module="alphapilot.factor_lab",
        copied_code=True,
        license_name="unverified_empty_license_file",
        status="许可证阻塞",
        adoption_reason="",
        rejection_reason="No usable license text is present.",
        test_plan="Independent implementation only after license review.",
    )

    errors = validate_adoption_matrix([record])

    assert errors == ["alpha101: blocked-license source cannot copy code"]


def test_reference_only_record_is_valid_without_copying_code() -> None:
    record = AdoptionRecord(
        source="Vibe-Trading",
        frozen_sha="b" * 40,
        source_module="factor research workflow",
        target_module="alphapilot.factor_lab",
        copied_code=False,
        license_name="MIT",
        status="参考后重写",
        adoption_reason="Use concepts while preserving AlphaPilot safety contracts.",
        rejection_reason="",
        test_plan="Cross-check independent numeric fixtures.",
    )

    assert validate_adoption_matrix([record]) == []
