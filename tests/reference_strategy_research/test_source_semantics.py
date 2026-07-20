from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from alphapilot.reference_strategy_research.source_semantics import audit_source_semantics


ROOT = "AlphaPilot_Reference_Strategy_Extraction_Package"


def _canonical_hash(value: dict, excluded: str) -> str:
    payload = {key: item for key, item in value.items() if key != excluded}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _source_package(tmp_path: Path, *, corrupt_source: bool = False) -> Path:
    candidates = [
        {
            "schemaVersion": "alphapilot_reference_candidate_v1",
            "candidateId": "ref_utc_session_range_breakout_1h_v1",
            "familyId": "utc_session_range_breakout",
            "timeframe": "1h",
            "directions": ["long", "short"],
            "implementationReadiness": "ready_for_bounded_prefilter",
            "marketHypothesis": "UTC range repricing.",
            "initialStopMayWiden": False,
            "derivation": {
                "type": "source_backed_clean_room_port",
                "sourceFiles": ["source_ea.mq4"],
            },
        },
        {
            "schemaVersion": "alphapilot_reference_candidate_v1",
            "candidateId": "ref_pa_breakout_failure_second_entry_4h_v1",
            "familyId": "price_action_breakout_failure_second_entry",
            "timeframe": "4h",
            "directions": ["long", "short"],
            "implementationReadiness": "ready_after_deterministic_normalization",
            "marketHypothesis": "Second failed breakout.",
            "initialStopMayWiden": False,
            "derivation": {
                "type": "documentation_normalization",
                "sourceFiles": ["second_entry.txt", "breakout_failure.txt"],
            },
        },
    ]
    for candidate in candidates:
        candidate["candidateSpecHash"] = _canonical_hash(candidate, "candidateSpecHash")
    candidate_set = {
        "schemaVersion": "alphapilot_reference_strategy_candidate_set_v1",
        "sourceArchiveSha256": "a" * 64,
        "candidateCount": len(candidates),
        "candidates": candidates,
    }
    payloads = {
        "candidates/candidate_specs.json": json.dumps(
            candidate_set, ensure_ascii=False, indent=2
        ).encode("utf-8"),
        "references/mql_sources/source_ea.mq4": (
            b"extern int LookBackHrs=2; extern int BreakEven=20; "
            b"OrderSend(Symbol(),OP_BUYSTOP,1,1,1,1,1); "
            b"OrderSend(Symbol(),OP_SELLSTOP,1,1,1,1,1);"
        ),
        "references/price_action_docs/second_entry.txt": "二次入场需要结合市场背景。".encode(
            "utf-8"
        ),
        "references/price_action_docs/breakout_failure.txt": "突破后缺少跟进可能失败。".encode(
            "utf-8"
        ),
    }
    files = [
        {
            "path": path,
            "sizeBytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for path, payload in payloads.items()
    ]
    manifest = {
        "schemaVersion": "alphapilot_reference_strategy_package_manifest_v1",
        "sourceArchive": "source.zip",
        "sourceArchiveSha256": "a" * 64,
        "candidateCount": len(candidates),
        "fileCount": len(files),
        "files": files,
    }
    manifest["manifestHash"] = _canonical_hash(manifest, "manifestHash")
    output = tmp_path / "source-package.zip"
    with zipfile.ZipFile(output, "w") as archive:
        for path, payload in payloads.items():
            if corrupt_source and path.endswith("source_ea.mq4"):
                payload += b" modified"
            archive.writestr(f"{ROOT}/{path}", payload)
        archive.writestr(
            f"{ROOT}/package_manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    return output


def test_source_audit_separates_original_semantics_from_normalized_candidates(
    tmp_path: Path,
) -> None:
    audit = audit_source_semantics(_source_package(tmp_path))

    rows = {row["candidateId"]: row for row in audit["candidates"]}
    assert rows["ref_utc_session_range_breakout_1h_v1"]["equivalenceStatus"] == (
        "not_source_equivalent"
    )
    assert rows["ref_pa_breakout_failure_second_entry_4h_v1"]["equivalenceStatus"] == (
        "deterministic_normalization_only"
    )
    assert audit["externalUseClaim"]["assessment"] == "insufficient_evidence"
    assert audit["sourceFilesExecuted"] is False
    assert audit["largeSourcePassagesStored"] is False
    serialized = json.dumps(audit, ensure_ascii=False)
    assert "OrderSend(Symbol()" not in serialized
    assert all(source["sha256"] for row in rows.values() for source in row["sources"])


def test_source_audit_rejects_a_manifest_source_hash_mismatch(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="file hash mismatch"):
        audit_source_semantics(_source_package(tmp_path, corrupt_source=True))
