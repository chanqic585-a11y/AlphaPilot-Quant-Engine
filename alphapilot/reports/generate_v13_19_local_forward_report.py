"""Generate the V13.19 local-forward daily report and console contract."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.forward.public_market import OkxForwardPublicMarket
from alphapilot.evolution.forward.runner import run_forward_cycle
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _profit_factor(values: list[float]) -> float | None:
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    return gains / losses if losses > 0 else None


def _summary(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# AlphaPilot V13.19 Local Forward Summary",
            "",
            f"- Status: `{report['status']}`",
            f"- Eligible releases: `{report['eligibleForwardReleaseCount']}`",
            f"- Sessions: `{report['forwardSessionCount']}`",
            f"- Forward events: `{report['forwardEventCount']}`",
            f"- Closed forward outcomes: `{report['closedForwardOutcomeCount']}`",
            f"- Virtual initial equity per account: `{report['virtualAccount']['initialEquityUsdt']} USDT`",
            "",
            "Real-time local forward evidence cannot be accelerated or backfilled. Collection",
            "gaps remain explicit. This stage uses public market data and creates no order.",
            "",
        ]
    )


def build_v13_19_report(
    *,
    registry_path: str | Path,
    code_commit: str,
    observe: bool,
    market_data: Any | None = None,
    account_id: str = "default_forward_account",
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not code_commit.strip():
        raise ValueError("V13.19 report requires a code commit")
    connection = connect_registry(registry_path)
    cycle_rows: list[dict[str, Any]] = []
    try:
        repository = RegistryRepository(connection)
        releases = repository.list_forward_releases(status="forward_eligible")
        if observe and releases:
            adapter = market_data or OkxForwardPublicMarket()
            for release in releases:
                cycle = run_forward_cycle(
                    release,
                    repository=repository,
                    market_data=adapter,
                    code_commit=code_commit,
                    account_id=account_id,
                )
                cycle_rows.append(cycle.__dict__)
        sessions = repository.list_forward_sessions()
        events = repository.list_forward_events()
        outcomes = [
            item
            for item in repository.list_outcomes()
            if item.evidenceClass == "realtime_local_forward"
        ]
    finally:
        connection.close()
    net_r = [float(item.outcome.get("netR", 0.0)) for item in outcomes]
    event_types = Counter(item.eventType for item in events)
    failure_count = event_types.get("collection_failure", 0)
    gap_count = event_types.get("collection_gap", 0)
    if not releases:
        status = "blocked_no_eligible_forward_release"
        blockers = [
            "no_formal_strategy_candidate",
            "no_candidate_bound_historical_replay",
            "no_immutable_forward_release",
        ]
    elif failure_count:
        status = "observing_with_collection_failures"
        blockers = ["unresolved_public_collection_failures"]
    else:
        status = "observing_public_market"
        blockers = []
    event_hash = stable_hash(
        [
            {
                "forwardEventId": item.forwardEventId,
                "contentHash": item.contentHash,
            }
            for item in events
        ],
        prefix="forward_event_manifest",
    )
    report = {
        "reportId": "v13_19_local_forward_report",
        "version": "V13.19.0",
        "status": status,
        "generatedAt": _utc_now(),
        "codeCommit": code_commit,
        "evidenceClass": "realtime_local_forward",
        "eligibleForwardReleaseCount": len(releases),
        "forwardSessionCount": len(sessions),
        "forwardEventCount": len(events),
        "forwardEventManifestHash": event_hash,
        "closedForwardOutcomeCount": len(outcomes),
        "collectionGapCount": gap_count,
        "collectionFailureCount": failure_count,
        "eventTypes": dict(event_types),
        "cycleResults": cycle_rows,
        "performance": {
            "averageNetR": fmean(net_r) if net_r else None,
            "totalNetR": sum(net_r),
            "profitFactor": _profit_factor(net_r),
            "sampleCount": len(net_r),
            "profitabilityClaimAllowed": False,
        },
        "virtualAccount": {
            "initialEquityUsdt": 1000.0,
            "exchangeAccountUsed": False,
            "timeCanBeAccelerated": False,
        },
        "blockers": blockers,
        "formalPromotionEligible": False,
        "safetyBoundary": {
            "publicMarketDataOnly": True,
            "downtimeBackfilled": False,
            "historicalReplayMixedIntoForward": False,
            "apiKeyUsed": False,
            "accountRead": False,
            "positionRead": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "orderCreated": False,
            "demoExecutionEnabled": False,
            "liveExecutionEnabled": False,
        },
    }
    contract = {
        "schemaVersion": "local_forward_console_contract_v1",
        "stage": "local_forward",
        "status": status,
        "eligibleForwardReleaseCount": len(releases),
        "activeSessionCount": len(sessions),
        "closedForwardOutcomeCount": len(outcomes),
        "collectionGapCount": gap_count,
        "collectionFailureCount": failure_count,
        "initialEquityUsdt": 1000.0,
        "evidenceClass": "realtime_local_forward",
        "timeCanBeAccelerated": False,
        "executionEnabled": False,
        "createsOrders": False,
        "blockers": blockers,
    }
    contract["contractHash"] = stable_hash(contract, prefix="local_forward_contract")
    return report, contract


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/evolution_registry.sqlite")
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--observe", action="store_true")
    parser.add_argument("--account-id", default="default_forward_account")
    parser.add_argument("--report", default="reports/v13_19_local_forward_report.json")
    parser.add_argument("--contract", default="reports/v13_19_local_forward_contract.json")
    parser.add_argument("--summary", default="reports/v13_19_local_forward_summary.md")
    args = parser.parse_args()
    report, contract = build_v13_19_report(
        registry_path=args.registry,
        code_commit=args.code_commit,
        observe=args.observe,
        account_id=args.account_id,
    )
    write_json_atomic(Path(args.report), report)
    write_json_atomic(Path(args.contract), contract)
    Path(args.summary).write_text(_summary(report), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "reportId": report["reportId"],
                "version": report["version"],
                "status": report["status"],
                "eligibleReleases": report["eligibleForwardReleaseCount"],
                "sessions": report["forwardSessionCount"],
                "closedOutcomes": report["closedForwardOutcomeCount"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
