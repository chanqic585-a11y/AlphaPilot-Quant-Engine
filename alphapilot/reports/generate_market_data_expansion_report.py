"""Generate V13.4.28 market data coverage and expansion reports.

This command reads local reports and schemas only. It does not download data,
run backtests, enter Dry-run, call exchange APIs, read accounts, create orders,
or auto trade.
"""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.data_expansion.data_source_registry import get_data_source_registry
from alphapilot.data_expansion.funding_rate_schema import build_funding_rate_schema
from alphapilot.data_expansion.liquidation_schema import build_liquidation_schema
from alphapilot.data_expansion.market_regime_proxy_schema import build_market_regime_proxy_schema
from alphapilot.data_expansion.open_interest_schema import build_open_interest_schema
from alphapilot.data_expansion.orderbook_proxy_schema import build_orderbook_proxy_schema
from alphapilot.data_expansion.public_data_collector_skeleton import collector_skeleton_manifest
from alphapilot.reports.market_data_expansion_schema import (
    CoverageRepairReport,
    DataCoverageGap,
    MarketDataExpansionReport,
    MissingPairTimeframe,
)

DEFAULT_PRE_REPAIR_REPORT = Path("reports/v13_4_27_market_regime_data_integrity_report.json")
DEFAULT_POST_REPAIR_REPORT = Path("reports/v13_4_28_post_repair_market_regime_data_integrity_report.json")
DEFAULT_COVERAGE_REPAIR_REPORT = Path("reports/v13_4_28_data_coverage_repair_report.json")
DEFAULT_COVERAGE_REPAIR_SUMMARY = Path("reports/v13_4_28_data_coverage_repair_summary.md")
DEFAULT_EXPANSION_REPORT = Path("reports/v13_4_28_market_data_expansion_report.json")
DEFAULT_EXPANSION_SUMMARY = Path("reports/v13_4_28_market_data_expansion_summary.md")
DEFAULT_DOWNLOAD_COMMAND = (
    'powershell -ExecutionPolicy Bypass -File scripts/download_data.ps1 '
    '-UseTop30 -Timeframes "1h,4h" -Timerange "20260101-" -Prepend -Run'
)
DEFAULT_DATA_PATH = "user_data/data/okx/futures"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(payload, encoding="utf-8")


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"_missing": True, "path": path.as_posix()}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - reports must preserve parse failures.
        return {"_error": str(exc), "path": path.as_posix()}


def _expected_ohlcv_path(pair: str, timeframe: str, data_path: str = DEFAULT_DATA_PATH) -> str:
    pair_file = pair.replace("/", "_").replace(":", "_")
    return f"{data_path}/{pair_file}-{timeframe}-futures.feather"


def _summary(report: dict[str, Any]) -> dict[str, Any]:
    return report.get("dataIntegrity", {}).get("summary", {})


def _quality_rows(report: dict[str, Any]) -> list[dict[str, Any]]:
    rows = report.get("dataIntegrity", {}).get("pairTimeframeQuality", [])
    return rows if isinstance(rows, list) else []


def _row_reason(row: dict[str, Any]) -> str:
    warnings = row.get("warnings") or []
    if warnings:
        return "; ".join(str(item) for item in warnings)
    status = row.get("status", "unknown")
    return f"status={status}"


def _missing_pair_timeframes(report: dict[str, Any]) -> list[MissingPairTimeframe]:
    missing = []
    for row in _quality_rows(report):
        if row.get("status") != "missing_file":
            continue
        pair = str(row.get("pair"))
        timeframe = str(row.get("timeframe"))
        missing.append(
            MissingPairTimeframe(
                pair=pair,
                timeframe=timeframe,
                expectedPath=_expected_ohlcv_path(pair, timeframe),
                reason=_row_reason(row),
                repairPlanned=True,
            )
        )
    return missing


