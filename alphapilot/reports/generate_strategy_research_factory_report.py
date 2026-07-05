"""Generate V13.4.25 Strategy Research Factory artifacts.

The generator reads local research reports and writes hypothesis reports only.
It does not write strategy code, run Freqtrade, run a backtest, enter Dry-run,
call exchange APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.reports.strategy_research_factory_schema import StrategyResearchFactoryReport
from alphapilot.research_factory.hypothesis_mining import mine_strategy_research_hypotheses, summarize_hypotheses
from alphapilot.research_factory.hypothesis_registry import HYPOTHESIS_CATEGORIES, SOURCE_REPORTS

REPORT_ID = "v13_4_25_strategy_research_factory_report"
VERSION = "V13.4.25"
SOURCE = "alphapilot_v13_4_25_strategy_research_factory"
DEFAULT_OUTPUT_JSON = Path("reports/v13_4_25_strategy_research_factory_report.json")
DEFAULT_OUTPUT_SUMMARY = Path("reports/v13_4_25_strategy_research_factory_summary.md")
DEFAULT_OUTPUT_HYPOTHESES = Path("reports/v13_4_25_research_hypotheses.json")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _next_experiment_plan() -> dict[str, Any]:
    return {
        "versionName": "V13.4.26 - Factor Hypothesis Validation Dataset",
        "goal": "Build a validation dataset for the highest-priority research hypotheses before any strategy implementation.",
        "scope": [
            "materialize hypothesis validation rows from FactorDataPanel and benchmark reports",
            "segment by volatility, trend strength, EMA50 distance, Bollinger position, volume expansion, and liquidity context",
            "compare all candidate contexts against NoTrade, BuyHoldBTC, and BenchmarkBollingerRebound after costs",
            "record invalidated and deferred hypotheses explicitly",
        ],
        "nonGoals": [
            "no Freqtrade strategy implementation",
            "no new backtest execution",
            "no Dry-run",
            "no Trade API or Withdraw API",
            "no account or position read",
            "no order creation",
            "no auto trading",
        ],
        "minimumPromotionGate": [
            "hypothesis has sufficient coverage",
            "hypothesis improves cost-adjusted evidence versus NoTrade and BuyHoldBTC in validation data",
            "effect is not isolated to one pair or one month",
            "execution-reality and liquidity notes are complete",
        ],
    }


def build_report(output_json: Path, output_summary: Path, output_hypotheses: Path) -> StrategyResearchFactoryReport:
    result = mine_strategy_research_hypotheses()
    hypothesis_dicts = [item.to_dict() for item in result.hypotheses]
    counts = summarize_hypotheses(result.hypotheses)
    return StrategyResearchFactoryReport(
        reportId=REPORT_ID,
        version=VERSION,
        status="research_only",
        source=SOURCE,
        inputReports=list(SOURCE_REPORTS.values()),
        inputReportSummaries=result.inputReportSummaries,
        hypothesisCategories=HYPOTHESIS_CATEGORIES,
        hypotheses=hypothesis_dicts,
        hypothesisCounts=counts,
        topPriorityHypotheses=counts["highPriority"],
        rejectedHypotheses=counts["rejected"],
        nextExperimentPlan=_next_experiment_plan(),
        dryRunApproved=False,
        liveTradingApproved=False,
        warnings=result.warnings,
        generatedAt=_utc_now(),
        outputReportPath=output_json.as_posix(),
        outputSummaryPath=output_summary.as_posix(),
        outputHypothesesPath=output_hypotheses.as_posix(),
        notes=[
            "Research hypotheses are not trading strategies.",
            "V13.4.25 did not run a backtest or modify user_data/strategies.",
            "No Dry-run, live trading, Trade API, Withdraw API, API key, account read, position read, order, or auto trading was used.",
        ],
    )


def _summary(report: StrategyResearchFactoryReport) -> str:
    payload = report.to_dict()
    counts = payload["hypothesisCounts"]
    high_priority = ", ".join(payload["topPriorityHypotheses"]) or "none"
    rejected = ", ".join(payload["rejectedHypotheses"]) or "none"
    category_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(counts["byCategory"].items()))
    status_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(counts["byStatus"].items()))
    priority_lines = "\n".join(f"- {key}: {value}" for key, value in sorted(counts["byPriority"].items()))
    hypothesis_lines = "\n".join(
        f"- {item['hypothesisId']} | {item['name']} | {item['category']} | {item['status']} | priority={item['priority']}"
        for item in payload["hypotheses"]
    )
    next_plan = payload["nextExperimentPlan"]
    return f"""# AlphaPilot V13.4.25 Strategy Research Factory Summary

Status: research-only hypothesis mining.

V13.4.25 reads V13.4.22 factor evaluation, V13.4.23 benchmark suite results,
and V13.4.24 benchmark failure review. It converts that evidence into a
Strategy Research Factory hypothesis registry.

No strategy code was written. No Freqtrade backtest was run. No Dry-run or live
trading approval was granted.

## Inputs

{chr(10).join(f"- {path}" for path in payload["inputReports"])}

## Hypothesis Counts

- total: {counts["total"]}

By category:

{category_lines}

By status:

{status_lines}

By priority:

{priority_lines}

## High Priority Hypotheses

{high_priority}

## Rejected Hypotheses

{rejected}

## Hypothesis Registry

{hypothesis_lines}

## Next Experiment Plan

- versionName: {next_plan["versionName"]}
- goal: {next_plan["goal"]}

Scope:

{chr(10).join(f"- {item}" for item in next_plan["scope"])}

Non-goals:

{chr(10).join(f"- {item}" for item in next_plan["nonGoals"])}

## Safety Boundary

- dryRunApproved: {payload["dryRunApproved"]}
- liveTradingApproved: {payload["liveTradingApproved"]}
- no strategy code written
- no backtest execution
- no Dry-run
- no Trade API
- no Withdraw API
- no API key
- no account or position reads
- no order creation
- no auto trading

## Outputs

- {payload["outputReportPath"]}
- {payload["outputSummaryPath"]}
- {payload["outputHypothesesPath"]}
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate V13.4.25 strategy research factory reports.")
    parser.add_argument("--output-json", default=str(DEFAULT_OUTPUT_JSON))
    parser.add_argument("--output-summary", default=str(DEFAULT_OUTPUT_SUMMARY))
    parser.add_argument("--output-hypotheses", default=str(DEFAULT_OUTPUT_HYPOTHESES))
    args = parser.parse_args()

    output_json = Path(args.output_json)
    output_summary = Path(args.output_summary)
    output_hypotheses = Path(args.output_hypotheses)
    report = build_report(output_json, output_summary, output_hypotheses)
    payload = report.to_dict()
    _write_json(output_json, payload)
    _write_json(output_hypotheses, {"reportId": "v13_4_25_research_hypotheses", "version": VERSION, "hypotheses": payload["hypotheses"]})
    _write_text(output_summary, _summary(report))
    print(json.dumps({"report": args.output_json, "summary": args.output_summary, "hypotheses": args.output_hypotheses}, indent=2))


if __name__ == "__main__":
    main()
