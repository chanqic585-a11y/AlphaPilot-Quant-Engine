"""Evaluate formal candidates for immutable, release-gated OKX Demo automation."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.adapters.control_console_contract import build_control_console_contract
from alphapilot.evolution.promotion.demo_release import promote_candidate_to_demo
from alphapilot.evolution.promotion.gate import PromotionEvidence, evaluate_demo_promotion
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _calendar_days(outcomes: list[Any]) -> int:
    if not outcomes:
        return 0
    dates = [datetime.fromisoformat(item.exitAt.replace("Z", "+00:00")).date() for item in outcomes]
    return (max(dates) - min(dates)).days + 1


def _promotion_evidence(candidate: Any, outcomes: list[Any]) -> PromotionEvidence:
    raw = candidate.candidate.get("promotionEvidence")
    if not isinstance(raw, dict):
        raise ValueError("candidate_missing_promotion_evidence")
    required = {
        "frequency",
        "pointInTimePassed",
        "leakageCheckPassed",
        "fdrPassed",
        "deflatedSharpePassed",
        "pboPassed",
        "validWalkForwardFolds",
        "lockedOosProfitFactor",
        "doubledCostProfitFactor",
        "maxDrawdownPercent",
        "realizedRewardRisk",
        "largestSymbolShare",
        "largestMonthShare",
        "largestRegimeShare",
        "lockedOosClosedSamples",
        "inputsFrozen",
        "checksumsMatch",
    }
    missing = sorted(required - set(raw))
    if missing:
        raise ValueError("candidate_incomplete_promotion_evidence:" + ",".join(missing))
    public_forward = bool(outcomes) and all(
        item.evidenceClass == "realtime_local_forward" for item in outcomes
    )
    values = {key: raw[key] for key in required}
    values.update(
        {
            "shadowClosedSamples": len(outcomes),
            "shadowCalendarDays": _calendar_days(outcomes),
            "shadowPublicMarketDriven": public_forward,
        }
    )
    return PromotionEvidence(**values)


def build_v13_20_report(
    *,
    registry_path: str | Path,
    code_commit: str,
    contract_directory: str | Path,
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not code_commit.strip():
        raise ValueError("V13.20 report requires a code commit")
    output_directory = Path(contract_directory)
    output_directory.mkdir(parents=True, exist_ok=True)
    connection = connect_registry(registry_path)
    candidate_rows: list[dict[str, Any]] = []
    contract_paths: list[str] = []
    try:
        repository = RegistryRepository(connection)
        candidates = repository.list_strategy_candidates()
        all_outcomes = repository.list_outcomes()
        for candidate in candidates:
            outcomes = [
                item
                for item in all_outcomes
                if item.strategyCandidateId == candidate.strategyCandidateId
                and item.evidenceClass == "realtime_local_forward"
            ]
            row: dict[str, Any] = {
                "strategyCandidateId": candidate.strategyCandidateId,
                "candidateContentHash": candidate.contentHash,
                "forwardClosedSamples": len(outcomes),
                "forwardCalendarDays": _calendar_days(outcomes),
            }
            try:
                evidence = _promotion_evidence(candidate, outcomes)
                gate = evaluate_demo_promotion(evidence)
                candidate_evidence = candidate.candidate.get("evidence", {})
                snapshot_id = str(candidate_evidence.get("dataSnapshotId") or "")
                snapshot = repository.get_data_snapshot(snapshot_id) if snapshot_id else None
                model_checksum = str(
                    candidate.candidate.get("promotionEvidence", {}).get("modelChecksum") or ""
                )
                if snapshot is None:
                    raise ValueError("candidate_training_snapshot_missing")
                if not model_checksum:
                    raise ValueError("candidate_model_checksum_missing")
                outcome = promote_candidate_to_demo(
                    candidate=candidate,
                    gateResult=gate,
                    repository=repository,
                    codeCommit=code_commit,
                    dataChecksum=snapshot.contentHash,
                    modelChecksum=model_checksum,
                )
                row["gate"] = gate.as_dict()
                row["promotionDecisionId"] = outcome.promotionDecision.promotionDecisionId
                if outcome.demoRelease is not None:
                    contract = build_control_console_contract(outcome.demoRelease)
                    path = output_directory / f"demo_release_contract_{outcome.demoRelease.demoReleaseId}.json"
                    write_json_atomic(path, contract)
                    contract_paths.append(str(path.resolve()))
                    row["demoReleaseId"] = outcome.demoRelease.demoReleaseId
                    row["contractPath"] = str(path.resolve())
                    row["status"] = "demo_eligible"
                else:
                    row["status"] = "promotion_gate_failed"
            except (TypeError, ValueError) as exc:
                row["status"] = "promotion_evidence_incomplete"
                row["blocker"] = str(exc)
            candidate_rows.append(row)
        releases = repository.list_demo_releases()
    finally:
        connection.close()
    if not candidates:
        status = "blocked_no_formal_strategy_candidate"
        blockers = [
            "no_formal_strategy_candidate",
            "no_completed_local_forward_evidence",
            "no_immutable_demo_release",
        ]
    elif not releases:
        status = "completed_no_demo_eligible_release"
        blockers = ["no_candidate_passed_all_demo_hard_gates"]
    else:
        status = "demo_release_ready"
        blockers = []
    report = {
        "reportId": "v13_20_okx_demo_release_report",
        "version": "V13.20.0",
        "status": status,
        "generatedAt": _utc_now(),
        "codeCommit": code_commit,
        "strategyCandidateCount": len(candidates),
        "demoReleaseCount": len(releases),
        "generatedContractCount": len(contract_paths),
        "contractPaths": contract_paths,
        "candidateEvaluations": candidate_rows,
        "blockers": blockers,
        "riskEnvelope": {
            "initialEquityUsdt": 1000.0,
            "maxOrderNotionalUsdt": 250.0,
            "riskPerTradePercent": 0.25,
            "maxConcurrentPositions": 3,
        },
        "safetyBoundary": {
            "immutableDemoReleaseRequired": True,
            "runtimeCredentialsStored": False,
            "noKeyModeFailsClosed": True,
            "liveExecutionEnabled": False,
            "withdrawApiEnabled": False,
            "automaticLivePromotion": False,
        },
    }
    contract = {
        "schemaVersion": "okx_demo_readiness_contract_v1",
        "stage": "okx_demo",
        "status": status,
        "demoReleaseCount": len(releases),
        "generatedContractCount": len(contract_paths),
        "blockers": blockers,
        "requiresRuntimeCredentials": True,
        "requiresOrderGate": True,
        "requiresAutomationGate": True,
        "liveExecutionEnabled": False,
        "withdrawApiEnabled": False,
    }
    return report, contract


def _summary(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# AlphaPilot V13.20 OKX Demo Release Summary",
            "",
            f"- Status: `{report['status']}`",
            f"- Strategy candidates: `{report['strategyCandidateCount']}`",
            f"- Demo releases: `{report['demoReleaseCount']}`",
            f"- Console contracts: `{report['generatedContractCount']}`",
            "",
            "Only a candidate that passes every fixed OOS, cost, concentration, forward,",
            "checksum, and risk gate may produce an immutable OKX Demo contract.",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", default="data/evolution_registry.sqlite")
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--contract-directory", default="reports")
    parser.add_argument("--report", default="reports/v13_20_okx_demo_release_report.json")
    parser.add_argument("--contract", default="reports/v13_20_okx_demo_readiness_contract.json")
    parser.add_argument("--summary", default="reports/v13_20_okx_demo_release_summary.md")
    args = parser.parse_args()
    report, contract = build_v13_20_report(
        registry_path=args.registry,
        code_commit=args.code_commit,
        contract_directory=args.contract_directory,
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
                "strategyCandidates": report["strategyCandidateCount"],
                "demoReleases": report["demoReleaseCount"],
                "contracts": report["generatedContractCount"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