def _coverage_gaps(pre_report: dict[str, Any], post_report: dict[str, Any]) -> list[DataCoverageGap]:
    post_lookup = {
        (row.get("pair"), row.get("timeframe")): row
        for row in _quality_rows(post_report)
    }
    gaps: list[DataCoverageGap] = []
    for row in _quality_rows(pre_report):
        status = row.get("status")
        if status not in {"missing_file", "warning", "invalid"}:
            continue
        pair = str(row.get("pair"))
        timeframe = str(row.get("timeframe"))
        post = post_lookup.get((pair, timeframe), {})
        post_status = str(post.get("status", "missing_after_repair"))
        if post_status in {"valid"}:
            repair_status = "repaired"
        elif post_status == status:
            repair_status = "unresolved"
        else:
            repair_status = f"changed_to_{post_status}"
        gaps.append(
            DataCoverageGap(
                pair=pair,
                timeframe=timeframe,
                status=str(status),
                reason=_row_reason(row),
                warnings=[str(item) for item in row.get("warnings", [])],
                rowCount=int(row.get("rowCount") or 0),
                missingRatePct=float(row.get("missingRatePct") or 0),
                repairStatus=repair_status,
            )
        )
    return gaps


def _build_repair_conclusion(pre_summary: dict[str, Any], post_summary: dict[str, Any]) -> tuple[str, str, list[str]]:
    warnings = []
    pre_missing = int(pre_summary.get("missingFileCount") or 0)
    post_missing = int(post_summary.get("missingFileCount") or 0)
    pre_warning = int(pre_summary.get("warningCount") or 0)
    post_warning = int(post_summary.get("warningCount") or 0)
    if post_missing == 0 and post_summary.get("status") == "valid":
        return "completed", "Local OHLCV coverage repair is complete for the checked pair/timeframe set.", warnings
    if post_missing < pre_missing:
        warnings.append("Some missing local OHLCV files remain after the public download repair attempt.")
        return (
            "completed_with_unresolved_gaps",
            "The repair attempt reduced missing coverage but unresolved local OHLCV gaps remain.",
            warnings,
        )
    if post_missing >= pre_missing and post_missing > 0:
        warnings.append("Missing local OHLCV files remain after the public download repair attempt.")
        warnings.append("The affected symbols may be unavailable in the configured OKX futures market universe.")
        return (
            "completed_with_unresolved_gaps",
            "The repair attempt completed, but the same missing local OHLCV gaps remain.",
            warnings,
        )
    if post_warning > pre_warning:
        warnings.append("Warning count increased after repair and needs review.")
    return (
        "completed_with_warnings",
        "No missing files remain, but data quality warnings still need review before strategy work.",
        warnings,
    )


def build_coverage_repair_report(args: argparse.Namespace) -> CoverageRepairReport:
    pre_report = _read_json(Path(args.pre_repair_report))
    post_report = _read_json(Path(args.post_repair_report))
    pre_summary = _summary(pre_report)
    post_summary = _summary(post_report)
    status, conclusion, warnings = _build_repair_conclusion(pre_summary, post_summary)
    warnings.extend(str(item) for item in post_summary.get("warnings", []) if item not in warnings)
    return CoverageRepairReport(
        reportId="v13_4_28_data_coverage_repair",
        version="V13.4.28",
        status=status,
        downloadCommand=args.download_command,
        preRepairSummary=pre_summary,
        postRepairSummary=post_summary,
        missingPairTimeframes=_missing_pair_timeframes(pre_report),
        dataCoverageGaps=_coverage_gaps(pre_report, post_report),
        repairConclusion=conclusion,
        generatedAt=utc_now(),
        warnings=warnings,
    )


