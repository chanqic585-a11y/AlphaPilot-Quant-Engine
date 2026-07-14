"""Build a null-preserving inventory of archived failed strategies."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

from alphapilot.reports.archived_strategy_failure_analysis_schema import (
    EVIDENCE_LEVELS,
    METRIC_FIELDS,
    NEUTRAL_BASELINE_IDS,
)


VOLUME_ARCHIVE = Path("reports/v13_4_6_strategy_status_archive.json")
VOLUME_EXPANDED = Path("reports/v13_4_5_expanded_validation_report.json")
VOLUME_COMPARATIVE = Path("reports/v13_4_4_comparative_backtest_report.json")
BENCHMARK_ARCHIVE = Path("reports/v13_4_24_benchmark_status_archive.json")
BENCHMARK_SUITE = Path("reports/v13_4_23_benchmark_suite_report.json")
BENCHMARK_REVIEW = Path("reports/v13_4_24_benchmark_result_review.json")
SHORT_ARCHIVE = Path("reports/v13_4_30_short_strategy_status_archive.json")
SHORT_REPORT = Path("reports/v13_4_29_short_rejection_1h_report.json")
SHORT_REVIEW = Path("reports/v13_4_30_short_rejection_failure_review.json")

VOLUME_CLASS_NAMES = {
    "alpha_volume_rebound_v01": "AlphaPilotVolumeReboundV01",
    "alpha_volume_rebound_v02_a_trend_strict": "AlphaPilotVolumeReboundV02ATrendStrict",
    "alpha_volume_rebound_v02_b_volume_quality": "AlphaPilotVolumeReboundV02BVolumeQuality",
    "alpha_volume_rebound_v02_c_exit_cleanup": "AlphaPilotVolumeReboundV02CExitCleanup",
    "alpha_volume_rebound_v02_d_early_failure_exit": "AlphaPilotVolumeReboundV02DEarlyFailureExit",
    "alpha_volume_rebound_v02_e_pair_risk_watchlist": "AlphaPilotVolumeReboundV02EPairRiskWatchlist",
}


def normalize_optional_number(value: Any) -> float | int | None:
    """Return a real number while preserving missing/invalid values as ``None``."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return value
    try:
        text = str(value).strip()
        if not text or text.lower() in {"none", "null", "n/a", "na", "unavailable", "--"}:
            return None
        parsed = float(text)
        return int(parsed) if parsed.is_integer() and "." not in text else parsed
    except (TypeError, ValueError):
        return None


def _read_json(root: Path, relative_path: Path) -> dict[str, Any]:
    path = root / relative_path
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _host_repository_root(root: Path) -> Path:
    if root.parent.name == ".worktrees":
        return root.parent.parent
    return root


def _resolve_existing_path(root: Path, value: str | Path | None) -> Path | None:
    if not value:
        return None
    relative = Path(str(value).replace("\\", "/"))
    if relative.is_absolute() and relative.exists():
        return relative
    for base in (root, _host_repository_root(root)):
        candidate = base / relative
        if candidate.exists():
            return candidate
    return None


