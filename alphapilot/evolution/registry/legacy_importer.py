"""Import existing reports as immutable evidence without automatic promotion."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from alphapilot.evolution.adapters.legacy_report_adapter import (
    classify_legacy_payload,
    load_json_object,
)

from .hashing import sha256_file, stable_hash
from .repositories import RegistryRepository
from .types import LegacyEvidenceRecord, StrategyFamilyRecord


DEFAULT_EXCLUDED_NAMES = {
    "evolution_registry_foundation_report.json",
}


def _relative_source_path(path: Path, reports_dir: Path) -> str:
    return f"reports/{path.relative_to(reports_dir).as_posix()}"


def import_legacy_reports(
    reports_dir: Path | str,
    repository: RegistryRepository,
    *,
    excluded_names: set[str] | None = None,
) -> dict[str, Any]:
    root = Path(reports_dir)
    excluded = DEFAULT_EXCLUDED_NAMES | (excluded_names or set())
    paths = sorted(path for path in root.glob("*.json") if path.name not in excluded)
    existing_rule_members = {
        (item.familyFingerprint, item.ruleFingerprint)
        for item in repository.list_legacy_evidence()
        if item.familyFingerprint and item.evidenceType in {"strategy_candidate_evidence", "duplicate_family_member"}
    }
    seen_rule_members = set(existing_rule_members)
    classifications: Counter[str] = Counter()
    errors: list[dict[str, str]] = []
    new_evidence = 0
    family_ids: set[str] = set()
    valid_object_count = 0
    valid_json_count = 0

    for path in paths:
        payload, error = load_json_object(path)
        if payload is None:
            errors.append({"file": _relative_source_path(path, root), "error": error or "invalid_json"})
            continue
        valid_json_count += 1
        if isinstance(payload, dict):
            valid_object_count += 1
        classification = classify_legacy_payload(path, payload)
        evidence_type = classification.evidenceType
        if evidence_type == "strategy_candidate_evidence":
            rule_member = (classification.familyFingerprint, classification.ruleFingerprint)
            if rule_member in seen_rule_members:
                evidence_type = "duplicate_family_member"
            else:
                seen_rule_members.add(rule_member)

        source_path = _relative_source_path(path, root)
        source_sha = sha256_file(path)
        evidence_id = stable_hash(
            {"sourcePath": source_path, "sourceSha256": source_sha},
            prefix="legacy_evidence",
        )
        family_id = classification.familyFingerprint
        if evidence_type in {"strategy_candidate_evidence", "duplicate_family_member"}:
            family_ids.add(family_id)
            family_metadata = {
                "legacyEvidenceOnly": True,
                "candidateAutoCreationAllowed": False,
                "familyFingerprint": classification.familyFingerprint,
            }
            repository.create_strategy_family(
                StrategyFamilyRecord(
                    strategyFamilyId=family_id,
                    familyKey=classification.familyKey,
                    name=classification.strategyIdentity,
                    status="legacy_evidence_only",
                    metadata=family_metadata,
                    contentHash=stable_hash(family_metadata),
                )
            )
        else:
            family_id = None

        record = LegacyEvidenceRecord(
            legacyEvidenceId=evidence_id,
            sourcePath=source_path,
            sourceSha256=source_sha,
            evidenceType=evidence_type,
            strategyFamilyId=family_id,
            familyFingerprint=classification.familyFingerprint,
            ruleFingerprint=classification.ruleFingerprint,
            classificationReasons=classification.reasons,
            payload=payload,
            contentHash=stable_hash(payload),
        )
        existed = repository.get_legacy_evidence(evidence_id) is not None
        repository.create_legacy_evidence(record)
        if not existed:
            new_evidence += 1
        classifications[evidence_type] += 1

    return {
        "scannedFileCount": len(paths),
        "validJsonCount": valid_json_count,
        "validObjectCount": valid_object_count,
        "invalidFileCount": len(errors),
        "newEvidenceCount": new_evidence,
        "totalEvidenceCount": repository.count("LegacyEvidence"),
        "independentStrategyFamilyCount": len(family_ids),
        "classificationCounts": dict(sorted(classifications.items())),
        "errors": errors,
        "automaticCandidateCreation": False,
        "automaticDemoPromotion": False,
    }