def _next_step_recommendation(coverage: dict[str, Any]) -> list[str]:
    post = coverage.get("postRepairSummary", {})
    missing_count = int(post.get("missingFileCount") or 0)
    warning_count = int(post.get("warningCount") or 0)
    if missing_count > 0:
        return [
            "Resolve remaining local OHLCV coverage gaps before approving V13.4.29 strategy specification.",
            "Review whether unresolved pairs are unavailable on OKX futures or need universe replacement/mapping.",
            "Keep V13.4.29 Bear Regime Short Strategy Specification blocked until coverage policy is explicit.",
        ]
    if warning_count > 0:
        return [
            "Review remaining data warnings, then proceed to V13.4.29 Bear Regime Short Strategy Specification if acceptable.",
            "Do not run backtests or Dry-run from V13.4.28 outputs.",
            "Prioritize Funding/OI public collector implementation only after OHLCV baseline is accepted.",
        ]
    return [
        "Proceed to V13.4.29 Bear Regime Short Strategy Specification.",
        "Keep public funding/open-interest/orderbook/liquidation collection as a separate data-engineering step.",
        "Do not enter Dry-run or live trading from this report.",
    ]


def build_expansion_report(coverage: CoverageRepairReport) -> MarketDataExpansionReport:
    coverage_payload = coverage.to_dict()
    warnings = list(coverage.warnings)
    warnings.append("Public data expansion is schema-only in V13.4.28; no new external collector is active.")
    return MarketDataExpansionReport(
        reportId="v13_4_28_market_data_expansion",
        version="V13.4.28",
        status=coverage.status,
        coverageRepair=coverage_payload,
        fundingRateSchema=build_funding_rate_schema().to_dict(),
        openInterestSchema=build_open_interest_schema().to_dict(),
        orderbookProxySchema=build_orderbook_proxy_schema().to_dict(),
        liquidationSchema=build_liquidation_schema().to_dict(),
        marketRegimeProxySchema=build_market_regime_proxy_schema().to_dict(),
        dataSourceRegistry=get_data_source_registry(),
        collectorSkeleton=collector_skeleton_manifest(),
        nextStepRecommendation=_next_step_recommendation(coverage_payload),
        dryRunApproved=False,
        liveTradingApproved=False,
        safetyBoundary={
            "strategyImplemented": False,
            "backtestExecuted": False,
            "dryRunExecuted": False,
            "liveTradingApproved": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyRequired": False,
            "apiKeyStored": False,
            "accountRead": False,
            "positionRead": False,
            "orderCreated": False,
            "autoTrading": False,
            "mobileAppChanged": False,
        },
        generatedAt=utc_now(),
        warnings=warnings,
    )


def _coverage_summary_markdown(report: dict[str, Any]) -> str:
    pre = report.get("preRepairSummary", {})
    post = report.get("postRepairSummary", {})
    missing = report.get("missingPairTimeframes", [])
    gaps = report.get("dataCoverageGaps", [])
    warnings = report.get("warnings", [])
    return f"""# AlphaPilot V13.4.28 Data Coverage Repair Report

Status: {report.get("status")}

V13.4.28 attempted to repair local public OHLCV coverage. It did not implement
a strategy, run a backtest, enter Dry-run, call private exchange APIs, read
accounts, create orders, or auto trade.

## Repair Command

```powershell
{report.get("downloadCommand")}
```

## Pre-Repair Summary

- status: {pre.get("status")}
- pairCount: {pre.get("pairCount")}
- pairTimeframeCount: {pre.get("pairTimeframeCount")}
- missingFileCount: {pre.get("missingFileCount")}
- warningCount: {pre.get("warningCount")}
- invalidCount: {pre.get("invalidCount")}

## Post-Repair Summary

- status: {post.get("status")}
- pairCount: {post.get("pairCount")}
- pairTimeframeCount: {post.get("pairTimeframeCount")}
- missingFileCount: {post.get("missingFileCount")}
- warningCount: {post.get("warningCount")}
- invalidCount: {post.get("invalidCount")}

## Missing Pair/Timeframes From Baseline

{chr(10).join(f"- {item.get('pair')} {item.get('timeframe')}: {item.get('reason')} -> {item.get('expectedPath')}" for item in missing) or "- none"}

## Coverage Gaps

{chr(10).join(f"- {item.get('pair')} {item.get('timeframe')}: {item.get('status')} -> {item.get('repairStatus')} ({item.get('reason')})" for item in gaps) or "- none"}

## Conclusion

{report.get("repairConclusion")}

Warnings:

{chr(10).join(f"- {item}" for item in warnings) or "- none"}
"""


