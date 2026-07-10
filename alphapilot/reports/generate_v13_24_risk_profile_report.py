"""Generate the auditable V13.24 immutable RiskProfile baseline."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.risk_profiles import (
    ENVIRONMENTS,
    build_risk_profile_record,
    conservative_profile,
)


def build_v13_24_risk_profile_report(*, code_commit: str) -> dict[str, Any]:
    if not str(code_commit).strip():
        raise ValueError("V13.24 report requires a code commit")
    records = [
        build_risk_profile_record(conservative_profile(environment), status="preset")
        for environment in sorted(ENVIRONMENTS)
    ]
    return {
        "reportId": "v13_24_risk_profile_report",
        "version": "V13.24.0",
        "status": "completed",
        "generatedAt": datetime.now(UTC).isoformat(),
        "codeCommit": str(code_commit),
        "schemaVersion": "risk_profile_v1",
        "profileCount": len(records),
        "profiles": [
            {
                "riskProfileId": record.riskProfileId,
                "riskProfileHash": record.contentHash,
                "profileKey": record.profileKey,
                "version": record.version,
                "environment": record.environment,
                "name": record.name,
                "profile": record.profile,
                "safetyEnvelope": record.safetyEnvelope,
            }
            for record in records
        ],
        "portfolioRiskControls": [
            "active_strategy_limit",
            "portfolio_and_per_strategy_position_limits",
            "per_symbol_and_per_direction_exposure_limits",
            "correlation_group_open_risk_limit",
            "daily_loss_drawdown_and_canary_stops",
            "loss_cooldown",
            "data_freshness_and_liquidity_gates",
        ],
        "safetyBoundary": {
            "configurationCreatesNewImmutableVersion": True,
            "activationIsAppendOnlyAndRollbackable": True,
            "routineUiCanChangeSafetyEnvelope": False,
            "activationEnablesTrading": False,
            "rawCredentialsStored": False,
            "withdrawApiEnabled": False,
            "liveAdapterPresent": False,
            "liveExecutionEnabled": False,
        },
    }


def _summary(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# AlphaPilot V13.24 RiskProfile Summary",
            "",
            f"- Status: `{report['status']}`",
            f"- Immutable default profiles: `{report['profileCount']}`",
            "- Every release binds a RiskProfile id and checksum.",
            "- Profile activation is audited and does not enable trading.",
            "- Live execution and Withdraw remain disabled in V13.24.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--report", default="reports/v13_24_risk_profile_report.json")
    parser.add_argument("--summary", default="reports/v13_24_risk_profile_summary.md")
    args = parser.parse_args()
    report = build_v13_24_risk_profile_report(code_commit=args.code_commit)
    write_json_atomic(Path(args.report), report)
    Path(args.summary).write_text(_summary(report), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "reportId": report["reportId"],
                "status": report["status"],
                "profileCount": report["profileCount"],
                "liveExecutionEnabled": report["safetyBoundary"]["liveExecutionEnabled"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
