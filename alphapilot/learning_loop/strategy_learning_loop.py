"""Build a local-paper-only continuous learning loop snapshot.

The learning loop turns existing local paper fills into research outcome
samples. It does not retrain a model, call exchanges, create orders, or approve
Dry-run/live trading. Retraining can only be reviewed after sample and freshness
gates pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import json


ACTIVE_STRATEGY_ID = "v13_5_7_alpha_overlay_fixed_watch"
OBSERVER_STRATEGY_ID = "v13_5_8_adaptive_ml_observer"
MIN_RETRAINING_SAMPLE_COUNT = 100


@dataclass(frozen=True)
class LearningLoopPaths:
    control_tower_report: Path = Path("reports/v13_5_9_strategy_control_tower_report.json")
    local_paper_ledger: Path = Path("reports/v13_5_3_local_paper_sandbox_ledger.json")
    monitoring_report: Path = Path("reports/v13_5_4_local_paper_monitoring_report.json")
    adaptive_ml_report: Path = Path("reports/v13_5_8_adaptive_ml_factor_report.json")
    strategy_evolution_schema: Path = Path("reports/v13_5_8_strategy_evolution_sample_schema.json")


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"missing": True, "path": str(path)}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {"parseError": str(exc), "path": str(path)}


def round_or_none(value: Any, digits: int = 6) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def _safe_text(value: Any, default: str = "unknown") -> str:
    if value is None:
        return default
    text = str(value).strip()
    return text or default


def _outcome_label(fill: dict[str, Any]) -> str:
    r_multiple = round_or_none(fill.get("rMultiple"))
    pnl = round_or_none(fill.get("pnl"))
    if r_multiple is None and pnl is None:
        return "unknown"
    if r_multiple is not None and r_multiple >= 2:
        return "two_r_or_better"
    if pnl is not None and pnl > 0:
        return "positive_under_two_r"
    if pnl is not None and pnl < 0:
        return "loss"
    return "flat_or_unknown"


def _quality_flags(fill: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    required = ["pair", "timeframe", "direction", "entryDate", "exitDate", "entryPrice", "exitPrice"]
    for field in required:
        if fill.get(field) in (None, ""):
            flags.append(f"missing_{field}")
    if fill.get("source") != "local_paper_sandbox_v13_5_3":
        flags.append("non_standard_local_paper_source")
    return flags


def _strategy_id_for_fill(fill: dict[str, Any], active_pool_id: str | None) -> str:
    candidate_id = fill.get("candidateId")
    if active_pool_id and candidate_id == active_pool_id:
        return ACTIVE_STRATEGY_ID
    if candidate_id:
        return _safe_text(candidate_id)
    return "unknown_strategy"


def _build_learning_sample(
    fill: dict[str, Any],
    index: int,
    *,
    active_pool_id: str | None,
    generated_at: str,
) -> dict[str, Any]:
    sample_id = f"v13_5_10_local_paper_sample_{index + 1:04d}"
    strategy_id = _strategy_id_for_fill(fill, active_pool_id)
    return {
        "sampleId": sample_id,
        "recordType": "research_outcome_sample",
        "sourceMode": "local_paper",
        "sourceReport": "reports/v13_5_3_local_paper_sandbox_ledger.json",
        "actualTrade": False,
        "paperSimulationOnly": True,
        "strategyVersion": strategy_id,
        "candidatePoolId": fill.get("candidateId"),
        "pair": fill.get("pair"),
        "timeframe": fill.get("timeframe"),
        "signalTime": fill.get("entryDate"),
        "entryTime": fill.get("entryDate"),
        "exitTime": fill.get("exitDate"),
        "direction": fill.get("direction"),
        "featureSnapshot": {
            "setupName": fill.get("setupName"),
            "source": fill.get("source"),
        },
        "factorSnapshot": {},
        "riskSnapshot": {
            "riskAmount": fill.get("riskAmount"),
            "notionalValue": fill.get("notionalValue"),
        },
        "outcome": {
            "status": fill.get("status"),
            "exitReason": fill.get("exitReason"),
            "entryPrice": fill.get("entryPrice"),
            "exitPrice": fill.get("exitPrice"),
            "quantity": fill.get("quantity"),
            "netReturnPct": fill.get("netReturnPct"),
            "pnl": fill.get("pnl"),
            "rMultiple": fill.get("rMultiple"),
            "outcomeLabel": _outcome_label(fill),
        },
        "quality": {
            "qualityFlags": _quality_flags(fill),
            "usableForRetraining": len(_quality_flags(fill)) == 0,
        },
        "humanReview": {
            "reviewed": False,
            "notes": "Generated from local paper simulation outcome. Human review is still required before promotion.",
        },
        "createdAt": generated_at,
    }


def _summarize_samples(samples: list[dict[str, Any]], *, active_pool_id: str | None = None) -> dict[str, Any]:
    by_label: dict[str, int] = {}
    by_pair: dict[str, int] = {}
    by_strategy: dict[str, int] = {}
    usable_count = 0
    active_strategy_sample_count = 0
    active_strategy_usable_count = 0
    for sample in samples:
        label = sample.get("outcome", {}).get("outcomeLabel") or "unknown"
        pair = sample.get("pair") or "unknown"
        strategy_id = sample.get("strategyVersion") or "unknown"
        is_active_sample = bool(active_pool_id and sample.get("candidatePoolId") == active_pool_id)
        by_label[label] = by_label.get(label, 0) + 1
        by_pair[pair] = by_pair.get(pair, 0) + 1
        by_strategy[strategy_id] = by_strategy.get(strategy_id, 0) + 1
        if sample.get("quality", {}).get("usableForRetraining"):
            usable_count += 1
            if is_active_sample:
                active_strategy_usable_count += 1
        if is_active_sample:
            active_strategy_sample_count += 1
    return {
        "totalSamples": len(samples),
        "usableForRetrainingCount": usable_count,
        "activeStrategySampleCount": active_strategy_sample_count,
        "activeStrategyUsableCount": active_strategy_usable_count,
        "outcomeLabelBreakdown": dict(sorted(by_label.items())),
        "pairBreakdown": dict(sorted(by_pair.items())),
        "strategyBreakdown": dict(sorted(by_strategy.items())),
    }


def _latest_exit_time(samples: list[dict[str, Any]]) -> str | None:
    exits = [sample.get("exitTime") for sample in samples if sample.get("exitTime")]
    return max(exits) if exits else None


def _build_retraining_gate(
    *,
    samples: list[dict[str, Any]],
    monitoring: dict[str, Any],
    control_tower: dict[str, Any],
    active_pool_id: str | None,
) -> dict[str, Any]:
    sample_summary = _summarize_samples(samples, active_pool_id=active_pool_id)
    monitoring_decision = monitoring.get("decision") or {}
    freshness = monitoring.get("freshness") or {}
    control_decision = control_tower.get("decision") or {}
    fail_reasons: list[str] = []
    warning_reasons: list[str] = []

    if sample_summary["usableForRetrainingCount"] < MIN_RETRAINING_SAMPLE_COUNT:
        fail_reasons.append("insufficient_usable_local_paper_samples")
    if sample_summary["activeStrategyUsableCount"] <= 0:
        fail_reasons.append("active_strategy_has_no_closed_local_paper_samples")
    if not freshness.get("closedFillFresh"):
        fail_reasons.append("closed_fill_not_fresh")
    if monitoring_decision.get("monitoringHealth") != "healthy":
        warning_reasons.append("monitoring_health_not_healthy")
    if not control_decision.get("continueLocalPaperMonitoring"):
        fail_reasons.append("control_tower_not_continuing_local_paper_monitoring")

    ready = not fail_reasons
    return {
        "readyForRetraining": ready,
        "minRetrainingSampleCount": MIN_RETRAINING_SAMPLE_COUNT,
        "usableSampleCount": sample_summary["usableForRetrainingCount"],
        "activeStrategyUsableSampleCount": sample_summary["activeStrategyUsableCount"],
        "latestExitTime": _latest_exit_time(samples),
        "freshness": {
            "latestSignal": freshness.get("latestSignal"),
            "latestClosedFill": freshness.get("latestClosedFill"),
            "signalFresh": freshness.get("signalFresh"),
            "closedFillFresh": freshness.get("closedFillFresh"),
        },
        "monitoringHealth": monitoring_decision.get("monitoringHealth"),
        "failReasons": fail_reasons,
        "warningReasons": warning_reasons,
        "allowedNextAction": "prepare_more_local_paper_outcomes" if not ready else "offline_retraining_review",
    }


def build_continuous_learning_loop(paths: LearningLoopPaths | None = None) -> dict[str, Any]:
    paths = paths or LearningLoopPaths()
    generated_at = utc_now()
    control_tower = read_json(paths.control_tower_report)
    ledger = read_json(paths.local_paper_ledger)
    monitoring = read_json(paths.monitoring_report)
    adaptive_ml = read_json(paths.adaptive_ml_report)
    schema = read_json(paths.strategy_evolution_schema)

    control_decision = control_tower.get("decision") or {}
    primary_strategy_id = control_decision.get("primaryActiveStrategyId")
    active_pool_id = None
    for state in control_tower.get("strategyStates") or []:
        if state.get("strategy_id") == primary_strategy_id:
            active_pool_id = state.get("candidate_pool_id")
            break

    fills = ledger.get("fills") or []
    learning_samples = [
        _build_learning_sample(fill, index, active_pool_id=active_pool_id, generated_at=generated_at)
        for index, fill in enumerate(fills)
        if isinstance(fill, dict)
    ]
    sample_summary = _summarize_samples(learning_samples, active_pool_id=active_pool_id)
    retraining_gate = _build_retraining_gate(
        samples=learning_samples,
        monitoring=monitoring,
        control_tower=control_tower,
        active_pool_id=active_pool_id,
    )

    adaptive_decision = adaptive_ml.get("decision") or {}
    learning_state = {
        "version": "V13.5.10",
        "generatedAt": generated_at,
        "learningLoopComputed": True,
        "activeStrategyId": primary_strategy_id,
        "activeCandidatePoolId": active_pool_id,
        "observerStrategyIds": [OBSERVER_STRATEGY_ID],
        "strategyEvolutionDatasetUpdated": True,
        "newTrainingSamplesFromPaper": sample_summary["totalSamples"],
        "usableTrainingSamplesFromPaper": sample_summary["usableForRetrainingCount"],
        "activeStrategySamplesFromPaper": sample_summary["activeStrategySampleCount"],
        "activeStrategyUsableSamplesFromPaper": sample_summary["activeStrategyUsableCount"],
        "readyForRetraining": retraining_gate["readyForRetraining"],
        "continueLocalPaperMonitoring": bool(control_decision.get("continueLocalPaperMonitoring")),
        "exchangeDryRunReviewReady": False,
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
        "reason": "learning_dataset_prepared_but_not_ready_for_retraining"
        if not retraining_gate["readyForRetraining"]
        else "learning_dataset_ready_for_offline_retraining_review",
    }

    return {
        "version": "V13.5.10",
        "reportId": "v13_5_10_continuous_learning_loop_report",
        "generatedAt": generated_at,
        "status": "completed",
        "objective": (
            "Convert local paper outcomes into research evolution samples and gate any future "
            "offline retraining. This report does not retrain a model or grant execution authority."
        ),
        "inputReports": {
            "controlTower": str(paths.control_tower_report),
            "localPaperLedger": str(paths.local_paper_ledger),
            "monitoringReport": str(paths.monitoring_report),
            "adaptiveMlReport": str(paths.adaptive_ml_report),
            "strategyEvolutionSchema": str(paths.strategy_evolution_schema),
        },
        "schemaReference": {
            "schemaVersion": schema.get("schemaVersion"),
            "recordType": schema.get("recordType"),
            "promotionRule": schema.get("promotionRule"),
        },
        "learningState": learning_state,
        "strategyEvolutionDataset": {
            "datasetId": "v13_5_10_strategy_evolution_dataset",
            "datasetType": "local_paper_outcome_samples",
            "createdAt": generated_at,
            "samples": learning_samples,
            "sampleSummary": sample_summary,
        },
        "retrainingGate": retraining_gate,
        "strategyRoles": [
            {
                "strategyId": primary_strategy_id,
                "role": "active_local_paper_watch",
                "candidatePoolId": active_pool_id,
                "canCreateOrders": False,
                "canTriggerDryRun": False,
            },
            {
                "strategyId": OBSERVER_STRATEGY_ID,
                "role": "observer_only",
                "candidatePoolId": adaptive_decision.get("localPaperWatchPoolId"),
                "adaptiveMLComputed": adaptive_decision.get("adaptiveMLComputed"),
                "canCreateOrders": False,
                "canTriggerDryRun": False,
            },
        ],
        "recommendations": [
            "Continue local paper monitoring until fresh closed fills accumulate.",
            "Do not retrain from fewer than 100 usable local paper outcome samples.",
            "Use the generated samples as offline research data only.",
            "Keep V13.5.8 adaptive ML observer-only until it independently improves on the active watch strategy.",
            "Do not move to exchange Dry-run or live trading from this report.",
        ],
        "safetyBoundary": {
            "localPaperOnly": True,
            "actualTradeOutcomes": False,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "emergencyCloseImplemented": False,
            "testnetExecutionImplemented": False,
            "autoTrading": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
        },
    }