def _expansion_summary_markdown(report: dict[str, Any]) -> str:
    coverage = report.get("coverageRepair", {})
    sources = report.get("dataSourceRegistry", [])
    recommendations = report.get("nextStepRecommendation", [])
    warnings = report.get("warnings", [])
    return f"""# AlphaPilot V13.4.28 Market Data Coverage and Expansion

Status: {report.get("status")}

V13.4.28 repairs local OHLCV coverage where possible and adds a public-data
expansion skeleton for future research inputs. It does not implement strategy
logic, run backtests, enter Dry-run, call private APIs, read accounts, create
orders, or auto trade.

## Coverage Repair

- preRepairMissingFileCount: {coverage.get("preRepairSummary", {}).get("missingFileCount")}
- postRepairMissingFileCount: {coverage.get("postRepairSummary", {}).get("missingFileCount")}
- postRepairWarningCount: {coverage.get("postRepairSummary", {}).get("warningCount")}
- conclusion: {coverage.get("repairConclusion")}

## Public Data Expansion Schemas

- Funding Rate: {report.get("fundingRateSchema", {}).get("storageStatus")}
- Open Interest: {report.get("openInterestSchema", {}).get("storageStatus")}
- Orderbook Spread Proxy: {report.get("orderbookProxySchema", {}).get("storageStatus")}
- Liquidation: {report.get("liquidationSchema", {}).get("storageStatus")}
- Market Regime Proxy: {report.get("marketRegimeProxySchema", {}).get("storageStatus")}

## Data Source Registry

{chr(10).join(f"- {item.get('sourceId')}: apiKey={item.get('requiresApiKey')} private={item.get('usesPrivateEndpoint')} status={item.get('status')}" for item in sources) or "- none"}

## Next Step Recommendation

{chr(10).join(f"- {item}" for item in recommendations) or "- none"}

## Safety Boundary

- dryRunApproved: {report.get("dryRunApproved")}
- liveTradingApproved: {report.get("liveTradingApproved")}
- no Trade API
- no Withdraw API
- no API key storage
- no account or position reads
- no order creation
- no auto trading

Warnings:

{chr(10).join(f"- {item}" for item in warnings) or "- none"}
"""


def run(args: argparse.Namespace) -> dict[str, Any]:
    coverage = build_coverage_repair_report(args)
    coverage_payload = coverage.to_dict()
    expansion = build_expansion_report(coverage)
    expansion_payload = expansion.to_dict()
    _write_json(Path(args.coverage_repair_report), coverage_payload)
    _write_text(Path(args.coverage_repair_summary), _coverage_summary_markdown(coverage_payload))
    _write_json(Path(args.expansion_report), expansion_payload)
    _write_text(Path(args.expansion_summary), _expansion_summary_markdown(expansion_payload))
    return expansion_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate V13.4.28 market data expansion report.")
    parser.add_argument("--pre-repair-report", default=str(DEFAULT_PRE_REPAIR_REPORT))
    parser.add_argument("--post-repair-report", default=str(DEFAULT_POST_REPAIR_REPORT))
    parser.add_argument("--coverage-repair-report", default=str(DEFAULT_COVERAGE_REPAIR_REPORT))
    parser.add_argument("--coverage-repair-summary", default=str(DEFAULT_COVERAGE_REPAIR_SUMMARY))
    parser.add_argument("--expansion-report", default=str(DEFAULT_EXPANSION_REPORT))
    parser.add_argument("--expansion-summary", default=str(DEFAULT_EXPANSION_SUMMARY))
    parser.add_argument("--download-command", default=DEFAULT_DOWNLOAD_COMMAND)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    report = run(args)
    coverage = report.get("coverageRepair", {})
    post = coverage.get("postRepairSummary", {})
    print(f"V13.4.28 status: {report.get('status')}")
    print(f"Post-repair missing files: {post.get('missingFileCount')}")
    print(f"Report: {args.expansion_report}")
    print(f"Summary: {args.expansion_summary}")


if __name__ == "__main__":
    main()
