"""Hash-verified data reuse and deterministic gap planning."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Iterable, Sequence

from alphapilot.research_screening.campaign_contract import CandidateSpec


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def audit_candidate_data(
    *,
    candidates: Sequence[CandidateSpec],
    catalog: dict[str, Any],
    instruments: Iterable[str],
) -> dict[str, Any]:
    """Reuse each verified symbol/timeframe partition once across all candidates."""

    requirements = sorted(
        {
            (str(instrument), candidate.timeframe)
            for candidate in candidates
            for instrument in instruments
        }
    )
    available: dict[tuple[str, str], dict[str, Any]] = {}
    invalid: list[dict[str, Any]] = []
    for row in catalog.get("datasets", []):
        if not isinstance(row, dict) or row.get("dataType") != "ohlcv":
            continue
        source_path = Path(str(row.get("sourcePath") or ""))
        expected_hash = str(row.get("contentHash") or "")
        valid = source_path.is_file() and len(expected_hash) == 64
        if valid:
            valid = _file_hash(source_path) == expected_hash
        symbols = row.get("symbols") if isinstance(row.get("symbols"), list) else []
        timeframe = str(row.get("timeframe") or "")
        for symbol in symbols:
            key = (str(symbol), timeframe)
            if valid:
                available.setdefault(key, row)
            elif key in requirements:
                invalid.append(
                    {
                        "instrumentId": key[0],
                        "timeframe": key[1],
                        "datasetId": row.get("datasetId"),
                        "reason": "missing_or_hash_mismatch",
                    }
                )

    missing = [
        {"instrumentId": instrument, "timeframe": timeframe}
        for instrument, timeframe in requirements
        if (instrument, timeframe) not in available
    ]
    return {
        "ready": not missing,
        "downloadRequired": bool(missing),
        "requiredPartitionCount": len(requirements),
        "reusedDatasetCount": sum(key in available for key in requirements),
        "missing": missing,
        "invalid": invalid,
        "gapPlan": [
            {**row, "mode": "gap_only", "status": "not_started"}
            for row in missing
        ],
    }