def _relative_display(root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    for base in (root, _host_repository_root(root)):
        try:
            return path.relative_to(base).as_posix()
        except ValueError:
            continue
    return str(path)


def _find_strategy_file(root: Path, class_name: str | None) -> str | None:
    if not class_name:
        return None
    search_roots = (root / "user_data" / "strategies", root / "alphapilot")
    needle = f"class {class_name}"
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in search_root.rglob("*.py"):
            try:
                if needle in path.read_text(encoding="utf-8", errors="ignore"):
                    return path.relative_to(root).as_posix()
            except OSError:
                continue
    return None


def _first_dict(rows: Iterable[Any], key: str, value: Any) -> dict[str, Any]:
    for row in rows:
        if isinstance(row, dict) and row.get(key) == value:
            return row
    return {}


def _metric_value(payload: dict[str, Any], *keys: str) -> float | int | None:
    for key in keys:
        if key in payload:
            value = normalize_optional_number(payload.get(key))
            if value is not None:
                return value
    return None


def _pair_count(pair_rows: Any, explicit_pairs: Any = None) -> int | None:
    if isinstance(explicit_pairs, list):
        return len(explicit_pairs)
    if isinstance(pair_rows, list):
        return len(pair_rows)
    return None


def _normalized_metrics(
    raw: dict[str, Any] | None,
    adjusted: dict[str, Any] | None = None,
    *,
    pair_rows: Any = None,
    month_rows: Any = None,
    explicit_pairs: Any = None,
) -> dict[str, Any]:
    raw = raw or {}
    adjusted = adjusted or {}
    metrics = {
        "tradeCount": _metric_value(raw, "tradeCount", "trades"),
        "totalReturnPct": _metric_value(raw, "totalReturnPct", "profit_total_pct"),
        "slippageAdjustedTotalReturnPct": _metric_value(
            adjusted, "slippageAdjustedTotalReturnPct"
        ),
        "winRatePct": _metric_value(raw, "winRate", "winRatePct"),
        "profitFactor": _metric_value(raw, "profitFactor", "profit_factor"),
        "slippageAdjustedProfitFactor": _metric_value(
            adjusted, "slippageAdjustedProfitFactor"
        ),
        "maxDrawdownPct": _metric_value(raw, "maxDrawdownPct", "max_drawdown_account"),
        "maxConsecutiveLosses": _metric_value(raw, "maxConsecutiveLosses"),
        "averageHoldingMinutes": _metric_value(
            raw, "averageHoldingMinutes", "averageDurationMinutes", "duration_avg"
        ),
        "feesPaid": _metric_value(raw, "feesPaid"),
        "slippageCost": _metric_value(adjusted, "totalSlippageCost", "slippageCost"),
        "averageNetR": _metric_value(raw, "averageNetR", "expectancyR"),
        "grossRewardRiskR": _metric_value(raw, "grossRewardRiskR", "targetR"),
        "pairCount": _pair_count(pair_rows, explicit_pairs),
        "monthCount": len(month_rows) if isinstance(month_rows, list) else None,
    }
    return {field: metrics.get(field) for field in METRIC_FIELDS}


def _evidence_level(root: Path, artifact: str | None, evidence_files: list[str]) -> tuple[int, bool]:
    artifact_path = _resolve_existing_path(root, artifact)
    if artifact_path is not None:
        return 1, True
    if any(str(item).lower().endswith(".json") for item in evidence_files):
        return 2, False
    if any(str(item).lower().endswith(".md") for item in evidence_files):
        return 3, False
    return 4, False


def _missing_fields(metrics: dict[str, Any], extra: list[str] | None = None) -> list[str]:
    missing = [field for field in METRIC_FIELDS if metrics.get(field) is None]
    for field in extra or []:
        if field not in missing:
            missing.append(field)
    return missing


def _base_record(
    *,
    root: Path,
    strategy_id: str,
    strategy_name: str,
    family: str,
    status: str,
    reason: str,
    source_archive: Path,
    evidence_files: list[str],
    artifact: str | None,
    class_name: str | None,
    version: str | None,
    direction: str | None,
    timeframe: str | None,
    timerange: str | None,
    pairs: list[str] | None,
    is_mock: bool | None,
    metrics: dict[str, Any],
    breakdowns: dict[str, Any] | None = None,
    extra_missing: list[str] | None = None,
) -> dict[str, Any]:
    level, artifact_exists = _evidence_level(root, artifact, evidence_files)
    strategy_file = _find_strategy_file(root, class_name)
    if strategy_file is None:
        extra_missing = [*(extra_missing or []), "strategyFile"]
    return {
        "strategyId": strategy_id,
        "strategyName": strategy_name,
        "strategyClass": class_name,
        "strategyVersion": version,
        "strategyFamily": family,
        "strategyFile": strategy_file,
        "direction": direction,
        "timeframe": timeframe,
        "pairScope": {
            "mode": "explicit_pairs" if pairs else None,
            "pairCount": len(pairs) if pairs else metrics.get("pairCount"),
            "pairs": pairs,
        },
        "timerange": timerange,
        "isMock": is_mock,
        "realDataConfirmed": is_mock is False or artifact_exists,
        "status": status,
        "reason": reason,
        "source": "local_status_archive",
        "sourceArchive": source_archive.as_posix(),
        "sourceReport": evidence_files[-1] if evidence_files else None,
        "sourceArtifact": artifact,
        "sourceArtifactAvailable": artifact_exists,
        "evidenceLevel": level,
        "evidenceLevelLabel": EVIDENCE_LEVELS[level],
        "evidenceFiles": list(dict.fromkeys(evidence_files)),
        "evidenceComplete": level <= 2 and metrics.get("tradeCount") is not None,
        "missingEvidenceFields": _missing_fields(metrics, extra_missing),
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "metrics": metrics,
        "breakdowns": breakdowns or {
            "pairs": None,
            "months": None,
            "exits": None,
            "regimes": None,
        },
    }


def _volume_inventory(root: Path) -> list[dict[str, Any]]:
    archive = _read_json(root, VOLUME_ARCHIVE)
    expanded = _read_json(root, VOLUME_EXPANDED)
    comparative = _read_json(root, VOLUME_COMPARATIVE)
    expanded_by_name = {
        row.get("strategy"): row
        for row in [expanded.get("baseline"), *(expanded.get("results") or [])]
        if isinstance(row, dict)
    }
    comparative_by_id = {
        row.get("candidateId"): row
        for row in comparative.get("candidateResults") or []
        if isinstance(row, dict)
    }
    scope = expanded.get("scope") or {}
    pairs = expanded.get("supportedPairs") or comparative.get("pairs") or None
    inventory: list[dict[str, Any]] = []
    for archived in archive.get("records") or []:
        strategy_id = archived.get("strategyId")
        class_name = VOLUME_CLASS_NAMES.get(strategy_id)
        expanded_row = expanded_by_name.get(class_name, {})
        comparative_row = comparative_by_id.get(strategy_id, {})
        source_row = expanded_row or comparative_row
        raw = source_row.get("rawMetrics") or source_row.get("metrics") or {}
        adjusted = source_row.get("slippageAdjustedMetrics") or {}
        pair_rows = source_row.get("pairBreakdown") or raw.get("pairPerformance")
        month_rows = source_row.get("monthlyBreakdown") or raw.get("monthlyPerformance")
        metrics = _normalized_metrics(
            raw,
            adjusted,
            pair_rows=pair_rows,
            month_rows=month_rows,
            explicit_pairs=pairs,
        )
        artifact = (
            source_row.get("backtestReport")
            or raw.get("sourceResult")
            or comparative_row.get("backtestReport")
        )
        evidence = [VOLUME_ARCHIVE.as_posix(), *(archived.get("evidenceReports") or [])]
        if artifact:
            evidence.append(str(artifact).replace("\\", "/"))
        inventory.append(
            _base_record(
                root=root,
                strategy_id=strategy_id,
                strategy_name=archived.get("strategyName") or class_name or strategy_id,
                family="volume_rebound",
                status=archived.get("status") or archived.get("researchStatus") or "archived",
                reason=archived.get("reason") or "Archived research failure.",
                source_archive=VOLUME_ARCHIVE,
                evidence_files=evidence,
                artifact=artifact,
                class_name=class_name,
                version="V01" if strategy_id.endswith("v01") else "V02",
                direction="long",
                timeframe=scope.get("timeframe") or comparative.get("timeframe") or "15m",
                timerange=scope.get("timerange") or comparative.get("timerange"),
                pairs=pairs,
                is_mock=False,
                metrics=metrics,
                breakdowns={
                    "pairs": pair_rows,
                    "months": month_rows,
                    "exits": None,
                    "regimes": None,
                },
            )
        )
    return inventory


def _benchmark_inventory(root: Path) -> list[dict[str, Any]]:
    archive = _read_json(root, BENCHMARK_ARCHIVE)
    suite = _read_json(root, BENCHMARK_SUITE)
    review = _read_json(root, BENCHMARK_REVIEW)
    suite_rows = suite.get("benchmarks") or []
    review_rows = review.get("benchmarkReviews") or []
    inventory: list[dict[str, Any]] = []
    for archived in archive.get("benchmarks") or []:
        raw_id = archived.get("benchmarkId")
        suite_row = _first_dict(suite_rows, "benchmarkId", raw_id)
        if not suite_row:
            suite_row = _first_dict(suite_rows, "className", raw_id)
        strategy_id = suite_row.get("benchmarkId") or raw_id
        if strategy_id in NEUTRAL_BASELINE_IDS:
            continue
        review_row = _first_dict(review_rows, "benchmarkId", strategy_id)
        metrics = _normalized_metrics(
            suite_row,
            {
                "slippageAdjustedTotalReturnPct": suite_row.get("slippageAdjustedTotalReturnPct"),
                "slippageAdjustedProfitFactor": suite_row.get("slippageAdjustedProfitFactor"),
                "slippageCost": suite_row.get("slippageCost"),
            },
        )
        artifact = suite_row.get("sourceResult")
        evidence = [
            BENCHMARK_ARCHIVE.as_posix(),
            BENCHMARK_SUITE.as_posix(),
            BENCHMARK_REVIEW.as_posix(),
        ]
        if artifact:
            evidence.append(str(artifact).replace("\\", "/"))
        class_name = suite_row.get("className") or (
            raw_id if str(raw_id).startswith("Benchmark") else None
        )
        inventory.append(
            _base_record(
                root=root,
                strategy_id=strategy_id,
                strategy_name=suite_row.get("name") or archived.get("name") or raw_id,
                family="benchmark_suite",
                status=archived.get("status") or suite_row.get("status") or "archived",
                reason=archived.get("reason") or review_row.get("mainWeakness") or "Archived benchmark.",
                source_archive=BENCHMARK_ARCHIVE,
                evidence_files=evidence,
                artifact=artifact,
                class_name=class_name,
                version="V13.4.23",
                direction=suite_row.get("direction"),
                timeframe=suite_row.get("timeframe") or suite.get("timeframe"),
                timerange=suite.get("timerange"),
                pairs=suite.get("supportedPairs") or None,
                is_mock=False if suite_row else None,
                metrics=metrics,
                breakdowns={
                    "pairs": suite_row.get("pairStability"),
                    "months": suite_row.get("monthlyStability"),
                    "exits": review_row.get("exitAttribution"),
                    "regimes": None,
                },
            )
        )
    return inventory


def _short_inventory(root: Path) -> list[dict[str, Any]]:
    archive = _read_json(root, SHORT_ARCHIVE)
    report = _read_json(root, SHORT_REPORT)
    review = _read_json(root, SHORT_REVIEW)
    raw = dict(report)
    adjusted = {
        "slippageAdjustedTotalReturnPct": report.get("slippageAdjustedTotalReturnPct"),
        "slippageAdjustedProfitFactor": report.get("slippageAdjustedProfitFactor"),
        "slippageCost": (report.get("slippageModel") or {}).get("totalSlippageCost"),
    }
    metrics = _normalized_metrics(
        raw,
        adjusted,
        pair_rows=report.get("pairPerformance"),
        month_rows=report.get("monthlyPerformance"),
        explicit_pairs=report.get("pairs"),
    )
    artifact = report.get("resultFile")
    evidence = [
        SHORT_ARCHIVE.as_posix(),
        SHORT_REPORT.as_posix(),
        SHORT_REVIEW.as_posix(),
        *(archive.get("evidenceReports") or []),
    ]
    if artifact:
        evidence.append(str(artifact).replace("\\", "/"))
    return [
        _base_record(
            root=root,
            strategy_id=archive.get("strategyId") or report.get("strategyId"),
            strategy_name=archive.get("strategyName") or report.get("strategyName"),
            family="short_rejection",
            status=archive.get("status") or "failed_research_current_sample",
            reason=archive.get("reason") or (review.get("overallFailure") or {}).get("conclusion"),
            source_archive=SHORT_ARCHIVE,
            evidence_files=evidence,
            artifact=artifact,
            class_name=report.get("strategyClass") or "AlphaPilotShortRejection1HV01",
            version=report.get("strategyVersion"),
            direction="short",
            timeframe=report.get("timeframe"),
            timerange=report.get("timerange"),
            pairs=report.get("pairs"),
            is_mock=report.get("isMock"),
            metrics=metrics,
            breakdowns={
                "pairs": report.get("pairPerformance"),
                "months": report.get("monthlyPerformance"),
                "exits": report.get("exitReasonBreakdown"),
                "regimes": report.get("regimeBackground"),
            },
            extra_missing=(
                ["perTradeRegimeAttribution"]
                if not (review.get("shortSqueezeRiskReview") or {}).get(
                    "perTradeRegimeAttributionAvailable"
                )
                else []
            ),
        )
    ]


def build_archived_strategy_inventory(root: Path | str) -> list[dict[str, Any]]:
    """Return all failed/rejected records from the repository's status archives."""

    project_root = Path(root).resolve()
    rows = [
        *_volume_inventory(project_root),
        *_benchmark_inventory(project_root),
        *_short_inventory(project_root),
    ]
    unique: dict[str, dict[str, Any]] = {}
    for row in rows:
        strategy_id = row.get("strategyId")
        if not strategy_id:
            continue
        unique[strategy_id] = row
    return [unique[key] for key in sorted(unique)]
