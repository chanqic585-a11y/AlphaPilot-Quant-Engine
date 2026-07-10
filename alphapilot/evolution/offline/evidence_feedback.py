"""Classify immutable outcomes and derive offline-only research feedback."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from statistics import fmean
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.types import OutcomeLedgerRecord


FORMAL_EVIDENCE_CLASSES = (
    "historical_path_replay",
    "realtime_local_forward",
    "okx_demo",
    "live",
)
QUARANTINED_EVIDENCE_CLASSES = {
    "historical_path_replay_probe",
    "legacy_synthetic",
    "synthetic_forward",
}


def _parse_time(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class EvidenceIngestionResult:
    acceptedByClass: dict[str, list[OutcomeLedgerRecord]]
    quarantined: list[dict[str, str]]
    invalid: list[dict[str, str]]

    @property
    def formalOutcomeCount(self) -> int:
        return sum(len(rows) for rows in self.acceptedByClass.values())

    def to_dict(self) -> dict[str, Any]:
        return {
            "formalOutcomeCount": self.formalOutcomeCount,
            "acceptedCounts": {
                name: len(self.acceptedByClass.get(name, []))
                for name in FORMAL_EVIDENCE_CLASSES
            },
            "acceptedOutcomeIds": {
                name: [row.outcomeId for row in self.acceptedByClass.get(name, [])]
                for name in FORMAL_EVIDENCE_CLASSES
            },
            "quarantinedCount": len(self.quarantined),
            "quarantined": self.quarantined,
            "invalidCount": len(self.invalid),
            "invalid": self.invalid,
            "syntheticEvidencePromoted": False,
        }


def _integrity_reason(record: OutcomeLedgerRecord) -> str | None:
    if record.status != "closed":
        return "outcome_not_closed"
    if not record.contentHash or not record.dataSnapshotId:
        return "lineage_incomplete"
    decision_at = _parse_time(record.decisionAt)
    entry_at = _parse_time(record.entryAt)
    exit_at = _parse_time(record.exitAt)
    if None in {decision_at, entry_at, exit_at}:
        return "event_time_invalid"
    if not decision_at <= entry_at <= exit_at:
        return "event_time_order_invalid"
    payload_class = str(record.outcome.get("evidenceClass") or record.evidenceClass)
    if payload_class != record.evidenceClass:
        return "evidence_class_mismatch"
    if record.evidenceClass == "historical_path_replay":
        if not bool(record.outcome.get("usesActualCanonicalCandlePath")):
            return "actual_candle_path_not_proven"
        if record.sourceEntityType == "engine_probe":
            return "engine_probe_not_formal_evidence"
    if record.evidenceClass == "realtime_local_forward":
        public_driven = record.outcome.get("publicMarketDriven")
        if public_driven is not True:
            return "public_market_forward_not_proven"
    if record.evidenceClass == "okx_demo":
        if not str(record.outcome.get("demoReleaseId") or "").strip():
            return "demo_release_lineage_missing"
    if record.evidenceClass == "live":
        if not str(record.outcome.get("liveReleaseId") or "").strip():
            return "live_release_lineage_missing"
    return None


def ingest_evidence_classed_outcomes(
    outcomes: list[OutcomeLedgerRecord],
) -> EvidenceIngestionResult:
    accepted = {name: [] for name in FORMAL_EVIDENCE_CLASSES}
    quarantined: list[dict[str, str]] = []
    invalid: list[dict[str, str]] = []
    for record in sorted(outcomes, key=lambda row: (row.decisionAt, row.outcomeId)):
        if record.evidenceClass in QUARANTINED_EVIDENCE_CLASSES:
            quarantined.append(
                {
                    "outcomeId": record.outcomeId,
                    "evidenceClass": record.evidenceClass,
                    "reason": "non_formal_or_synthetic_evidence_class",
                }
            )
            continue
        if record.evidenceClass not in accepted:
            quarantined.append(
                {
                    "outcomeId": record.outcomeId,
                    "evidenceClass": record.evidenceClass,
                    "reason": "unsupported_evidence_class",
                }
            )
            continue
        reason = _integrity_reason(record)
        if reason:
            invalid.append(
                {
                    "outcomeId": record.outcomeId,
                    "evidenceClass": record.evidenceClass,
                    "reason": reason,
                }
            )
            continue
        accepted[record.evidenceClass].append(record)
    return EvidenceIngestionResult(accepted, quarantined, invalid)


def _trade(record: OutcomeLedgerRecord) -> dict[str, Any]:
    trade = record.outcome.get("trade")
    return trade if isinstance(trade, dict) else record.outcome


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _net_r(record: OutcomeLedgerRecord) -> float | None:
    trade = _trade(record)
    for key in ("netR", "realizedR", "rewardR"):
        value = _finite(trade.get(key))
        if value is not None:
            return value
    net_pnl = _finite(trade.get("netPnl"))
    risk = _finite(trade.get("riskAmount"))
    if net_pnl is not None and risk is not None and risk > 0:
        return net_pnl / risk
    return None


def _gross_r(record: OutcomeLedgerRecord) -> float | None:
    trade = _trade(record)
    return _finite(trade.get("grossR"))


def _metric_summary(records: list[OutcomeLedgerRecord]) -> dict[str, Any]:
    ordered = sorted(records, key=lambda row: (row.exitAt, row.outcomeId))
    metric_rows = [(row, _net_r(row)) for row in ordered]
    valid = [(row, value) for row, value in metric_rows if value is not None]
    net_values = [value for _, value in valid]
    gains = sum(value for value in net_values if value > 0)
    losses = abs(sum(value for value in net_values if value < 0))
    profit_factor = gains / losses if losses > 0 else None
    wins = sum(value > 0 for value in net_values)
    trades = [_trade(row) for row, _ in valid]
    exit_reasons = Counter(str(trade.get("exitReason") or "unknown") for trade in trades)
    symbols = Counter(row.instrumentId for row, _ in valid)
    months = Counter(row.exitAt[:7] for row, _ in valid)
    gross_pairs = [(_gross_r(row), value) for row, value in valid]
    cost_drags = [gross - net for gross, net in gross_pairs if gross is not None]
    same_bar_count = sum(bool(trade.get("sameBarAmbiguous")) for trade in trades)
    midpoint = len(valid) // 2
    early = [value for _, value in valid[:midpoint]]
    recent = [value for _, value in valid[midpoint:]]
    early_mean = fmean(early) if early else None
    recent_mean = fmean(recent) if recent else None
    decay_delta = recent_mean - early_mean if early_mean is not None and recent_mean is not None else None
    return {
        "closedOutcomeCount": len(records),
        "metricAvailableCount": len(valid),
        "metricUnavailableCount": len(records) - len(valid),
        "netRSum": sum(net_values),
        "meanNetR": fmean(net_values) if net_values else None,
        "winRate": wins / len(net_values) if net_values else None,
        "profitFactor": profit_factor,
        "targetHitRate": exit_reasons.get("target", 0) / len(valid) if valid else None,
        "stopRate": exit_reasons.get("stop", 0) / len(valid) if valid else None,
        "meanCostDragR": fmean(cost_drags) if cost_drags else None,
        "sameBarAmbiguityRate": same_bar_count / len(valid) if valid else None,
        "largestSymbolShare": max(symbols.values(), default=0) / len(valid) if valid else None,
        "largestMonthShare": max(months.values(), default=0) / len(valid) if valid else None,
        "exitReasonCounts": dict(sorted(exit_reasons.items())),
        "earlyMeanNetR": early_mean,
        "recentMeanNetR": recent_mean,
        "factorDecayDeltaR": decay_delta,
        "factorDecayAvailable": len(early) >= 5 and len(recent) >= 5,
    }


def _failure_modes(metrics: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    checks = (
        ("negative_expectancy", metrics.get("meanNetR") is not None and metrics["meanNetR"] <= 0),
        ("profit_factor_below_demo_hurdle", metrics.get("profitFactor") is not None and metrics["profitFactor"] < 1.15),
        ("target_hit_rate_below_2r_breakeven", metrics.get("targetHitRate") is not None and metrics["targetHitRate"] < 1 / 3),
        ("entry_stop_concentration", metrics.get("stopRate") is not None and metrics["stopRate"] > 0.55),
        ("cost_drag_elevated", metrics.get("meanCostDragR") is not None and metrics["meanCostDragR"] > 0.08),
        ("factor_decay", metrics.get("factorDecayAvailable") and metrics.get("factorDecayDeltaR") is not None and metrics["factorDecayDeltaR"] < -0.20),
        ("symbol_concentration", metrics.get("largestSymbolShare") is not None and metrics["largestSymbolShare"] > 0.40),
        ("time_concentration", metrics.get("largestMonthShare") is not None and metrics["largestMonthShare"] > 0.35),
        ("same_bar_ambiguity", metrics.get("sameBarAmbiguityRate") is not None and metrics["sameBarAmbiguityRate"] > 0.05),
    )
    for code, triggered in checks:
        if triggered:
            failures.append({"code": code, "researchOnly": True})
    return failures


def build_failure_attribution(ingestion: EvidenceIngestionResult) -> dict[str, Any]:
    by_class: dict[str, Any] = {}
    all_formal: list[OutcomeLedgerRecord] = []
    for evidence_class in FORMAL_EVIDENCE_CLASSES:
        records = ingestion.acceptedByClass.get(evidence_class, [])
        all_formal.extend(records)
        metrics = _metric_summary(records)
        by_class[evidence_class] = {
            "metrics": metrics,
            "failureModes": _failure_modes(metrics),
        }
    combined = _metric_summary(all_formal)
    return {
        "schemaVersion": "offline_failure_attribution_v1",
        "byEvidenceClass": by_class,
        "combinedFormalEvidence": {
            "metrics": combined,
            "failureModes": _failure_modes(combined),
        },
        "quarantinedEvidenceIncluded": False,
    }


def build_research_triggers(
    ingestion: EvidenceIngestionResult,
    attribution: dict[str, Any],
    *,
    minimum_formal_outcomes: int = 30,
) -> list[dict[str, Any]]:
    if minimum_formal_outcomes <= 0:
        raise ValueError("minimum_formal_outcomes must be positive")
    triggers: list[dict[str, Any]] = []
    if ingestion.formalOutcomeCount < minimum_formal_outcomes:
        core = {
            "triggerType": "formal_evidence_gap",
            "formalOutcomeCount": ingestion.formalOutcomeCount,
            "required": minimum_formal_outcomes,
        }
        triggers.append(
            {
                "triggerId": stable_hash(core, prefix="offline_research_trigger"),
                **core,
                "priority": "blocking",
                "suggestedAction": "continue_formal_replay_forward_or_demo_collection",
                "allowsFactorGeneration": False,
                "researchOnly": True,
            }
        )
        return triggers
    action_by_failure = {
        "negative_expectancy": "generate_entry_and_regime_filter_challengers",
        "profit_factor_below_demo_hurdle": "generate_factor_and_exit_challengers",
        "target_hit_rate_below_2r_breakeven": "diagnose_entry_timing_for_fixed_2r",
        "entry_stop_concentration": "generate_entry_quality_challengers",
        "cost_drag_elevated": "tighten_liquidity_and_execution_filters",
        "factor_decay": "generate_recent_regime_robust_challengers",
        "symbol_concentration": "expand_point_in_time_universe_validation",
        "time_concentration": "expand_walk_forward_time_slices",
        "same_bar_ambiguity": "increase_path_resolution_without_optimistic_fill",
    }
    combined = attribution["combinedFormalEvidence"]
    for failure in combined["failureModes"]:
        code = failure["code"]
        core = {
            "triggerType": code,
            "formalOutcomeCount": ingestion.formalOutcomeCount,
        }
        triggers.append(
            {
                "triggerId": stable_hash(core, prefix="offline_research_trigger"),
                **core,
                "priority": "high" if code in {"negative_expectancy", "factor_decay"} else "normal",
                "suggestedAction": action_by_failure[code],
                "allowsFactorGeneration": code not in {"cost_drag_elevated", "same_bar_ambiguity"},
                "researchOnly": True,
            }
        )
    return triggers
