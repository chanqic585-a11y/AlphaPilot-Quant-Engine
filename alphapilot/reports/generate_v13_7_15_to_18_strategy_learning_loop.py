from __future__ import annotations

import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = ROOT / "reports"
DOCS_DIR = ROOT / "docs"
SAFETY_BOUNDARY = {
    "realTradingEnabled": False,
    "exchangeDryRunApproved": False,
    "liveTradingApproved": False,
    "tradeApiEnabled": False,
    "withdrawApiEnabled": False,
    "apiKeyStorage": False,
    "realAccountReads": False,
    "realPositionReads": False,
    "orderCreation": False,
    "autoTrading": False,
}


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _subject_kind(item: dict[str, Any]) -> str:
    text = " ".join([
        str(item.get("subjectId") or ""),
        str(item.get("title") or ""),
        str(item.get("sourceVersion") or ""),
    ]).lower()
    if "factor" in text or "因子" in text:
        return "factor_research"
    if "ml" in text or "machine" in text:
        return "ml_research"
    if "derivatives" in text or "1h" in text or "4h" in text:
        return "derivatives_strategy_research"
    return "strategy_research"


def _flatten_notes(item: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    for finding in item.get("reviewerFindings", []):
        if not isinstance(finding, dict):
            continue
        for note in finding.get("notes", []):
            if isinstance(note, str):
                notes.append(note)
    committee = item.get("committee") if isinstance(item.get("committee"), dict) else {}
    if committee.get("nextAction"):
        notes.append(str(committee["nextAction"]))
    return notes


def build_v13_7_15_learning_loop() -> dict[str, Any]:
    review = _read_json(REPORTS_DIR / "v13_7_14_multi_agent_strategy_review_report.json")
    reviews = [row for row in review.get("reviews", []) if isinstance(row, dict)]
    status_counter: Counter[str] = Counter()
    verdict_counter: Counter[str] = Counter()
    kind_counter: Counter[str] = Counter()
    learning_ledger: list[dict[str, Any]] = []
    strategy_graveyard: list[dict[str, Any]] = []
    research_watchlist: list[dict[str, Any]] = []
    factor_memory: list[dict[str, Any]] = []

    for item in reviews:
        committee = item.get("committee") if isinstance(item.get("committee"), dict) else {}
        status = str(committee.get("researchStatus") or "unknown")
        kind = _subject_kind(item)
        status_counter[status] += 1
        kind_counter[kind] += 1
        findings = [f for f in item.get("reviewerFindings", []) if isinstance(f, dict)]
        verdicts = [str(f.get("verdict") or "unknown") for f in findings]
        verdict_counter.update(verdicts)
        notes = _flatten_notes(item)
        learning = {
            "learningId": f"learn_{item.get('subjectId')}",
            "subjectId": item.get("subjectId"),
            "title": item.get("title"),
            "kind": kind,
            "researchStatus": status,
            "committeeScore": committee.get("committeeScore"),
            "dominantReviewerVerdicts": verdicts,
            "whatWeLearned": notes[:5],
            "doNotRepeat": [
                "Do not promote a report-only factor object as a strategy.",
                "Do not lower the 2R requirement to rescue a weak candidate.",
                "Do not move any failed sample into paper observation without new evidence.",
            ],
            "reuseAs": "factor_input" if kind == "factor_research" else "negative_evidence",
            "nextResearchQuestion": committee.get("nextAction"),
        }
        learning_ledger.append(learning)
        if status == "reject_for_now":
            strategy_graveyard.append({
                "subjectId": item.get("subjectId"),
                "title": item.get("title"),
                "reason": committee.get("nextAction"),
                "preserveEvidence": item.get("sourceFiles") or [],
                "resurrectionRule": "Only revisit after a new rule, new data split, and explicit stress-test plan exist.",
            })
        else:
            research_watchlist.append({
                "subjectId": item.get("subjectId"),
                "title": item.get("title"),
                "kind": kind,
                "nextAction": committee.get("nextAction"),
                "usableEvidence": item.get("sourceFiles") or [],
            })
        if kind == "factor_research":
            factor_memory.append({
                "subjectId": item.get("subjectId"),
                "title": item.get("title"),
                "usableAs": "feature_or_filter_input_only",
                "notUsableAs": "standalone_strategy",
            })

    return {
        "reportId": "v13_7_15_strategy_learning_loop",
        "version": "V13.7.15",
        "status": "completed",
        "generatedAt": _now(),
        "source": "alphapilot_strategy_learning_loop_v13_7_15",
        "objective": "Turn failed and inconclusive strategy research into reusable learning records.",
        "inputReports": [
            "reports/v13_7_14_multi_agent_strategy_review_report.json",
            "reports/v13_7_13_backtest_task_completion_report.json",
        ],
        "summary": {
            "reviewedSubjectCount": len(reviews),
            "learningItemCount": len(learning_ledger),
            "graveyardCount": len(strategy_graveyard),
            "researchWatchlistCount": len(research_watchlist),
            "factorMemoryCount": len(factor_memory),
            "statusCounts": dict(status_counter),
            "kindCounts": dict(kind_counter),
            "topReviewerVerdicts": dict(verdict_counter.most_common(12)),
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "nextStep": "Generate refactor candidates from the learning ledger, not from raw optimism.",
        },
        "learningLedger": learning_ledger,
        "strategyGraveyard": strategy_graveyard,
        "researchWatchlist": research_watchlist,
        "factorMemory": factor_memory,
        "safetyBoundary": SAFETY_BOUNDARY,
    }


def build_v13_7_16_refactor_candidates(learning: dict[str, Any]) -> dict[str, Any]:
    watchlist = [row for row in learning.get("researchWatchlist", []) if isinstance(row, dict)]
    graveyard = [row for row in learning.get("strategyGraveyard", []) if isinstance(row, dict)]
    candidates = [
        {
            "candidateId": "factor_confluence_low_frequency_filter_v0_1",
            "title": "因子共振低频过滤候选",
            "sourceLearningIds": [
                row.get("subjectId") for row in watchlist if row.get("kind") == "factor_research"
            ],
            "hypothesis": "把因子面板从入场信号降级为低频过滤器，只在趋势、动量和波动条件共振时允许策略继续研究。",
            "proposedChanges": [
                "Use factors as filters, not direct entries.",
                "Require 4h/1d context before testing lower-timeframe signals.",
                "Keep target reward multiple at 2R.",
            ],
            "blockedBy": ["no explicit entry/exit rule yet", "no completed stress-test yet"],
            "specReadyForResearchBacktest": True,
            "paperObservationAllowed": False,
            "priority": 91,
        },
        {
            "candidateId": "ml_loss_avoidance_overlay_v0_1",
            "title": "ML 亏损规避过滤候选",
            "sourceLearningIds": [
                row.get("subjectId") for row in graveyard if "ml" in str(row.get("title", "")).lower()
            ],
            "hypothesis": "把失败的 ML 方向从入场模型改造成亏损规避过滤器，只决定什么时候不研究某个信号。",
            "proposedChanges": [
                "ML output cannot create signals.",
                "Use ML only to block high-risk market states.",
                "Measure avoided loss against missed opportunity.",
            ],
            "blockedBy": ["needs leakage audit", "needs walk-forward no-trade comparison"],
            "specReadyForResearchBacktest": True,
            "paperObservationAllowed": False,
            "priority": 86,
        },
        {
            "candidateId": "regime_aware_low_frequency_rebuild_v0_1",
            "title": "市场状态低频重构候选",
            "sourceLearningIds": [row.get("subjectId") for row in graveyard],
            "hypothesis": "把失败的一小时/四小时候选重构为更低频、更少交易、带 BTC 状态过滤的策略族。",
            "proposedChanges": [
                "Use BTC regime labels as the first gate.",
                "Prefer 4h/1d setups over dense 1h entries.",
                "Reject trades during BTC急跌, high volatility expansion, or liquidity deterioration.",
            ],
            "blockedBy": ["needs deterministic rule implementation", "needs 2020-2026 replay"],
            "specReadyForResearchBacktest": True,
            "paperObservationAllowed": False,
            "priority": 88,
        },
        {
            "candidateId": "strategy_failure_memory_index_v0_1",
            "title": "策略失败记忆索引候选",
            "sourceLearningIds": [row.get("learningId") for row in learning.get("learningLedger", [])],
            "hypothesis": "把失败原因做成索引，后续每次生成新策略前先检查是否重复踩坑。",
            "proposedChanges": [
                "Index failure modes by factor, timeframe, market regime, and risk failure.",
                "Block duplicate hypotheses before expensive backtests.",
            ],
            "blockedBy": ["requires more failure cases for richer taxonomy"],
            "specReadyForResearchBacktest": False,
            "paperObservationAllowed": False,
            "priority": 75,
        },
    ]
    return {
        "reportId": "v13_7_16_strategy_refactor_candidates",
        "version": "V13.7.16",
        "status": "completed",
        "generatedAt": _now(),
        "source": "alphapilot_strategy_refactor_candidates_v13_7_16",
        "objective": "Convert strategy failures and research-only artifacts into next-generation refactor candidates.",
        "inputReports": ["reports/v13_7_15_strategy_learning_loop_report.json"],
        "summary": {
            "candidateCount": len(candidates),
            "researchBacktestSpecReadyCount": sum(1 for item in candidates if item["specReadyForResearchBacktest"]),
            "paperObservationAllowedCount": 0,
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "topCandidateId": candidates[0]["candidateId"],
            "nextStep": "Turn top refactor candidates into explicit low-frequency/regime-filtered experiment specs.",
        },
        "refactorCandidates": candidates,
        "safetyBoundary": SAFETY_BOUNDARY,
    }


def build_v13_7_17_experiment_specs(refactor: dict[str, Any]) -> dict[str, Any]:
    candidates = [row for row in refactor.get("refactorCandidates", []) if isinstance(row, dict)]
    specs: list[dict[str, Any]] = []
    for row in candidates:
        cid = str(row.get("candidateId") or "")
        if not row.get("specReadyForResearchBacktest"):
            continue
        if "factor_confluence" in cid:
            specs.append({
                "experimentId": "lf_factor_confluence_regime_filter_4h_v0_1",
                "sourceCandidateId": cid,
                "timeframes": ["4h", "1d"],
                "universe": "Top liquid crypto per available public OHLCV; start with BTC/ETH/SOL and expand only after smoke replay.",
                "entryResearchConditions": [
                    "BTC regime is not crash or high-volatility breakdown.",
                    "Asset close is above long moving-average context.",
                    "RSI14 is between 45 and 68, avoiding overextended entries.",
                    "Volume ratio confirms participation but is not a standalone trigger.",
                    "At least two factor families agree: trend, momentum, volatility compression, liquidity.",
                ],
                "exitResearchModel": ["fixed 2R target", "volatility-aware invalidation", "time stop for stale setups"],
                "requiredBacktests": ["2020-2026", "walk-forward split", "fee/slippage stress", "regime breakdown"],
                "passGate": {
                    "minTradeCount": 80,
                    "minRewardRiskRatio": 2.0,
                    "minProfitFactor": 1.15,
                    "maxDrawdownPct": 25,
                    "mustBeatNoTrade": True,
                    "mustBeatEqualWeight": True,
                },
            })
        elif "ml_loss_avoidance" in cid:
            specs.append({
                "experimentId": "ml_loss_avoidance_filter_overlay_v0_1",
                "sourceCandidateId": cid,
                "timeframes": ["1h", "4h"],
                "universe": "Use same symbols as candidate strategy replay; no new market exposure from ML alone.",
                "entryResearchConditions": [
                    "ML cannot open a trade or create a signal.",
                    "ML may only veto signals generated by deterministic rules.",
                    "Veto must reduce drawdown or consecutive-loss clusters without destroying 2R structure.",
                ],
                "exitResearchModel": ["inherits deterministic strategy exit", "no ML-managed exit"],
                "requiredBacktests": ["baseline rule vs rule+ML-veto", "leakage audit", "walk-forward folds"],
                "passGate": {
                    "minAvoidedLossImprovementPct": 10,
                    "maxMissedProfitPenaltyPct": 15,
                    "minRewardRiskRatio": 2.0,
                    "mustImproveMaxDrawdown": True,
                },
            })
        elif "regime_aware" in cid:
            specs.append({
                "experimentId": "regime_aware_low_frequency_rebuild_4h_1d_v0_1",
                "sourceCandidateId": cid,
                "timeframes": ["4h", "1d"],
                "universe": "BTC, ETH, SOL smoke first; expand to Top 50/100 only after deterministic replay passes.",
                "entryResearchConditions": [
                    "Trade research only when BTC regime is trend-up, recovery, or low-volatility neutral.",
                    "Block all entries during BTC急跌, broad-market liquidity deterioration, and high-volatility breakdown.",
                    "Require pullback or consolidation after trend confirmation; avoid chasing vertical moves.",
                ],
                "exitResearchModel": ["2R target unchanged", "ATR-based invalidation", "cooldown after loss clusters"],
                "requiredBacktests": ["2020-2026", "bull/bear/sideways split", "exchange comparison if public data available"],
                "passGate": {
                    "minTradeCount": 60,
                    "minRewardRiskRatio": 2.0,
                    "minProfitFactor": 1.2,
                    "maxDrawdownPct": 22,
                    "maxConsecutiveLosses": 6,
                },
            })
    return {
        "reportId": "v13_7_17_regime_filtered_experiment_specs",
        "version": "V13.7.17",
        "status": "completed",
        "generatedAt": _now(),
        "source": "alphapilot_regime_filtered_experiment_specs_v13_7_17",
        "objective": "Define explicit research experiment specs before writing new strategy code.",
        "inputReports": ["reports/v13_7_16_strategy_refactor_candidates_report.json"],
        "summary": {
            "experimentSpecCount": len(specs),
            "readyForBacktestImplementationCount": len(specs),
            "paperObservationAllowedCount": 0,
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "nextStep": "Implement and backtest one experiment at a time; do not move to paper observation from specs alone.",
        },
        "experimentSpecs": specs,
        "safetyBoundary": SAFETY_BOUNDARY,
    }


def build_v13_7_18_paper_re_review(specs_report: dict[str, Any]) -> dict[str, Any]:
    specs = [row for row in specs_report.get("experimentSpecs", []) if isinstance(row, dict)]
    rows: list[dict[str, Any]] = []
    for spec in specs:
        rows.append({
            "experimentId": spec.get("experimentId"),
            "sourceCandidateId": spec.get("sourceCandidateId"),
            "paperObservationStatus": "not_approved",
            "readinessScore": 35,
            "missingEvidence": [
                "No completed deterministic strategy implementation for this experiment.",
                "No completed 2020-2026 replay for this exact rule set.",
                "No walk-forward validation for this exact rule set.",
                "No fee/slippage/latency stress report for this exact rule set.",
                "No proof that 2R target survives after costs.",
            ],
            "allowedNextAction": "research_backtest_only",
            "blockedActions": [
                "paper_observation",
                "exchange_dry_run",
                "live_trading",
                "auto_trading",
            ],
        })
    return {
        "reportId": "v13_7_18_paper_observation_rereview",
        "version": "V13.7.18",
        "status": "completed",
        "generatedAt": _now(),
        "source": "alphapilot_paper_observation_rereview_v13_7_18",
        "objective": "Re-review whether newly generated research specs can enter paper observation.",
        "inputReports": ["reports/v13_7_17_regime_filtered_experiment_specs_report.json"],
        "summary": {
            "reviewedExperimentCount": len(rows),
            "paperObservationApprovedCount": 0,
            "researchBacktestOnlyCount": len(rows),
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "nextExecutableResearchStep": (
                "Implement a deterministic backtest for lf_factor_confluence_regime_filter_4h_v0_1 first, "
                "then rerun paper observation review only after evidence exists."
            ),
        },
        "paperObservationReviews": rows,
        "safetyBoundary": SAFETY_BOUNDARY,
    }


def _summary_md(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        f"# {report.get('version')} {report.get('reportId')}",
        "",
        report.get("objective", ""),
        "",
        "## Summary",
        "",
    ]
    for key, value in summary.items():
        lines.append(f"- {key}: {value}")
    lines.extend([
        "",
        "## Safety Boundary",
        "",
        "- No Trade API.",
        "- No Withdraw API.",
        "- No exchange API key storage.",
        "- No real account or position reads.",
        "- No order creation.",
        "- No exchange Dry-run execution.",
        "- No live or automatic trading.",
        "",
    ])
    return "\n".join(lines)


def _write_report(report: dict[str, Any], doc_name: str) -> None:
    report_id = str(report["reportId"])
    _write_json(REPORTS_DIR / f"{report_id}_report.json", report)
    summary = _summary_md(report)
    _write_text(REPORTS_DIR / f"{report_id}_summary.md", summary)
    _write_text(DOCS_DIR / doc_name, summary)


def main() -> None:
    v15 = build_v13_7_15_learning_loop()
    _write_report(v15, "V13.7.15-strategy-learning-loop.md")
    v16 = build_v13_7_16_refactor_candidates(v15)
    _write_report(v16, "V13.7.16-strategy-refactor-candidates.md")
    v17 = build_v13_7_17_experiment_specs(v16)
    _write_report(v17, "V13.7.17-regime-filtered-experiment-specs.md")
    v18 = build_v13_7_18_paper_re_review(v17)
    _write_report(v18, "V13.7.18-paper-observation-rereview.md")
    print(json.dumps({
        "status": "completed",
        "versions": ["V13.7.15", "V13.7.16", "V13.7.17", "V13.7.18"],
        "learningItems": v15["summary"]["learningItemCount"],
        "refactorCandidates": v16["summary"]["candidateCount"],
        "experimentSpecs": v17["summary"]["experimentSpecCount"],
        "paperObservationApprovedCount": v18["summary"]["paperObservationApprovedCount"],
        "dryRunApproved": False,
        "liveTradingApproved": False,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
