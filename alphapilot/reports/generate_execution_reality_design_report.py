"""Generate V13.4.11 execution reality and liquidity gate design report.

This generator writes design artifacts only. It does not download data, run
backtests, enter Dry-run, call exchange APIs, read accounts, create orders, or
auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.execution_reality.liquidity_gate import LiquidityGateInput, evaluate_liquidity_gate
from alphapilot.execution_reality.live_feasibility_score import LiveFeasibilityInput, calculate_live_feasibility_score
from alphapilot.execution_reality.order_impact import OrderImpactInput, estimate_order_impact
from alphapilot.execution_reality.slippage_model import DEFAULT_SLIPPAGE_SCENARIOS, apply_slippage_stress
from alphapilot.reports.execution_reality_schema import ExecutionRealityDesignReport

DEFAULT_REDESIGN_REVIEW = Path("reports/v13_4_10_trend_pullback_redesign_review.json")
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_11_execution_reality_design_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_11_execution_reality_summary.md")

REPORT_ID = "v13_4_11_execution_reality_design"
REPORT_VERSION = "V13.4.11"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, warnings: list[str]) -> dict[str, Any]:
    if not path.exists():
        warnings.append(f"Missing input report: {path}")
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        warnings.append(f"Unable to parse input report {path}: {exc}")
        return {}


def _expanded_metrics(redesign_review: dict[str, Any]) -> dict[str, Any]:
    smoke = redesign_review.get("smokeVsExpanded", {})
    return smoke.get("expandedRaw", {}) if isinstance(smoke, dict) else {}


def _adjusted_metrics(redesign_review: dict[str, Any]) -> dict[str, Any]:
    smoke = redesign_review.get("smokeVsExpanded", {})
    return smoke.get("expandedSlippageAdjusted", {}) if isinstance(smoke, dict) else {}


def _build_modules() -> list[dict[str, Any]]:
    return [
        {
            "module": "liquidity_gate",
            "path": "alphapilot/execution_reality/liquidity_gate.py",
            "purpose": "Reject or flag signals with insufficient public liquidity context.",
            "executionCapability": False,
        },
        {
            "module": "slippage_model",
            "path": "alphapilot/execution_reality/slippage_model.py",
            "purpose": "Apply report-layer slippage stress scenarios.",
            "executionCapability": False,
        },
        {
            "module": "order_impact",
            "path": "alphapilot/execution_reality/order_impact.py",
            "purpose": "Estimate theoretical order impact from public depth or volume approximations.",
            "executionCapability": False,
        },
        {
            "module": "shadow_trading_schema",
            "path": "alphapilot/execution_reality/shadow_trading_schema.py",
            "purpose": "Define shadow signal, snapshot, and outcome structures without starting execution.",
            "executionCapability": False,
        },
        {
            "module": "live_feasibility_score",
            "path": "alphapilot/execution_reality/live_feasibility_score.py",
            "purpose": "Score readiness for research, shadow trading, Dry-run candidate review, or controlled live design.",
            "executionCapability": False,
        },
    ]


def _build_liquidity_gate_section() -> dict[str, Any]:
    sample = LiquidityGateInput(
        symbol="BTC/USDT:USDT",
        timestamp="unavailable",
        marketType="swap",
        positionNotional=1000.0,
        lastPrice=50000.0,
    )
    result = evaluate_liquidity_gate(sample)
    return {
        "inputs": [
            "symbol",
            "timestamp",
            "marketType",
            "positionNotional",
            "lastPrice",
            "quoteVolume24h",
            "quoteVolume1h",
            "bidAskSpreadPct",
            "orderbookDepthTop5",
            "orderbookDepthTop10",
            "maxPositionToVolumePct",
            "maxPositionToDepthPct",
        ],
        "defaultRules": [
            "missing quoteVolume1h prevents approval",
            "positionNotional greater than quoteVolume1h * 0.001 is rejected or needs review",
            "bidAskSpreadPct greater than 0.0008 is rejected or needs review",
            "positionNotional greater than top5Depth * 0.10 is rejected",
            "missing depth and 1h volume returns insufficient_liquidity_data",
        ],
        "sampleMissingDataResult": result.to_dict(),
        "publicDataOnly": True,
        "createsOrders": False,
    }


def _build_slippage_section(redesign_review: dict[str, Any]) -> dict[str, Any]:
    raw = _expanded_metrics(redesign_review)
    raw_return = float(raw.get("totalReturnPct") or 0.0)
    raw_pf = raw.get("profitFactor")
    trade_count = int(raw.get("tradeCount") or 0)
    scenario_rows = [
        apply_slippage_stress(
            raw_return_pct=raw_return,
            raw_profit_factor=float(raw_pf) if raw_pf != "unavailable" and raw_pf is not None else None,
            trade_count=trade_count,
            scenario=scenario,
        ).to_dict()
        for scenario in DEFAULT_SLIPPAGE_SCENARIOS
    ]
    return {
        "scenarioRates": [scenario.to_dict() for scenario in DEFAULT_SLIPPAGE_SCENARIOS],
        "sampleStressRows": scenario_rows,
        "modelBoundary": "report-layer post-processing, not Freqtrade native matching",
        "createsOrders": False,
    }


def _build_order_impact_section() -> dict[str, Any]:
    no_depth = estimate_order_impact(OrderImpactInput(positionNotional=1000.0)).to_dict()
    volume_based = estimate_order_impact(
        OrderImpactInput(
            positionNotional=1000.0,
            bidAskSpreadPct=0.0004,
            quoteVolume1h=2_000_000.0,
        )
    ).to_dict()
    return {
        "inputs": [
            "positionNotional",
            "lastPrice",
            "bidAskSpreadPct",
            "orderbookDepth",
            "quoteVolume1h",
            "quoteVolume24h",
        ],
        "sampleNoDepthResult": no_depth,
        "sampleVolumeApproximationResult": volume_based,
        "modelBoundary": "uses public depth or volume approximations only",
        "createsOrders": False,
    }


def _build_shadow_trading_section() -> dict[str, Any]:
    return {
        "meaning": "record hypothetical signal and follow-up outcomes without placing orders",
        "schemas": [
            "ShadowSignal",
            "ShadowExecutionSnapshot",
            "ShadowOutcome",
        ],
        "followUps": ["1m", "5m", "15m", "1h", "4h", "24h"],
        "tracks": [
            "theoreticalEntryPrice",
            "bidPriceAtSignal",
            "askPriceAtSignal",
            "spreadPctAtSignal",
            "orderbookDepthAtSignal",
            "wouldHitStop",
            "wouldHitTakeProfit",
            "maxFavorableExcursion",
            "maxAdverseExcursion",
        ],
        "startedInV13_4_11": False,
        "createsOrders": False,
    }


def _build_live_feasibility_section(redesign_review: dict[str, Any]) -> dict[str, Any]:
    adjusted = _adjusted_metrics(redesign_review)
    raw_score = LiveFeasibilityInput(
        backtestQuality=10,
        slippageRobustness=5 if float(adjusted.get("totalReturnPct") or 0) < 0 else 60,
        liquidityQuality=None,
        tradeFrequency=25,
        pairConcentration=70,
        drawdownRisk=5,
        lossStreakRisk=20,
        executionDataAvailability=20,
        shadowTradingReadiness=0,
        riskGateReadiness=30,
        hasShadowTradingResults=False,
    )
    score = calculate_live_feasibility_score(raw_score)
    return {
        "dimensions": list(raw_score.to_dict().keys()),
        "levels": {
            "0-39": "not_live_feasible",
            "40-59": "research_only",
            "60-74": "shadow_ready",
            "75-84": "dry_run_candidate",
            "85+": "controlled_live_candidate",
        },
        "defaultCap": "missing shadow trading results caps score at research_only or below",
        "currentTrendPullbackExample": score.to_dict(),
        "dryRunApprovalFromScore": False,
    }


def build_report(redesign_review_path: Path) -> ExecutionRealityDesignReport:
    warnings: list[str] = []
    redesign_review = _read_json(redesign_review_path, warnings)
    if redesign_review.get("currentStatus") != "needs_redesign":
        warnings.append("Input redesign review does not declare currentStatus=needs_redesign.")

    return ExecutionRealityDesignReport(
        reportId=REPORT_ID,
        version=REPORT_VERSION,
        purpose="Design execution reality and liquidity gate before Dry-run",
        modules=_build_modules(),
        liquidityGate=_build_liquidity_gate_section(),
        slippageStressTest=_build_slippage_section(redesign_review),
        orderImpactModel=_build_order_impact_section(),
        shadowTrading=_build_shadow_trading_section(),
        liveFeasibilityScore=_build_live_feasibility_section(redesign_review),
        proposalIntegration={
            "fieldsAdded": [
                "liquidity_context",
                "execution_reality_context",
                "shadow_trading_context",
                "live_feasibility_score",
            ],
            "allFieldsOptional": True,
            "createsOrders": False,
        },
        riskGateIntegration={
            "requiredBeforeDryRunCandidate": [
                "liquidity_gate_result",
                "execution_reality_result",
                "shadow_trading_result",
            ],
            "defaultWithoutResults": "rejected_before_dry_run_candidate",
            "createsOrders": False,
        },
        dryRunApproved=False,
        liveTradingApproved=False,
        nextStepRecommendation="V13.4.12 - Shadow Trading Skeleton",
        warnings=warnings,
        generatedAt=_utc_now(),
    )


def _write_summary(report: dict[str, Any], path: Path) -> None:
    lines = [
        "# V13.4.11 Execution Reality Summary",
        "",
        "## Decision",
        "",
        f"- dryRunApproved: {report['dryRunApproved']}",
        f"- liveTradingApproved: {report['liveTradingApproved']}",
        f"- nextStepRecommendation: {report['nextStepRecommendation']}",
        "- V13.4.11 is a design skeleton only.",
        "",
        "## Modules",
        "",
    ]
    for module in report["modules"]:
        lines.append(f"- {module['module']}: {module['purpose']}")
    lines.extend(
        [
            "",
            "## Liquidity Gate",
            "",
            "- Missing 1h volume and orderbook depth returns insufficient_liquidity_data.",
            "- Position notional must stay below configured volume/depth ratios.",
            "- Wide spread or oversized notional rejects or requires review.",
            "",
            "## Slippage Stress Test",
            "",
            "- Scenarios: 0.05%, 0.10%, 0.20%, 0.30% one-way.",
            "- This is report-layer post-processing, not native exchange matching.",
            "",
            "## Order Impact Model",
            "",
            "- Uses orderbook depth when available.",
            "- Falls back to 1h or 24h quote volume approximations.",
            "- Missing public data returns unavailable, not approved.",
            "",
            "## Shadow Trading",
            "",
            "- Defines ShadowSignal, ShadowExecutionSnapshot, and ShadowOutcome.",
            "- Does not start polling or create orders in V13.4.11.",
            "",
            "## Live Feasibility Score",
            "",
            f"- Current Trend Pullback example level: {report['liveFeasibilityScore']['currentTrendPullbackExample']['level']}",
            f"- Current Trend Pullback example score: {report['liveFeasibilityScore']['currentTrendPullbackExample']['totalScore']}",
            "- Missing shadow trading results cap the score before Dry-run candidate levels.",
            "",
            "## Proposal Integration",
            "",
        ]
    )
    lines.extend(f"- {field}" for field in report["proposalIntegration"]["fieldsAdded"])
    lines.extend(
        [
            "",
            "## Risk Gate Integration",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in report["riskGateIntegration"]["requiredBeforeDryRunCandidate"])
    lines.extend(
        [
            "",
            "## Safety",
            "",
            "No backtest was run. No Dry-run was entered. No real API key, Trade API, Withdraw API, account read, position read, order creation, or auto trading was added.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def export_report(redesign_review_path: Path, output_json: Path, output_summary: Path) -> tuple[Path, Path]:
    report = build_report(redesign_review_path).to_dict()
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(report, output_summary)
    return output_json, output_summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.11 execution reality design report.")
    parser.add_argument("--redesign-review", type=Path, default=DEFAULT_REDESIGN_REVIEW)
    parser.add_argument("--output-json", type=Path, default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-summary", type=Path, default=DEFAULT_OUTPUT_SUMMARY)
    args = parser.parse_args()

    output_json, output_summary = export_report(args.redesign_review, args.output_json, args.output_summary)
    print(f"Exported execution reality design report: {output_json}")
    print(f"Exported execution reality summary: {output_summary}")


if __name__ == "__main__":
    main()

