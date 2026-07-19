from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest


def canonical_hash(value: object) -> str:
    raw = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@pytest.fixture
def reference_package_zip(tmp_path: Path) -> Path:
    candidates = [
        {
            "schemaVersion": "alphapilot_reference_candidate_v1",
            "candidateId": "ref_utc_session_range_breakout_1h_v1",
            "familyId": "utc_session_range_breakout",
            "researchBatch": "batch_1",
            "timeframe": "1h",
            "directions": ["long", "short"],
            "implementationReadiness": "ready_for_bounded_prefilter",
            "marketHypothesis": "Frozen UTC range repricing.",
            "initialStop": {"type": "opposite_range_or_cap"},
            "initialStopMayWiden": False,
            "exitPolicy": {"mode": "structure_or_time", "maximumHoldBars": 12},
            "signal": {"sessionAnchorUtc": "00:00", "rangeBars": 4},
            "dataRequirements": {"required": ["OKX 1H OHLCV"], "timeframe": "1h"},
        },
        {
            "schemaVersion": "alphapilot_reference_candidate_v1",
            "candidateId": "ref_turtle_donchian_20_10_4h_v1",
            "familyId": "canonical_turtle_trend_following",
            "researchBatch": "batch_1",
            "timeframe": "4h",
            "directions": ["long", "short"],
            "implementationReadiness": "ready_for_bounded_prefilter",
            "marketHypothesis": "Canonical trend breakout.",
            "initialStop": {"type": "atr", "atrMultiple": 2.0},
            "initialStopMayWiden": False,
            "exitPolicy": {"mode": "structure_or_time", "maximumHoldBars": 180},
            "signal": {"entryChannelBars": 20},
            "dataRequirements": {"required": ["OKX OHLCV"], "timeframe": "4h"},
        },
        {
            "schemaVersion": "alphapilot_reference_candidate_v1",
            "candidateId": "ref_pa_breakout_failure_second_entry_4h_v1",
            "familyId": "price_action_breakout_failure_second_entry",
            "researchBatch": "batch_1",
            "timeframe": "4h",
            "directions": ["long", "short"],
            "implementationReadiness": "ready_for_bounded_prefilter",
            "marketHypothesis": "A second failed breakout traps late participants.",
            "initialStop": {"type": "failed_test_extreme_or_cap"},
            "initialStopMayWiden": False,
            "exitPolicy": {"mode": "hybrid", "maximumHoldBars": 20},
            "signal": {"boundaryWindowBars": 20, "failureWindowBars": 2},
            "dataRequirements": {"required": ["OKX 4H OHLCV"], "timeframe": "4h"},
        },
    ]
    for candidate in candidates:
        candidate["candidateSpecHash"] = canonical_hash(candidate)
    candidate_set = {
        "schemaVersion": "alphapilot_reference_strategy_candidate_set_v1",
        "sourceArchiveSha256": "a" * 64,
        "candidateCount": len(candidates),
        "readyBatch1Count": len(candidates),
        "candidates": candidates,
    }
    candidate_bytes = json.dumps(candidate_set, ensure_ascii=False, indent=2).encode("utf-8")
    readme_bytes = b"Reference research package."
    files = [
        {
            "path": "README.md",
            "sizeBytes": len(readme_bytes),
            "sha256": hashlib.sha256(readme_bytes).hexdigest(),
        },
        {
            "path": "candidates/candidate_specs.json",
            "sizeBytes": len(candidate_bytes),
            "sha256": hashlib.sha256(candidate_bytes).hexdigest(),
        },
    ]
    manifest = {
        "schemaVersion": "alphapilot_reference_strategy_package_manifest_v1",
        "sourceArchive": "source.zip",
        "sourceArchiveSha256": "a" * 64,
        "candidateCount": len(candidates),
        "fileCount": len(files),
        "files": files,
    }
    manifest["manifestHash"] = canonical_hash(manifest)
    output = tmp_path / "reference.zip"
    root = "AlphaPilot_Reference_Strategy_Extraction_Package"
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(f"{root}/README.md", readme_bytes)
        archive.writestr(f"{root}/candidates/candidate_specs.json", candidate_bytes)
        archive.writestr(
            f"{root}/package_manifest.json",
            json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
        )
    return output
