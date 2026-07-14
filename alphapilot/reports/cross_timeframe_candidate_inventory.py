"""Pure builders for the auditable five-timeframe research inventory."""

from __future__ import annotations

from typing import Any, Mapping, Sequence


TIMEFRAMES = ("5m", "15m", "1h", "4h", "1d")
SELECTION_TIERS = ("research_eligible", "shadow_only", "rejected")


def classify_event_prescreen_candidate(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    target_r = float(result.get("targetR") or 0)
    if target_r < 2.0:
        raise ValueError("cross_timeframe_candidate_target_r_below_two")
    segments = dict(result.get("segmentMetrics") or {})
    if not segments:
        raise ValueError("cross_timeframe_candidate_segments_missing")
    profit_factor = min(
        float(values.get("profitFactor") or 0) for values in segments.values()
    )
    expectancy_r = min(
        float(values.get("expectancyR") or 0) for values in segments.values()
    )
    trade_count = sum(
        int(values.get("tradeCount") or 0) for values in segments.values()
    )
    if bool(result.get("eligible")):
        tier = "research_eligible"
    elif profit_factor > 1.0 and expectancy_r > 0:
        tier = "shadow_only"
    else:
        tier = "rejected"
    return {
        "candidateId": str(result["candidateKey"]),
        "displayName": str(result["displayName"]),
        "timeframe": str(result["timeframe"]),
        "family": str(result.get("signalFamily") or "event_window"),
        "direction": str(result.get("direction") or "unknown"),
        "targetR": target_r,
        "selectionTier": tier,
        "failedSelectionChecks": list(result.get("rejectionReasons") or []),
        "metrics": {
            "tradeCount": trade_count,
            "profitFactor": round(profit_factor, 8),
            "expectancyR": round(expectancy_r, 8),
        },
        "segmentMetrics": segments,
        "directCandidateBacktestCompleted": True,
        "executableWorkflowAvailable": True,
        "lockedOrHoldoutUsedForSelection": False,
    }


def normalize_long_horizon_candidate(
    result: Mapping[str, Any],
) -> dict[str, Any]:
    """Mark report-only low-frequency rows and normalize comparable metrics."""

    row = dict(result)
    metrics = dict(row.get("metrics") or {})
    trade_count = int(metrics.get("tradeCount") or 0)
    if "expectancyR" not in metrics and trade_count > 0:
        metrics["expectancyR"] = round(
            float(metrics.get("totalNetR") or 0) / trade_count,
            8,
        )
    row["metrics"] = metrics
    row["executableWorkflowAvailable"] = False
    row["workflowBlocker"] = "low_frequency_formal_workflow_adapter_pending"
    return row


def build_cross_timeframe_candidate_inventory(
    candidates: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    rows = [dict(item) for item in candidates]
    identifiers = [str(item.get("candidateId") or "") for item in rows]
    if not all(identifiers) or len(set(identifiers)) != len(identifiers):
        raise ValueError("cross_timeframe_candidate_identity_invalid")
    for item in rows:
        if float(item.get("targetR") or 0) < 2.0:
            raise ValueError("cross_timeframe_candidate_target_r_below_two")
        if str(item.get("selectionTier")) not in SELECTION_TIERS:
            raise ValueError("cross_timeframe_candidate_tier_invalid")
    packs = {
        timeframe: [item for item in rows if item.get("timeframe") == timeframe]
        for timeframe in TIMEFRAMES
    }
    incomplete = {
        timeframe: len(items)
        for timeframe, items in packs.items()
        if len(items) != 5
    }
    if incomplete:
        raise ValueError(f"cross_timeframe_candidate_pack_incomplete:{incomplete}")
    tier_counts = {
        tier: sum(item["selectionTier"] == tier for item in rows)
        for tier in SELECTION_TIERS
    }
    return {
        "schemaVersion": "cross_timeframe_candidate_inventory_v1",
        "status": "completed",
        "objective": "Screen five auditable candidates per timeframe without forcing promotion.",
        "targetR": 2.0,
        "selectionBoundary": "development_temporal_validation_and_symbol_holdback_only",
        "lockedOrHoldoutUsedForSelection": False,
        "candidatePacks": packs,
        "summary": {
            "candidateCount": len(rows),
            "candidateCountByTimeframe": {
                timeframe: len(items) for timeframe, items in packs.items()
            },
            "researchEligibleCount": tier_counts["research_eligible"],
            "executableResearchEligibleCount": sum(
                item["selectionTier"] == "research_eligible"
                and bool(item.get("executableWorkflowAvailable"))
                for item in rows
            ),
            "shadowOnlyCount": tier_counts["shadow_only"],
            "rejectedCount": tier_counts["rejected"],
            "researchEligibleByTimeframe": {
                timeframe: sum(
                    item["selectionTier"] == "research_eligible" for item in items
                )
                for timeframe, items in packs.items()
            },
        },
        "safetyBoundary": {
            "researchOnly": True,
            "executionEnabled": False,
            "demoReleaseCreated": False,
            "liveReleaseCreated": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyStored": False,
        },
    }
