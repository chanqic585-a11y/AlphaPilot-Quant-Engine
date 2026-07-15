"""Discover archived strategy identities without changing lifecycle state."""

from __future__ import annotations

import ast
import json
import re
import sqlite3
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


def _json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not raw:
        return {}
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def _json_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    if not raw:
        return []
    try:
        value = json.loads(str(raw))
    except (TypeError, ValueError, json.JSONDecodeError):
        return []
    return value if isinstance(value, list) else []


def _table_exists(connection: sqlite3.Connection, table: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone()
    return row is not None


def _rows(connection: sqlite3.Connection, table: str) -> list[dict[str, Any]]:
    if not _table_exists(connection, table):
        return []
    cursor = connection.execute(f'SELECT * FROM "{table}"')
    columns = [item[0] for item in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def _read_registry(root: Path) -> dict[str, list[dict[str, Any]]]:
    path = root / "data" / "evolution_registry.sqlite"
    if not path.exists():
        return {}
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        return {
            table: _rows(connection, table)
            for table in (
                "StrategyFamilies",
                "StrategyVersions",
                "WorkflowRuns",
                "FailureDiagnoses",
                "LegacyEvidence",
            )
        }
    finally:
        connection.close()


def _latest_by(
    rows: Iterable[dict[str, Any]], key: str, date_fields: tuple[str, ...]
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(key)
        if value:
            grouped[str(value)].append(row)

    def sort_key(row: dict[str, Any]) -> tuple[str, ...]:
        return tuple(str(row.get(field) or "") for field in date_fields)

    return {value: sorted(items, key=sort_key)[-1] for value, items in grouped.items()}


def _timeframe(definition: dict[str, Any]) -> str | None:
    formal_plan = _json_object(definition.get("formalDataPlan"))
    forward_policy = _json_object(definition.get("forwardSignalPolicy"))
    for value in (
        definition.get("timeframe"),
        definition.get("signalTimeframe"),
        formal_plan.get("signal"),
        forward_policy.get("timeframe"),
    ):
        if value:
            return str(value)
    return None


def _metric_completeness(metrics: dict[str, Any]) -> float:
    keys = ("tradeCount", "profitFactor", "averageNetR", "maximumDrawdownR", "winRate")
    return round(sum(metrics.get(key) is not None for key in keys) / len(keys), 4)


def _strategy_classes(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    strategy_dir = root / "user_data" / "strategies"
    for path in sorted(strategy_dir.glob("*.py")) if strategy_dir.exists() else []:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, SyntaxError):
            continue
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            assignments: dict[str, Any] = {}
            for child in node.body:
                if isinstance(child, (ast.Assign, ast.AnnAssign)):
                    targets = child.targets if isinstance(child, ast.Assign) else [child.target]
                    value_node = child.value
                    for target in targets:
                        if isinstance(target, ast.Name) and value_node is not None:
                            try:
                                assignments[target.id] = ast.literal_eval(value_node)
                            except (ValueError, TypeError):
                                pass
            if (
                node.name.startswith("_")
                or node.name.startswith("Base")
                or node.name.startswith("IStrategy")
            ):
                continue
            result[node.name] = {
                "sourceFile": path.relative_to(root).as_posix(),
                "timeframe": assignments.get("timeframe"),
                "canShort": assignments.get("can_short"),
                "stoploss": assignments.get("stoploss"),
                "minimalRoi": assignments.get("minimal_roi"),
            }
    return result


def _freqtrade_meta_index(root: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"timeframes": set(), "metaFiles": [], "runCount": 0}
    )
    directory = root / "user_data" / "backtest_results"
    for path in sorted(directory.glob("*.meta.json")) if directory.exists() else []:
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            continue
        if not isinstance(payload, dict):
            continue
        for name, metadata in payload.items():
            if not isinstance(metadata, dict):
                continue
            item = result[str(name)]
            item["runCount"] += 1
            item["metaFiles"].append(path.relative_to(root).as_posix())
            if metadata.get("timeframe"):
                item["timeframes"].add(str(metadata["timeframe"]))
    return result


def _identity_token(value: str) -> str:
    token = re.sub(r"[^a-z0-9]", "", value.lower())
    for prefix in ("alphapilot", "alpha"):
        if token.startswith(prefix):
            token = token[len(prefix) :]
    return token


def _legacy_inventory(root: Path) -> list[dict[str, Any]]:
    try:
        from alphapilot.reports.archived_strategy_inventory import (
            build_archived_strategy_inventory,
        )

        return build_archived_strategy_inventory(root)
    except (ImportError, OSError, ValueError, KeyError, json.JSONDecodeError):
        return []


def build_full_inventory(root: Path | str) -> list[dict[str, Any]]:
    """Return every known archived identity with explicit provenance."""

    project_root = Path(root).resolve()
    registry = _read_registry(project_root)
    families = {
        str(row.get("strategyFamilyId")): row
        for row in registry.get("StrategyFamilies", [])
        if row.get("strategyFamilyId")
    }
    latest_run = _latest_by(
        registry.get("WorkflowRuns", []),
        "strategyVersionId",
        ("completedAt", "checkpointAt", "updatedAt", "createdAt"),
    )
    latest_diagnosis = _latest_by(
        registry.get("FailureDiagnoses", []),
        "workflowRunId",
        ("createdAt",),
    )
    records: list[dict[str, Any]] = []

    for version in sorted(
        registry.get("StrategyVersions", []), key=lambda row: str(row.get("createdAt") or "")
    ):
        strategy_id = str(version.get("strategyVersionId") or "")
        if not strategy_id:
            continue
        family = families.get(str(version.get("strategyFamilyId") or ""), {})
        definition = _json_object(version.get("definitionJson"))
        parameters = _json_object(version.get("parametersJson"))
        run = latest_run.get(strategy_id, {})
        result = _json_object(run.get("resultJson"))
        progress = _json_object(run.get("progressJson"))
        metrics = _json_object(result.get("metrics"))
        diagnosis = latest_diagnosis.get(str(run.get("workflowRunId") or ""), {})
        artifacts = _json_object(progress.get("artifacts"))
        evidence_files = sorted(
            {
                str(value)
                for key, value in artifacts.items()
                if key.lower().endswith("path") and value
            }
        )
        aliases = sorted(
            {
                str(value)
                for value in (
                    version.get("displayName"),
                    family.get("name"),
                    family.get("familyKey"),
                )
                if value
            }
        )
        records.append(
            {
                "strategyId": strategy_id,
                "strategyFamilyId": version.get("strategyFamilyId"),
                "strategyFamily": family.get("familyKey") or family.get("name"),
                "strategyName": version.get("displayName") or family.get("name") or strategy_id,
                "aliases": aliases,
                "identitySource": "registry_version",
                "identityConfidence": "high",
                "sourceType": version.get("sourceType"),
                "status": version.get("status") or "archived",
                "parentStrategyVersionId": version.get("parentStrategyVersionId"),
                "direction": definition.get("direction"),
                "timeframe": _timeframe(definition),
                "timeframes": [_timeframe(definition)] if _timeframe(definition) else [],
                "plannedTargetR": definition.get("plannedTargetR") or definition.get("targetR"),
                "definition": definition,
                "parameters": parameters,
                "metrics": metrics,
                "checks": _json_object(result.get("checks")),
                "researchSmoke": _json_object(result.get("researchSmoke")),
                "workflowRunId": run.get("workflowRunId"),
                "workflowStatus": run.get("status"),
                "workflowAttempt": run.get("attemptNumber"),
                "failureCategory": diagnosis.get("category"),
                "failureSummary": diagnosis.get("summary") or result.get("blocker"),
                "retryDisposition": diagnosis.get("retryDisposition"),
                "failureSuggestions": _json_list(diagnosis.get("suggestionsJson")),
                "evidenceFiles": evidence_files,
                "evidenceLevel": 2 if metrics or evidence_files else 3,
                "evidenceCompleteness": _metric_completeness(metrics),
                "createdAt": version.get("createdAt"),
                "executionEligible": False,
                "dryRunApproved": False,
                "liveTradingApproved": False,
            }
        )

    classes = _strategy_classes(project_root)
    meta_index = _freqtrade_meta_index(project_root)
    for name in sorted(set(classes) | set(meta_index)):
        class_data = classes.get(name, {})
        meta_data = meta_index.get(name, {})
        timeframes = sorted(meta_data.get("timeframes") or [])
        if not timeframes and class_data.get("timeframe"):
            timeframes = [str(class_data["timeframe"])]
        records.append(
            {
                "strategyId": f"freqtrade::{name}",
                "strategyFamilyId": None,
                "strategyFamily": name,
                "strategyName": name,
                "aliases": [name],
                "identitySource": "legacy_freqtrade_class",
                "identityConfidence": "high" if name in classes and name in meta_index else "medium",
                "sourceType": "legacy_freqtrade_backtest",
                "status": "archived_legacy_evidence",
                "parentStrategyVersionId": None,
                "direction": (
                    "long_short" if class_data.get("canShort") is True else "long_or_unspecified"
                ),
                "timeframe": timeframes[0] if len(timeframes) == 1 else None,
                "timeframes": timeframes,
                "plannedTargetR": None,
                "definition": class_data,
                "parameters": {},
                "metrics": {},
                "checks": {},
                "researchSmoke": {},
                "workflowRunId": None,
                "workflowStatus": None,
                "workflowAttempt": None,
                "failureCategory": None,
                "failureSummary": None,
                "retryDisposition": None,
                "failureSuggestions": [],
                "evidenceFiles": list(meta_data.get("metaFiles") or []) + (
                    [class_data["sourceFile"]] if class_data.get("sourceFile") else []
                ),
                "evidenceLevel": 1 if meta_data.get("runCount") else 4,
                "evidenceCompleteness": 0.8 if meta_data.get("runCount") else 0.1,
                "backtestRunCount": meta_data.get("runCount", 0),
                "createdAt": None,
                "executionEligible": False,
                "dryRunApproved": False,
                "liveTradingApproved": False,
            }
        )

    by_token = {
        _identity_token(record["strategyName"]): record
        for record in records
        if record["identitySource"] == "legacy_freqtrade_class"
    }
    existing_ids = {record["strategyId"] for record in records}
    for legacy in _legacy_inventory(project_root):
        legacy_id = str(legacy.get("strategyId") or "")
        if not legacy_id:
            continue
        candidates = (
            _identity_token(legacy_id),
            _identity_token(str(legacy.get("strategyName") or "")),
        )
        target = next((by_token[token] for token in candidates if token in by_token), None)
        if target:
            target["aliases"] = sorted(
                set(target["aliases"] + [legacy_id, str(legacy.get("strategyName") or "")])
                - {""}
            )
            target["evidenceFiles"] = sorted(
                set(target["evidenceFiles"] + list(legacy.get("evidenceFiles") or []))
            )
            target["legacyArchiveId"] = legacy_id
            target["failureSummary"] = target.get("failureSummary") or legacy.get("reason")
            continue
        synthetic_id = f"legacy::{legacy_id}"
        if synthetic_id in existing_ids:
            continue
        records.append(
            {
                "strategyId": synthetic_id,
                "strategyFamilyId": None,
                "strategyFamily": legacy.get("strategyFamily"),
                "strategyName": legacy.get("strategyName") or legacy_id,
                "aliases": [legacy_id],
                "identitySource": "legacy_status_archive",
                "identityConfidence": "medium",
                "sourceType": "legacy_status_archive",
                "status": legacy.get("status") or "archived",
                "parentStrategyVersionId": None,
                "direction": legacy.get("direction"),
                "timeframe": legacy.get("timeframe"),
                "timeframes": [legacy["timeframe"]] if legacy.get("timeframe") else [],
                "plannedTargetR": None,
                "definition": {},
                "parameters": {},
                "metrics": dict(legacy.get("metrics") or {}),
                "checks": {},
                "researchSmoke": {},
                "workflowRunId": None,
                "workflowStatus": None,
                "workflowAttempt": None,
                "failureCategory": None,
                "failureSummary": legacy.get("reason"),
                "retryDisposition": None,
                "failureSuggestions": [],
                "evidenceFiles": list(legacy.get("evidenceFiles") or []),
                "evidenceLevel": legacy.get("evidenceLevel") or 3,
                "evidenceCompleteness": 1.0 if legacy.get("evidenceComplete") else 0.3,
                "createdAt": None,
                "executionEligible": False,
                "dryRunApproved": False,
                "liveTradingApproved": False,
            }
        )
        existing_ids.add(synthetic_id)

    return sorted(records, key=lambda row: (str(row["strategyFamily"]), str(row["strategyId"])))
