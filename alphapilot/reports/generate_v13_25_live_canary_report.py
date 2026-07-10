"""Export immutable LiveReleases and the V13.25 fail-closed readiness report."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.promotion.live_release import export_live_release
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


def build_v13_25_live_canary_report(
    *,
    registry_path: str | Path,
    code_commit: str,
    export_directory: str | Path,
) -> dict[str, Any]:
    if not str(code_commit).strip():
        raise ValueError("V13.25 report requires a code commit")
    directory = Path(export_directory)
    directory.mkdir(parents=True, exist_ok=True)
    connection = connect_registry(registry_path)
    try:
        repository = RegistryRepository(connection)
        releases = repository.list_live_releases()
    finally:
        connection.close()
    exports: list[dict[str, Any]] = []
    for record in releases:
        payload = export_live_release(record)
        path = directory / f"live_release_{record.liveReleaseId}.json"
        write_json_atomic(path, payload)
        exports.append({
            "liveReleaseId": record.liveReleaseId,
            "liveReleaseHash": record.contentHash,
            "status": record.status,
            "exportPath": str(path.resolve()),
        })
    ready = bool(exports)
    return {
        "reportId": "v13_25_live_canary_report",
        "version": "V13.25.0",
        "status": "live_release_ready_runtime_disabled" if ready else "blocked_no_live_release",
        "generatedAt": datetime.now(UTC).isoformat(),
        "codeCommit": str(code_commit),
        "liveReleaseCount": len(exports),
        "liveReleases": exports,
        "blockers": [
            "no_approved_live_release",
            "runtime_credentials_not_loaded",
            "live_process_gates_disabled",
            "live_canary_kill_switch_active",
            "live_reconciliation_not_confirmed",
        ] if not ready else [
            "runtime_credentials_not_loaded",
            "live_process_gates_disabled",
            "live_canary_kill_switch_active",
            "live_reconciliation_not_confirmed",
        ],
        "runtimeContract": {
            "adapterPresent": True,
            "enabledByDefault": False,
            "approvedLiveReleaseRequired": True,
            "activeRiskProfileHashRequired": True,
            "readOnlyReconciliationRequired": True,
            "attachedTakeProfitRequired": True,
            "attachedStopLossRequired": True,
            "minimumRewardRiskRatio": 2.0,
            "idempotencyRequired": True,
            "restartRecoveryRequired": True,
            "unknownStatePausesEntries": True,
            "killSwitchRequired": True,
            "withdrawAllowed": False,
            "rawCredentialStorageAllowed": False,
        },
        "executionEvidence": {
            "realOrdersPlacedByReport": 0,
            "liveCredentialsReadByReport": False,
            "privateAccountRequestedByReport": False,
        },
    }


def _summary(report: dict[str, Any]) -> str:
    return "\n".join([
        "# AlphaPilot V13.25 Live Canary Summary",
        "",
        f"- Status: `{report['status']}`",
        f"- Approved Live releases: `{report['liveReleaseCount']}`",
        "- OKX Live adapter is installed but disabled by default.",
        "- This report reads no credentials, account state, positions, or orders.",
        "- Withdraw is not implemented.",
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/evolution_registry.sqlite")
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--export-directory", default="reports")
    parser.add_argument("--report", default="reports/v13_25_live_canary_report.json")
    parser.add_argument("--summary", default="reports/v13_25_live_canary_summary.md")
    args = parser.parse_args()
    report = build_v13_25_live_canary_report(
        registry_path=args.registry,
        code_commit=args.code_commit,
        export_directory=args.export_directory,
    )
    write_json_atomic(Path(args.report), report)
    Path(args.summary).write_text(_summary(report), encoding="utf-8", newline="\n")
    print(json.dumps({
        "reportId": report["reportId"],
        "status": report["status"],
        "liveReleaseCount": report["liveReleaseCount"],
        "realOrdersPlacedByReport": report["executionEvidence"]["realOrdersPlacedByReport"],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
