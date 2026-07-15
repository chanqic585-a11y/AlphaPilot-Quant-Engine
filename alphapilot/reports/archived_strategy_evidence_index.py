"""Evidence discovery and grading for archived strategy identities."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import zipfile
from pathlib import Path
from typing import Any


def _canonical_hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_hash_cache(root: Path) -> dict[tuple[str, int, int], str]:
    path = root / "reports" / "full_archived_strategy_evidence_index.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {}
    result = {}
    for item in payload.get("artifacts") or []:
        source = item.get("sourcePath")
        size = item.get("artifactSize")
        mtime = item.get("artifactMtimeNs")
        digest = item.get("artifactHash")
        if source and isinstance(size, int) and isinstance(mtime, int) and digest:
            result[(str(source), size, mtime)] = str(digest)
    return result


def _cached_file_hash(root: Path, path: Path, cache: dict[tuple[str, int, int], str]) -> str:
    relative = path.relative_to(root).as_posix()
    stat = path.stat()
    key = (relative, stat.st_size, stat.st_mtime_ns)
    return cache.get(key) or _file_hash(path)


def _zip_shape(path: Path) -> dict[str, Any]:
    result = {
        "zipReadable": False,
        "hasResultJson": False,
        "hasConfigJson": False,
        "hasStrategySource": False,
        "containsTrades": None,
        "zipError": None,
    }
    try:
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
        result.update(
            {
                "zipReadable": True,
                "hasResultJson": any(
                    name.endswith(".json") and "config" not in name.lower() for name in names
                ),
                "hasConfigJson": any(
                    name.endswith(".json") and "config" in name.lower() for name in names
                ),
                "hasStrategySource": any(name.endswith(".py") for name in names),
            }
        )
    except (OSError, zipfile.BadZipFile) as exc:
        result["zipError"] = str(exc)
    return result


def _registry_evidence(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in inventory:
        if item.get("identitySource") != "registry_version":
            continue
        material = {
            "strategyId": item.get("strategyId"),
            "workflowRunId": item.get("workflowRunId"),
            "workflowStatus": item.get("workflowStatus"),
            "metrics": item.get("metrics"),
            "checks": item.get("checks"),
            "failureSummary": item.get("failureSummary"),
            "evidenceFiles": item.get("evidenceFiles"),
        }
        rows.append(
            {
                "artifactId": f"registry::{item['strategyId']}",
                "strategyId": item["strategyId"],
                "strategyFamilyId": item.get("strategyFamilyId"),
                "strategyName": item.get("strategyName"),
                "artifactType": "registry_workflow_result",
                "evidenceLevel": 2,
                "sourcePath": (
                    f"data/evolution_registry.sqlite#StrategyVersions/{item['strategyId']}"
                ),
                "artifactHash": _canonical_hash(material),
                "artifactSize": None,
                "artifactMtimeNs": None,
                "timeframe": item.get("timeframe"),
                "backtestStartTs": None,
                "backtestEndTs": None,
                "isMock": False,
                "tradeRowsAvailable": False,
                "completenessScore": item.get("evidenceCompleteness", 0.0),
                "readable": True,
                "conflicts": [],
                "notes": [
                    "结构化工作流指标可审计，但当前工作流产物没有逐笔交易行。"
                ],
            }
        )
    return rows


def _freqtrade_evidence(
    root: Path, inventory: list[dict[str, Any]], cache: dict[tuple[str, int, int], str]
) -> list[dict[str, Any]]:
    known = {item["strategyId"] for item in inventory}
    result_dir = root / "user_data" / "backtest_results"
    rows: list[dict[str, Any]] = []
    for meta_path in sorted(result_dir.glob("*.meta.json")) if result_dir.exists() else []:
        try:
            metadata = json.loads(meta_path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(metadata, dict):
            continue
        zip_path = meta_path.with_name(meta_path.name.replace(".meta.json", ".zip"))
        zip_shape = _zip_shape(zip_path) if zip_path.exists() else {
            "zipReadable": False,
            "hasResultJson": False,
            "hasConfigJson": False,
            "hasStrategySource": False,
            "containsTrades": None,
            "zipError": "missing_zip",
        }
        source = zip_path if zip_path.exists() else meta_path
        source_stat = source.stat()
        source_relative = source.relative_to(root).as_posix()
        digest = _cached_file_hash(root, source, cache)
        for strategy_name, run in metadata.items():
            if not isinstance(run, dict):
                continue
            strategy_id = f"freqtrade::{strategy_name}"
            completeness = sum(
                (
                    zip_shape["zipReadable"],
                    zip_shape["hasResultJson"],
                    zip_shape["hasConfigJson"],
                    bool(run.get("timeframe")),
                    run.get("backtest_start_ts") is not None,
                    run.get("backtest_end_ts") is not None,
                )
            ) / 6
            rows.append(
                {
                    "artifactId": f"freqtrade::{digest[:20]}::{strategy_name}",
                    "strategyId": strategy_id if strategy_id in known else None,
                    "unresolvedStrategyName": None if strategy_id in known else strategy_name,
                    "strategyFamilyId": None,
                    "strategyName": strategy_name,
                    "artifactType": "freqtrade_backtest_zip" if zip_path.exists() else "freqtrade_meta_only",
                    "evidenceLevel": 1 if zip_path.exists() and zip_shape["zipReadable"] else 2,
                    "sourcePath": source_relative,
                    "sourceMetaPath": meta_path.relative_to(root).as_posix(),
                    "sourceZip": zip_path.relative_to(root).as_posix() if zip_path.exists() else None,
                    "artifactHash": digest,
                    "artifactSize": source_stat.st_size,
                    "artifactMtimeNs": source_stat.st_mtime_ns,
                    "timeframe": run.get("timeframe"),
                    "backtestStartTs": run.get("backtest_start_ts"),
                    "backtestEndTs": run.get("backtest_end_ts"),
                    "runId": run.get("run_id"),
                    "isMock": False,
                    "tradeRowsAvailable": bool(
                        zip_path.exists() and zip_shape["zipReadable"] and zip_shape["hasResultJson"]
                    ),
                    "completenessScore": round(completeness, 4),
                    "readable": bool(zip_shape["zipReadable"]),
                    "conflicts": [],
                    "notes": [zip_shape["zipError"]] if zip_shape.get("zipError") else [],
                }
            )
    return rows


def _legacy_registry_evidence(root: Path) -> list[dict[str, Any]]:
    path = root / "data" / "evolution_registry.sqlite"
    if not path.exists():
        return []
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='LegacyEvidence'"
        ).fetchone()
        if not exists:
            return []
        cursor = connection.execute("SELECT * FROM LegacyEvidence")
        columns = [item[0] for item in cursor.description]
        source_rows = [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]
    finally:
        connection.close()
    rows = []
    for item in source_rows:
        source_path = str(item.get("sourcePath") or "")
        level = 2 if item.get("evidenceType") in {"report_summary", "strategy_candidate_evidence"} else 4
        rows.append(
            {
                "artifactId": item.get("legacyEvidenceId"),
                "strategyId": None,
                "strategyFamilyId": item.get("strategyFamilyId"),
                "strategyName": None,
                "artifactType": f"legacy_{item.get('evidenceType') or 'unknown'}",
                "evidenceLevel": level,
                "sourcePath": source_path,
                "artifactHash": item.get("sourceSha256") or item.get("contentHash") or _canonical_hash(item),
                "artifactSize": None,
                "artifactMtimeNs": None,
                "timeframe": None,
                "backtestStartTs": None,
                "backtestEndTs": None,
                "isMock": level == 4,
                "tradeRowsAvailable": False,
                "completenessScore": 0.5 if level == 2 else 0.1,
                "readable": (root / source_path).exists() if source_path else False,
                "conflicts": [],
                "notes": json.loads(item.get("classificationReasonsJson") or "[]"),
            }
        )
    return rows


def _indexed_report_evidence(root: Path) -> list[dict[str, Any]]:
    path = root / "reports" / "strategy_artifact_index.json"
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return []
    rows = []
    for item in payload.get("artifacts") or []:
        source = str(item.get("sourceFile") or "")
        source_path = root / source
        digest = _file_hash(source_path) if source_path.exists() and source_path.is_file() else _canonical_hash(item)
        rows.append(
            {
                "artifactId": f"report-index::{item.get('artifactId') or digest[:20]}",
                "strategyId": None,
                "unresolvedStrategyName": item.get("strategyId"),
                "strategyFamilyId": None,
                "strategyName": item.get("title") or item.get("strategyId"),
                "artifactType": "indexed_structured_report",
                "evidenceLevel": 2 if str(source).endswith(".json") else 3,
                "sourcePath": source,
                "artifactHash": digest,
                "artifactSize": source_path.stat().st_size if source_path.exists() else None,
                "artifactMtimeNs": source_path.stat().st_mtime_ns if source_path.exists() else None,
                "timeframe": None,
                "backtestStartTs": None,
                "backtestEndTs": None,
                "isMock": False,
                "tradeRowsAvailable": False,
                "completenessScore": 0.5,
                "readable": source_path.exists(),
                "conflicts": [],
                "notes": ["策略身份无法仅凭旧索引安全映射到当前不可变版本。"],
            }
        )
    return rows


def build_evidence_index(
    root: Path | str, inventory: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    project_root = Path(root).resolve()
    cache = _load_hash_cache(project_root)
    rows = []
    rows.extend(_registry_evidence(inventory))
    rows.extend(_freqtrade_evidence(project_root, inventory, cache))
    rows.extend(_legacy_registry_evidence(project_root))
    rows.extend(_indexed_report_evidence(project_root))
    return sorted(
        rows,
        key=lambda item: (
            int(item.get("evidenceLevel") or 99),
            str(item.get("strategyId") or item.get("unresolvedStrategyName") or ""),
            str(item.get("sourcePath") or ""),
        ),
    )
