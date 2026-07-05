"""Strategy control tower and local paper router.

This module converts prior AlphaPilot research reports into a conservative
state-machine view. It emits local paper routing intents only. It never calls
exchange APIs, reads real accounts, creates orders, or auto trades.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import json


STRATEGY_STAGES = [
    "research_candidate",
    "local_paper_watch",
    "paper_trial",
    "dry_run_review",
    "rejected",
    "promoted",
]


@dataclass(frozen=True)
class ControlTowerPaths:
    v13_5_7_report: Path = Path("reports/v13_5_7_external_alpha_overlay_report.json")
    v13_5_8_report: Path = Path("reports/v13_5_8_adaptive_ml_factor_report.json")
    v13_5_3_ledger: Path = Path("reports/v13_5_3_local_paper_sandbox_ledger.json")
    v13_5_4_monitoring: Path = Path("reports/v13_5_4_local_paper_monitoring_report.json")


@dataclass
class StrategyState:
    strategy_id: str
    strategy_name: str
    source_report: str
    stage: str
    route_action: str
    priority: int
    candidate_pool_id: str | None = None
    reason: str = ""
    warnings: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    risk_gate: dict[str, Any] = field(default_factory=dict)
    evidence: dict[str, Any] = field(default_factory=dict)


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


def _find_pool(report: dict[str, Any], pool_id: str | None) -> dict[str, Any] | None:
    if not pool_id:
        return None
    for key in ("topAlphaOverlayPools", "approvedLocalPaperWatchPools", "topAdaptiveCandidates"):
        for item in report.get(key, []) or []:
            if item.get("poolId") == pool_id:
                return item
    return None


def _metrics_from_pool(pool: dict[str, Any] | None) -> dict[str, Any]:
    if not pool:
        return {}
    metrics = pool.get("selectedMetrics") or pool.get("metrics") or {}
    cost = pool.get("costAdjusted2R") or {}
    return {
        "tradeCount": metrics.get("tradeCount"),
        "winRatePct": metrics.get("winRatePct"),
        "rewardRiskRatio": metrics.get("rewardRiskRatio"),
        "profitFactor": metrics.get("profitFactor"),
        "totalReturnPct": metrics.get("totalReturnPct"),
        "maxDrawdownPct": metrics.get("maxDrawdownPct"),
        "observedToCostAdjusted2RCloseness": cost.get("observedToCostAdjusted2RCloseness"),
        "recentProfitFactor": (pool.get("recentHoldout") or {}).get("profitFactor"),
    }


def _paper_metrics_from_monitoring(monitoring: dict[str, Any]) -> dict[str, Any]:
    full = monitoring.get("fullMetrics") or {}
    freshness = monitoring.get("freshness") or {}
    decision = monitoring.get("decision") or {}
    return {
        "tradeCount": full.get("tradeCount"),
        "winRatePct": full.get("winRatePct"),
        "rewardRiskRatio": full.get("rewardRiskRatio"),
        "profitFactor": full.get("profitFactor"),
        "totalReturnPct": full.get("totalReturnPct"),
        "maxDrawdownPct": full.get("maxDrawdownPct"),
        "latestSignal": freshness.get("latestSignal"),
        "latestClosedFill": freshness.get("latestClosedFill"),
        "signalFresh": freshness.get("signalFresh"),
        "closedFillFresh": freshness.get("closedFillFresh"),
        "monitoringHealth": decision.get("monitoringHealth"),
    }


def _risk_gate_for_local_paper(
    *,
    strategy_id: str,
    pool_metrics: dict[str, Any],
    paper_metrics: dict[str, Any],
    monitoring_decision: dict[str, Any],
) -> dict[str, Any]:
    warnings = list(monitoring_decision.get("warningReasons") or [])
    blockers = list(monitoring_decision.get("failReasons") or [])

    max_drawdown = round_or_none(pool_metrics.get("maxDrawdownPct"))
    if max_drawdown is not None and max_drawdown > 45:
        blockers.append("research_pool_drawdown_above_45")

    paper_drawdown = round_or_none(paper_metrics.get("maxDrawdownPct"))
    if paper_drawdown is not None and paper_drawdown > 20:
        warnings.append("paper_drawdown_above_20")

    if not paper_metrics.get("closedFillFresh"):
        warnings.append("paper_closed_fill_not_fresh")

    passed = not blockers
    dry_run_review_ready = bool(monitoring_decision.get("exchangeDryRunReviewReady")) and passed
    return {
        "strategyId": strategy_id,
        "passedForLocalPaperWatch": passed,
        "exchangeDryRunReviewReady": dry_run_review_ready,
        "liveTradingApproved": False,
        "warnings": sorted(set(warnings)),
        "blockers": sorted(set(blockers)),
        "checks": {
            "localPaperOnly": True,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "autoTrading": False,
        },
    }


def build_strategy_control_tower(paths: ControlTowerPaths | None = None) -> dict[str, Any]:
    paths = paths or ControlTowerPaths()
    v57 = read_json(paths.v13_5_7_report)
    v58 = read_json(paths.v13_5_8_report)
    ledger = read_json(paths.v13_5_3_ledger)
    monitoring = read_json(paths.v13_5_4_monitoring)

    states: list[StrategyState] = []
    router_intents: list[dict[str, Any]] = []

    v57_decision = v57.get("decision") or {}
    v57_pool_id = v57_decision.get("localPaperWatchPoolId")
    v57_pool = _find_pool(v57, v57_pool_id)
    v57_metrics = _metrics_from_pool(v57_pool)
    paper_metrics = _paper_metrics_from_monitoring(monitoring)
    monitoring_decision = monitoring.get("decision") or {}
    v57_risk_gate = _risk_gate_for_local_paper(
        strategy_id="v13_5_7_alpha_overlay_fixed_watch",
        pool_metrics=v57_metrics,
        paper_metrics=paper_metrics,
        monitoring_decision=monitoring_decision,
    )
    v57_route = "continue_local_paper_watch" if v57_decision.get("localPaperWatchApproved") else "do_not_route"
    if v57_risk_gate["blockers"]:
        v57_route = "pause_local_paper_watch"
    states.append(
        StrategyState(
            strategy_id="v13_5_7_alpha_overlay_fixed_watch",
            strategy_name="V13.5.7 Alpha101-style 4h overlay watch",
            source_report=str(paths.v13_5_7_report),
            stage="local_paper_watch" if v57_route == "continue_local_paper_watch" else "rejected",
            route_action=v57_route,
            priority=1,
            candidate_pool_id=v57_pool_id,
            reason=v57_decision.get("reason") or "",
            warnings=v57_risk_gate["warnings"],
            blockers=v57_risk_gate["blockers"],
            metrics={**v57_metrics, "paperMonitoring": paper_metrics},
            risk_gate=v57_risk_gate,
            evidence={
                "targetRMultipleUnchanged": v57_decision.get("targetRMultipleUnchanged"),
                "sourceVersion": v57.get("version"),
                "monitoringVersion": monitoring.get("version"),
            },
        )
    )
    router_intents.append(
        {
            "intentId": "router-v13-5-9-0001",
            "strategyId": "v13_5_7_alpha_overlay_fixed_watch",
            "candidatePoolId": v57_pool_id,
            "intentType": "local_paper_route",
            "routeAction": v57_route,
            "isOrder": False,
            "requiresHumanReviewBeforeDryRun": True,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "riskGate": v57_risk_gate,
        }
    )

    v58_decision = v58.get("decision") or {}
    top_adaptive = (v58.get("topAdaptiveCandidates") or [{}])[0]
    adaptive_metrics = _metrics_from_pool(top_adaptive)
    states.append(
        StrategyState(
            strategy_id="v13_5_8_adaptive_ml_observer",
            strategy_name="V13.5.8 adaptive ML observer",
            source_report=str(paths.v13_5_8_report),
            stage="research_candidate",
            route_action="observe_only",
            priority=2,
            candidate_pool_id=top_adaptive.get("poolId"),
            reason=v58_decision.get("reason") or "adaptive_observer_only",
            warnings=["adaptive_ml_no_local_paper_approval"],
            blockers=[],
            metrics=adaptive_metrics,
            risk_gate={
                "passedForLocalPaperWatch": False,
                "exchangeDryRunReviewReady": False,
                "liveTradingApproved": False,
                "checks": {
                    "localPaperOnly": True,
                    "usesApiKey": False,
                    "tradeApiUsed": False,
                    "withdrawApiUsed": False,
                    "readsRealAccount": False,
                    "readsRealPositions": False,
                    "createsOrders": False,
                    "autoTrading": False,
                },
            },
            evidence={
                "adaptiveMLComputed": v58_decision.get("adaptiveMLComputed"),
                "targetRMultipleUnchanged": v58_decision.get("targetRMultipleUnchanged"),
                "localPaperWatchApproved": v58_decision.get("localPaperWatchApproved"),
                "sourceVersion": v58.get("version"),
            },
        )
    )
    router_intents.append(
        {
            "intentId": "router-v13-5-9-0002",
            "strategyId": "v13_5_8_adaptive_ml_observer",
            "candidatePoolId": top_adaptive.get("poolId"),
            "intentType": "research_observer",
            "routeAction": "observe_only",
            "isOrder": False,
            "requiresHumanReviewBeforeDryRun": True,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
            "riskGate": states[-1].risk_gate,
        }
    )

    ledger_metrics = ledger.get("metrics") or {}
    active_states = [state for state in states if state.stage == "local_paper_watch"]
    decision = {
        "controlTowerComputed": True,
        "activeLocalPaperStrategies": len(active_states),
        "primaryActiveStrategyId": active_states[0].strategy_id if active_states else None,
        "continueLocalPaperMonitoring": any(
            state.route_action == "continue_local_paper_watch" for state in states
        ),
        "paperTrialApproved": False,
        "exchangeDryRunReviewReady": False,
        "exchangeDryRunApproved": False,
        "liveTradingApproved": False,
        "reason": "continue_local_paper_watch_only"
        if active_states
        else "no_active_local_paper_strategy",
    }

    references = [
        {
            "name": "yydhYYDH/alpha101",
            "url": "https://github.com/yydhYYDH/alpha101",
            "license": "unknown_from_raw_license_fetch",
            "localReference": "docs/future-factor-research-reference-alpha101.md",
            "usedFor": "factor panel and expression-search design reference",
            "copiedCodeOrLongText": False,
        },
        {
            "name": "ryckli/CryptoAgentPro.beta",
            "url": "https://github.com/ryckli/CryptoAgentPro.beta",
            "license": "MIT",
            "localReference": "docs/future-live-trading-reference-cryptoagentpro-beta.md",
            "usedFor": "future execution-boundary and risk-gateway design reference",
            "copiedCodeOrLongText": False,
        },
    ]

    return {
        "version": "V13.5.9",
        "reportId": "v13_5_9_strategy_control_tower_report",
        "generatedAt": utc_now(),
        "status": "completed",
        "objective": (
            "Coordinate existing research candidates into local-paper-only strategy states "
            "and route intents without adding execution authority."
        ),
        "decision": decision,
        "strategyStages": STRATEGY_STAGES,
        "strategyStates": [asdict(state) for state in states],
        "localPaperRouterIntents": router_intents,
        "ledgerSummary": {
            "ledgerPath": str(paths.v13_5_3_ledger),
            "tradeCount": ledger_metrics.get("tradeCount"),
            "winRatePct": ledger_metrics.get("winRatePct"),
            "rewardRiskRatio": ledger_metrics.get("rewardRiskRatio"),
            "profitFactor": ledger_metrics.get("profitFactor"),
            "totalReturnPct": ledger_metrics.get("totalReturnPct"),
            "maxDrawdownPct": ledger_metrics.get("maxDrawdownPct"),
        },
        "monitoringSummary": {
            "monitoringPath": str(paths.v13_5_4_monitoring),
            "decision": monitoring_decision,
            "paperMetrics": paper_metrics,
        },
        "externalReferences": references,
        "safetyBoundary": {
            "localPaperOnly": True,
            "usesPublicLocalDataOnly": True,
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
        "recommendations": [
            "Keep V13.5.7 as the only active local paper watch strategy.",
            "Keep V13.5.8 adaptive ML as observer-only until it passes independent validation.",
            "Do not move to exchange Dry-run because monitoring still has freshness and decay warnings.",
            "Use future paper/manual outcomes as strategy evolution samples; do not fabricate actual trade outcomes.",
        ],
    }
