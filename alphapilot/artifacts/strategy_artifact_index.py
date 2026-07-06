from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VERSION = "V13.7.4"
SOURCE = "alphapilot_strategy_artifact_center_v13_7_4"

ROOT_DIR = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT_DIR / "reports"
OUTPUT_FILE = REPORTS_DIR / "strategy_artifact_index.json"

EXCLUDED_REPORTS = {
    "runtime_status.json",
    "signal_tape.json",
    "paper_observation_ledger.json",
    "strategy_artifact_index.json",
}

SAFETY_BOUNDARY = {
    "tradeApiUsed": False,
    "withdrawApiUsed": False,
    "apiKeyStored": False,
    "accountRead": False,
    "positionRead": False,
    "orderCreated": False,
    "dryRunExecuted": False,
    "liveTradingUsed": False,
    "autoTradingUsed": False,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def as_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return round(float(value), 6)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    number = as_number(value)
    return int(number) if number is not None else None


def slug(value: str | None) -> str:
    if not value:
        return "unknown"
    return re.sub(r"[^a-zA-Z0-9_]+", "_", value).strip("_").lower() or "unknown"


def title_from_id(value: str | None) -> str:
    clean = slug(value).replace("_", " ").strip()
    return clean.title() if clean else "Unknown Strategy Artifact"


def compact_source_file(path: Path) -> str:
    try:
        return path.relative_to(ROOT_DIR).as_posix()
    except ValueError:
        return path.as_posix()


def get_dict(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key)
    return value if isinstance(value, dict) else {}


def find_first_dict(data: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    for key in keys:
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return {}


def bool_from_paths(report: dict[str, Any], keys: list[str]) -> bool:
    dicts = [report, get_dict(report, "decision"), get_dict(report, "gate"), get_dict(report, "safetyBoundary")]
    for mapping in dicts:
        for key in keys:
            if mapping.get(key) is True:
                return True
    return False


def extract_metrics(raw: dict[str, Any]) -> dict[str, Any]:
    trade_count = (
        as_int(raw.get("tradeCount"))
        or as_int(raw.get("filledSignalCount"))
        or as_int(raw.get("selectedSignalCount"))
        or as_int(raw.get("signalCount"))
    )
    win_rate = as_number(raw.get("winRatePct"))
    if win_rate is None:
        win_rate = as_number(raw.get("winRate"))
    max_drawdown = as_number(raw.get("maxDrawdownPct"))
    if max_drawdown is None:
        max_drawdown = as_number(raw.get("maxDrawdownPercent"))
    if max_drawdown is None:
        max_drawdown = as_number(raw.get("max_drawdown"))
    total_return = as_number(raw.get("totalReturnPct"))
    if total_return is None:
        total_return = as_number(raw.get("netReturnPct"))
    if total_return is None:
        total_return = as_number(raw.get("profit_total_pct"))

    return {
        "sampleCount": trade_count,
        "tradeCount": trade_count,
        "winRatePct": win_rate,
        "profitFactor": as_number(raw.get("profitFactor")),
        "rewardRiskRatio": as_number(raw.get("rewardRiskRatio")),
        "maxDrawdownPct": max_drawdown,
        "totalReturnPct": total_return,
        "slippageAdjustedReturnPct": as_number(raw.get("slippageAdjustedReturnPct")),
        "slippageAdjustedProfitFactor": as_number(raw.get("slippageAdjustedProfitFactor")),
        "maxConsecutiveLosses": as_int(raw.get("maxConsecutiveLosses")),
    }


def merge_metrics(*metric_dicts: dict[str, Any]) -> dict[str, Any]:
    merged: dict[str, Any] = {
        "sampleCount": None,
        "tradeCount": None,
        "winRatePct": None,
        "profitFactor": None,
        "rewardRiskRatio": None,
        "maxDrawdownPct": None,
        "totalReturnPct": None,
        "slippageAdjustedReturnPct": None,
        "slippageAdjustedProfitFactor": None,
        "maxConsecutiveLosses": None,
    }
    for metrics in metric_dicts:
        for key, value in metrics.items():
            if merged.get(key) is None and value is not None:
                merged[key] = value
    return merged


def metrics_from_report(report: dict[str, Any]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for key in ("ledgerMetrics", "metrics", "fullMetrics", "ledgerReportedMetrics"):
        value = report.get(key)
        if isinstance(value, dict):
            candidates.append(extract_metrics(value))

    best_raw = get_dict(report, "bestRawCandidate")
    if best_raw:
        candidates.append(extract_metrics(get_dict(best_raw, "metrics")))

    best_exit = get_dict(report, "bestExitAwarePolicy")
    if best_exit:
        candidates.append(extract_metrics(get_dict(best_exit, "metrics")))

    local_paper = get_dict(report, "localPaperSimulation")
    if local_paper:
        candidates.append(extract_metrics(get_dict(local_paper, "ledgerMetrics")))

    best_candidate = get_dict(report, "bestCandidate")
    if best_candidate:
        candidates.append(extract_metrics(best_candidate))
        candidates.append(extract_metrics(get_dict(best_candidate, "metrics")))

    return merge_metrics(*candidates) if candidates else extract_metrics(report)


def safety_summary(report: dict[str, Any]) -> dict[str, Any]:
    safety = get_dict(report, "safetyBoundary")
    decision = get_dict(report, "decision")
    return {
        "tradeApiUsed": bool(safety.get("tradeApiUsed", False)),
        "withdrawApiUsed": bool(safety.get("withdrawApiUsed", False)),
        "apiKeyStored": bool(safety.get("apiKeyStored", False)),
        "accountRead": bool(safety.get("accountRead", False)),
        "positionRead": bool(safety.get("positionRead", False)),
        "orderCreated": bool(safety.get("orderCreated", False)),
        "dryRunApproved": bool(
            report.get("dryRunApproved", False)
            or decision.get("exchangeDryRunApproved", False)
            or safety.get("dryRunApproved", False)
        ),
        "liveTradingApproved": bool(
            report.get("liveTradingApproved", False)
            or decision.get("liveTradingApproved", False)
            or safety.get("liveTradingApproved", False)
        ),
        "autoTradingUsed": bool(safety.get("autoTradingUsed", False)),
    }


def baseline_status(report: dict[str, Any], node: dict[str, Any] | None = None) -> dict[str, Any]:
    source = node or report
    baseline = get_dict(source, "baselineComparison")
    if not baseline:
        baseline = get_dict(report, "baselineComparison")
    return {
        "available": bool(baseline),
        "beatsNoTrade": baseline.get("beatsNoTrade") or baseline.get("beatsNoTradeCount"),
        "beatsEqualWeight": baseline.get("beatsEqualWeight") or baseline.get("beatsEqualWeightCount"),
        "researchWorthContinuing": source.get("researchWorthContinuing", report.get("researchWorthContinuing")),
    }


def readiness_from_metrics(
    metrics: dict[str, Any],
    report: dict[str, Any],
    status: str | None,
    baseline: dict[str, Any],
) -> tuple[str, list[str], bool, bool, float]:
    reasons: list[str] = []
    score = 0.0
    sample_count = as_int(metrics.get("sampleCount"))
    profit_factor = as_number(metrics.get("profitFactor"))
    reward_risk = as_number(metrics.get("rewardRiskRatio"))
    max_drawdown = as_number(metrics.get("maxDrawdownPct"))
    total_return = as_number(metrics.get("totalReturnPct"))

    if status and status not in {"completed", "success", "ok"}:
        return "archived_or_failed", [f"report_status={status}"], False, False, 0.0

    if sample_count is None:
        reasons.append("missing_sample_count")
    elif sample_count < 30:
        reasons.append("sample_count_below_30")
    else:
        score += min(30.0, sample_count / 10.0)

    if profit_factor is None:
        reasons.append("missing_profit_factor")
    elif profit_factor >= 1.2:
        score += 25.0
    elif profit_factor >= 1.0:
        score += 14.0
    else:
        reasons.append("profit_factor_below_1")

    if reward_risk is None:
        reasons.append("missing_reward_risk_ratio")
    elif reward_risk >= 1.5:
        score += 20.0
    elif reward_risk >= 1.0:
        score += 10.0
    else:
        reasons.append("reward_risk_below_1")

    if max_drawdown is None:
        reasons.append("missing_max_drawdown")
    elif max_drawdown <= 25:
        score += 15.0
    elif max_drawdown <= 40:
        score += 8.0
    else:
        reasons.append("drawdown_above_40")

    if total_return is not None and total_return > 0:
        score += 10.0
    elif total_return is not None:
        reasons.append("non_positive_total_return")

    gate_passed = bool_from_paths(
        report,
        [
            "passed",
            "localPaperGatePassed",
            "localPaperRefreshCandidateReady",
            "localPaperSandboxApproved",
            "paperMonitoringReady",
            "researchWorthContinuing",
        ],
    ) or baseline.get("researchWorthContinuing") is True

    paper_ready = bool(
        sample_count is not None
        and sample_count >= 30
        and profit_factor is not None
        and profit_factor >= 1.2
        and reward_risk is not None
        and reward_risk >= 1.5
        and max_drawdown is not None
        and max_drawdown <= 35
        and (total_return is None or total_return > 0)
    )
    shadow_ready = bool(
        sample_count is not None
        and sample_count >= 30
        and profit_factor is not None
        and profit_factor >= 1.0
        and (max_drawdown is None or max_drawdown <= 45)
    )

    if paper_ready:
        tier = "paper_observation_ready"
        reasons.append("metrics_passed_paper_observation_gate")
    elif shadow_ready or gate_passed:
        tier = "research_watchlist"
        reasons.append("research_context_available")
    elif sample_count is None and profit_factor is None and reward_risk is None:
        tier = "needs_review"
        reasons.append("no_standard_metrics_found")
    else:
        tier = "archived_or_failed"
        reasons.append("metrics_failed_research_gate")

    return tier, reasons, paper_ready, shadow_ready, round(score, 2)


def artifact_from_node(
    report: dict[str, Any],
    path: Path,
    node: dict[str, Any],
    suffix: str,
    metrics: dict[str, Any],
) -> dict[str, Any]:
    report_id = str(report.get("reportId") or path.stem)
    strategy_id = str(
        node.get("strategyId")
        or node.get("candidateId")
        or node.get("strategyClass")
        or report.get("candidateId")
        or report_id
    )
    status = str(node.get("status") or report.get("status") or "completed")
    baseline = baseline_status(report, node)
    tier, reasons, paper_ready, shadow_ready, score = readiness_from_metrics(metrics, report, status, baseline)
    safety = safety_summary(report)
    if any(safety.get(key) for key in ("tradeApiUsed", "withdrawApiUsed", "apiKeyStored", "accountRead", "positionRead", "orderCreated", "autoTradingUsed")):
        tier = "blocked_by_safety_review"
        reasons.append("safety_boundary_violation_detected")
        paper_ready = False
        shadow_ready = False

    artifact_id = f"{slug(strategy_id)}__{slug(suffix)}"
    title = node.get("description") or node.get("title") or node.get("strategyClass") or title_from_id(strategy_id)

    return {
        "artifactId": artifact_id,
        "strategyId": strategy_id,
        "title": title,
        "version": report.get("version"),
        "reportId": report_id,
        "status": status,
        "generatedAt": report.get("generatedAt"),
        "sourceFile": compact_source_file(path),
        "sourceKind": suffix,
        "metrics": metrics,
        "baselineStatus": baseline,
        "readinessTier": tier,
        "researchScore": score,
        "readinessReasons": sorted(set(reasons)),
        "paperObservationEligible": paper_ready,
        "shadowEligible": shadow_ready,
        "exchangeDryRunApproved": safety.get("dryRunApproved", False),
        "liveTradingApproved": safety.get("liveTradingApproved", False),
        "safetyBoundary": safety,
        "recommendedAction": recommended_action(tier),
    }


def recommended_action(tier: str) -> str:
    if tier == "paper_observation_ready":
        return "Review the evidence, then consider local paper observation only. No exchange execution is approved."
    if tier == "research_watchlist":
        return "Keep this artifact in research watchlist and gather more validation evidence."
    if tier == "needs_review":
        return "Review the source report manually because standard metrics are missing or incomplete."
    if tier == "blocked_by_safety_review":
        return "Block this artifact from runtime surfaces until safety fields are reviewed."
    return "Archive as research evidence unless a future report improves the metrics."


def artifacts_from_report(report: dict[str, Any], path: Path) -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []

    strategy_results = report.get("strategyResults")
    if isinstance(strategy_results, list):
        for index, node in enumerate(strategy_results):
            if isinstance(node, dict):
                artifacts.append(
                    artifact_from_node(
                        report,
                        path,
                        node,
                        f"strategy_result_{index + 1}",
                        extract_metrics(node),
                    )
                )
        return artifacts

    main_metrics = metrics_from_report(report)
    artifacts.append(artifact_from_node(report, path, report, "report_summary", main_metrics))

    best_raw = get_dict(report, "bestRawCandidate")
    if best_raw:
        artifacts.append(
            artifact_from_node(report, path, best_raw, "best_raw_candidate", extract_metrics(get_dict(best_raw, "metrics")))
        )

    best_exit = get_dict(report, "bestExitAwarePolicy")
    if best_exit:
        artifacts.append(
            artifact_from_node(report, path, best_exit, "best_exit_aware_policy", extract_metrics(get_dict(best_exit, "metrics")))
        )

    local_paper = get_dict(report, "localPaperSimulation")
    if local_paper:
        artifacts.append(
            artifact_from_node(
                report,
                path,
                local_paper,
                "local_paper_simulation",
                extract_metrics(get_dict(local_paper, "ledgerMetrics")),
            )
        )

    return dedupe_artifacts(artifacts)


def dedupe_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[str, dict[str, Any]] = {}
    for item in artifacts:
        artifact_id = item["artifactId"]
        existing = deduped.get(artifact_id)
        if not existing or item.get("researchScore", 0) >= existing.get("researchScore", 0):
            deduped[artifact_id] = item
    return list(deduped.values())


def should_index(path: Path) -> bool:
    if path.name in EXCLUDED_REPORTS:
        return False
    if path.name.endswith("_signal_log.json") or path.name.endswith("_selected_signals.json"):
        return False
    if path.name.endswith("_sample.json") or "sample_dataset" in path.name or "snapshots" in path.name:
        return False
    return path.name.endswith(".json") and ("report" in path.name or path.name in {"latest_backtest_report.json", "smoke_backtest_report.json", "sample_backtest_report.json"})


def sort_artifacts(artifacts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    tier_rank = {
        "paper_observation_ready": 0,
        "research_watchlist": 1,
        "needs_review": 2,
        "archived_or_failed": 3,
        "blocked_by_safety_review": 4,
    }
    return sorted(
        artifacts,
        key=lambda item: (
            tier_rank.get(item.get("readinessTier"), 9),
            -(item.get("researchScore") or 0),
            item.get("generatedAt") or "",
        ),
    )


def build_strategy_artifact_index(reports_dir: Path = REPORTS_DIR) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    indexed_files: list[str] = []
    skipped_files: list[str] = []
    errors: list[dict[str, str]] = []

    if reports_dir.exists():
        for path in sorted(reports_dir.glob("*.json")):
            if not should_index(path):
                skipped_files.append(compact_source_file(path))
                continue
            report = read_json(path)
            if not report:
                errors.append({"file": compact_source_file(path), "error": "invalid_json_or_non_object"})
                continue
            file_artifacts = artifacts_from_report(report, path)
            if file_artifacts:
                artifacts.extend(file_artifacts)
                indexed_files.append(compact_source_file(path))
            else:
                skipped_files.append(compact_source_file(path))

    artifacts = sort_artifacts(dedupe_artifacts(artifacts))
    summary = build_summary(artifacts, indexed_files, skipped_files, errors)
    return {
        "version": VERSION,
        "source": SOURCE,
        "generatedAt": now_iso(),
        "reportsDir": str(reports_dir),
        "summary": summary,
        "safetyBoundary": SAFETY_BOUNDARY,
        "artifacts": artifacts,
        "topArtifacts": artifacts[:10],
        "indexedFiles": indexed_files,
        "skippedFiles": skipped_files,
        "errors": errors,
        "notes": [
            "This index is built from local research reports only.",
            "Readiness tiers are research routing labels, not trading approval.",
            "No Trade API, Withdraw API, account read, position read, order creation, dry-run, live trading, or auto trading is performed.",
        ],
    }


def build_summary(
    artifacts: list[dict[str, Any]],
    indexed_files: list[str],
    skipped_files: list[str],
    errors: list[dict[str, str]],
) -> dict[str, Any]:
    latest = max((item.get("generatedAt") for item in artifacts if item.get("generatedAt")), default=None)
    return {
        "totalArtifacts": len(artifacts),
        "indexedFileCount": len(indexed_files),
        "skippedFileCount": len(skipped_files),
        "errorCount": len(errors),
        "paperObservationReadyCount": sum(1 for item in artifacts if item.get("readinessTier") == "paper_observation_ready"),
        "researchWatchlistCount": sum(1 for item in artifacts if item.get("readinessTier") == "research_watchlist"),
        "needsReviewCount": sum(1 for item in artifacts if item.get("readinessTier") == "needs_review"),
        "archivedOrFailedCount": sum(1 for item in artifacts if item.get("readinessTier") == "archived_or_failed"),
        "blockedBySafetyReviewCount": sum(1 for item in artifacts if item.get("readinessTier") == "blocked_by_safety_review"),
        "latestSourceGeneratedAt": latest,
    }


def generate_strategy_artifact_index() -> dict[str, Any]:
    payload = build_strategy_artifact_index()
    write_json(OUTPUT_FILE, payload)
    return payload
