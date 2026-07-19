"""Bounded source-lineage audit for reference strategy packages."""

from __future__ import annotations

import zipfile
from pathlib import Path, PurePosixPath
from typing import Any

from .package_loader import load_reference_package


_SELECTED_IDS = {
    "ref_utc_session_range_breakout_1h_v1",
    "ref_pa_breakout_failure_second_entry_4h_v1",
}


def _decode_text(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-16", "gb18030", "cp1252"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8", errors="replace")


def _manifest_rows(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row["path"]): dict(row) for row in manifest.get("files", [])}


def _source_member(
    source_name: str,
    rows: dict[str, dict[str, Any]],
) -> str:
    normalized = PurePosixPath(source_name).name
    matches = [path for path in rows if PurePosixPath(path).name == normalized]
    if len(matches) != 1:
        raise ValueError(f"selected source must resolve exactly once: {source_name}")
    return matches[0]


def _mql_mechanics(text: str) -> list[str]:
    mechanics: list[str] = []
    if "OP_BUYSTOP" in text and "OP_SELLSTOP" in text:
        mechanics.append("opposing_pending_stop_orders")
    if "LookBackHrs" in text:
        mechanics.append("bar_lookback_parameter")
    if "BreakEven" in text:
        mechanics.append("break_even_management")
    if "TakeProfit" in text:
        mechanics.append("take_profit_parameter")
    if "Hour()" in text:
        mechanics.append("broker_hour_dependency")
    if "Point" in text or "Pips" in text:
        mechanics.append("pip_or_point_price_semantics")
    return mechanics


def _candidate_classification(candidate: dict[str, Any]) -> tuple[str, str, list[str]]:
    candidate_id = str(candidate.get("candidateId") or "")
    if candidate_id == "ref_utc_session_range_breakout_1h_v1":
        return (
            "not_source_equivalent",
            "clean_room_research_variant",
            [
                "source uses MetaTrader pending-order execution while V37B uses close confirmation and next-bar open",
                "source broker-time, pip, spread and order lifecycle semantics are not reproduced",
                "source defaults and V37B ATR-normalized range/window parameters differ materially",
                "source break-even and trailing behavior is replaced by a frozen AlphaPilot exit policy",
            ],
        )
    if candidate_id == "ref_pa_breakout_failure_second_entry_4h_v1":
        return (
            "deterministic_normalization_only",
            "documentation_normalization",
            [
                "source material is contextual prose rather than one executable algorithm",
                "20-bar boundary and ATR tolerances are package normalization choices",
                "confirmation, stop and hybrid exit rules are deterministic research assumptions",
            ],
        )
    raise ValueError(f"unsupported selected candidate: {candidate_id}")


def audit_source_semantics(package_path: str | Path) -> dict[str, Any]:
    """Verify source hashes and emit metadata-only equivalence findings."""

    package = load_reference_package(package_path)
    rows = _manifest_rows(package.manifest)
    selected = [
        dict(candidate)
        for candidate in package.candidates
        if candidate.get("candidateId") in _SELECTED_IDS
    ]
    if {row["candidateId"] for row in selected} != _SELECTED_IDS:
        raise ValueError("reference package is missing one or more selected candidates")

    audit_rows: list[dict[str, Any]] = []
    archive_path = Path(package.archivePath)
    with zipfile.ZipFile(archive_path) as archive:
        manifest_members = [name for name in archive.namelist() if name.endswith("package_manifest.json")]
        if len(manifest_members) != 1:
            raise ValueError("archive must contain exactly one package_manifest.json")
        root = PurePosixPath(manifest_members[0]).parent
        for candidate in selected:
            derivation = dict(candidate.get("derivation") or {})
            source_names = [str(value) for value in derivation.get("sourceFiles") or []]
            sources: list[dict[str, Any]] = []
            mechanics: set[str] = set()
            for source_name in source_names:
                relative = _source_member(source_name, rows)
                member_name = (root / PurePosixPath(relative)).as_posix()
                payload = archive.read(member_name)
                text = _decode_text(payload)
                suffix = PurePosixPath(relative).suffix.lower()
                detected = _mql_mechanics(text) if suffix == ".mq4" else []
                mechanics.update(detected)
                sources.append(
                    {
                        "path": relative,
                        "sha256": rows[relative]["sha256"],
                        "sizeBytes": rows[relative]["sizeBytes"],
                        "sourceType": "mql_source" if suffix == ".mq4" else "qualitative_documentation",
                        "summary": (
                            "MetaTrader strategy source with platform-specific execution semantics."
                            if suffix == ".mq4"
                            else "Qualitative price-action reference requiring deterministic normalization."
                        ),
                    }
                )
            equivalence, translation_class, gaps = _candidate_classification(candidate)
            audit_rows.append(
                {
                    "candidateId": candidate["candidateId"],
                    "derivationType": derivation.get("type"),
                    "equivalenceStatus": equivalence,
                    "translationClass": translation_class,
                    "detectedSourceMechanics": sorted(mechanics),
                    "materialGaps": gaps,
                    "sources": sources,
                }
            )

    return {
        "schemaVersion": "reference_strategy_source_lineage_audit_v1",
        "archivePath": package.archivePath,
        "archiveSha256": package.archiveSha256,
        "manifestHash": package.manifest.get("manifestHash"),
        "sourceArchiveSha256": package.manifest.get("sourceArchiveSha256"),
        "sourceFilesExecuted": False,
        "largeSourcePassagesStored": False,
        "externalUseClaim": {
            "assessment": "insufficient_evidence",
            "reason": (
                "Source availability or third-party use is not comparable audited performance evidence "
                "without verified fills, market, period, costs and risk controls."
            ),
        },
        "candidates": sorted(audit_rows, key=lambda row: row["candidateId"]),
    }
