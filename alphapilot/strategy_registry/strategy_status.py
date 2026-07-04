"""Strategy status archive for research-only AlphaPilot strategies.

The registry records research decisions from local reports only. It does not
enable Dry-run, call exchange APIs, create orders, or auto trade.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVIDENCE_REPORTS = [
    "reports/v13_4_1_diagnosis_report.json",
    "reports/v13_4_2_signal_audit_report.json",
    "reports/v13_4_3_v02_candidate_matrix.json",
    "reports/v13_4_4_comparative_backtest_report.json",
    "reports/v13_4_5_expanded_validation_report.json",
]


@dataclass
class StrategyStatusRecord:
    strategyId: str
    strategyName: str
    status: str
    researchStatus: str
    reason: str
    evidenceReports: list[str]
    canBeUsedForLive: bool
    canBeUsedForDryRun: bool
    archivedAt: str


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_volume_rebound_status_records(archived_at: str | None = None) -> list[StrategyStatusRecord]:
    timestamp = archived_at or utc_now()
    common_reason = "Expanded validation remains negative after slippage adjustment; rejected for Dry-run."
    entries = [
        ("alpha_volume_rebound_v01", "AlphaPilotVolumeReboundV01", common_reason),
        (
            "alpha_volume_rebound_v02_a_trend_strict",
            "AlphaPilotVolumeReboundV02A",
            "Smoke comparison improved relatively, but the candidate was not included in the successful expanded validation set and is not approved.",
        ),
        (
            "alpha_volume_rebound_v02_b_volume_quality",
            "AlphaPilotVolumeReboundV02B",
            "Expanded validation reduced trade count but remained deeply negative after slippage.",
        ),
        (
            "alpha_volume_rebound_v02_c_exit_cleanup",
            "AlphaPilotVolumeReboundV02C",
            "Best relative expanded candidate, but still deeply negative after slippage and not usable for Dry-run.",
        ),
        (
            "alpha_volume_rebound_v02_d_early_failure_exit",
            "AlphaPilotVolumeReboundV02D",
            "Failed the V13.4.4 smoke comparison gate and was eliminated before expanded validation.",
        ),
        (
            "alpha_volume_rebound_v02_e_pair_risk_watchlist",
            "AlphaPilotVolumeReboundV02E",
            "Pair-risk changes did not improve enough in expanded validation and remain negative after slippage.",
        ),
    ]
    return [
        StrategyStatusRecord(
            strategyId=strategy_id,
            strategyName=name,
            status="rejected_for_dry_run",
            researchStatus="failed_research_current_sample",
            reason=reason,
            evidenceReports=EVIDENCE_REPORTS,
            canBeUsedForLive=False,
            canBeUsedForDryRun=False,
            archivedAt=timestamp,
        )
        for strategy_id, name, reason in entries
    ]


def build_strategy_status_archive(archived_at: str | None = None) -> dict[str, Any]:
    timestamp = archived_at or utc_now()
    return {
        "reportId": "v13_4_6_strategy_status_archive",
        "strategyFamily": "alpha_volume_rebound_v01_v02",
        "familyStatus": "rejected_for_dry_run",
        "researchStatus": "failed_research_current_sample",
        "dryRunApproved": False,
        "liveTradingApproved": False,
        "records": [asdict(record) for record in build_volume_rebound_status_records(timestamp)],
        "archivedAt": timestamp,
        "source": "alphapilot_v13_4_6_strategy_registry",
    }


def write_strategy_status_archive(path: Path, archived_at: str | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    archive = build_strategy_status_archive(archived_at)
    path.write_text(json.dumps(archive, ensure_ascii=False, indent=2), encoding="utf-8")
    return path

