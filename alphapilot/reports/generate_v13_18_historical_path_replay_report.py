"""Run the V13.18 actual-candle replay engine probe and Outcome Ledger."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.factor_runs.materializer import load_snapshot_frames
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.replay import ReplayConfig, ReplaySignal, run_historical_replay
from alphapilot.evolution.replay.ledger import persist_replay_outcomes


DEFAULT_V13_17_REPORT = Path("reports/v13_17_factor_run_backtest_report.json")


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _profit_factor(values: list[float]) -> float | None:
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    return gains / losses if losses > 0 else None


def _drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def _build_probe_signals(
    matrix: pd.DataFrame,
    *,
    source_entity_id: str,
    cadence_bars: int,
) -> list[ReplaySignal]:
    signals: list[ReplaySignal] = []
    for instrument_index, (instrument, frame) in enumerate(
        matrix.groupby("instrument_id", sort=True)
    ):
        ordered = frame.sort_values("timestamp_ms").reset_index(drop=True)
        for sequence, row in enumerate(ordered.iloc[::cadence_bars].itertuples(index=False)):
            risk_distance = float(row.factor_atr_pct_14) * float(row.close)
            direction = "long" if (sequence + instrument_index) % 2 == 0 else "short"
            signal_id = stable_hash(
                {
                    "sourceEntityId": source_entity_id,
                    "instrumentId": instrument,
                    "decisionTimestampMs": int(row.timestamp_ms),
                    "direction": direction,
                    "riskDistance": risk_distance,
                },
                prefix="replay_signal",
            )
            signals.append(
                ReplaySignal(
                    signalId=signal_id,
                    instrumentId=str(instrument),
                    timeframe=str(row.timeframe),
                    direction=direction,
                    decisionTimestampMs=int(row.timestamp_ms),
                    riskDistance=risk_distance,
                    sourceEntityId=source_entity_id,
                    strategyCandidateId=None,
                )
            )
    return signals


def _metrics(trades: list[dict[str, Any]]) -> dict[str, Any]:
    net_values = [float(item["netR"]) for item in trades]
    reasons = Counter(str(item["exitReason"]) for item in trades)
    return {
        "closedTradeCount": len(trades),
        "targetCount": reasons.get("target", 0),
        "stopCount": reasons.get("stop", 0),
        "timeoutCount": reasons.get("timeout", 0),
        "targetRate": reasons.get("target", 0) / len(trades) if trades else None,
        "averageNetR": fmean(net_values) if net_values else None,
        "totalNetR": sum(net_values),
        "profitFactor": _profit_factor(net_values),
        "maximumDrawdownR": _drawdown(net_values),
        "averageMfeR": fmean(float(item["mfeR"]) for item in trades) if trades else None,
        "averageMaeR": fmean(float(item["maeR"]) for item in trades) if trades else None,
        "sameBarAmbiguousCount": sum(bool(item["sameBarAmbiguous"]) for item in trades),
        "fundingDataAvailableCount": sum(bool(item["fundingDataAvailable"]) for item in trades),
    }


def _summary(report: dict[str, Any]) -> str:
    metrics = report["probeMetrics"]
    return "\n".join(
        [
            "# AlphaPilot V13.18 Historical Path Replay Summary",
            "",
            f"- Status: `{report['status']}`",
            f"- DataSnapshot: `{report['dataSnapshotId']}`",
            f"- Formal strategy replay count: `{report['formalStrategyReplayCount']}`",
            f"- Engine probe signals: `{report['probeSignalCount']}`",
            f"- Closed probe paths: `{metrics['closedTradeCount']}`",
            f"- Skipped probe paths: `{report['skippedSignalCount']}`",
            f"- Outcome Ledger rows: `{report['outcomeLedger']['outcomeCount']}`",
            "",
            "The probe validates actual canonical candle execution paths. Its alternating",
            "signals are not a strategy and its PnL is not promotion evidence. Formal",
            "strategy replay remains blocked because V13.17 created no StrategyCandidate.",
            "",
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--v13-17-report", default=str(DEFAULT_V13_17_REPORT))
    parser.add_argument("--registry", default="data/evolution_registry.sqlite")
    parser.add_argument("--canonical-root", default="data/market/canonical")
    parser.add_argument("--cadence-bars", type=int, default=120)
    parser.add_argument("--code-commit", required=True)
    parser.add_argument("--report", default="reports/v13_18_historical_path_replay_report.json")
    parser.add_argument("--contract", default="reports/v13_18_historical_replay_contract.json")
    parser.add_argument("--summary", default="reports/v13_18_historical_path_replay_summary.md")
    args = parser.parse_args()
    if args.cadence_bars <= 0:
        raise ValueError("cadence-bars must be positive")
    prior = json.loads(Path(args.v13_17_report).read_text(encoding="utf-8"))
    matrix_path = Path(prior["matrix"]["path"])
    matrix = pd.read_parquet(matrix_path)
    snapshot_id = str(prior["dataSnapshotId"])
    source_entity_id = stable_hash(
        {
            "schemaVersion": "v13_18_engine_probe_v1",
            "dataSnapshotId": snapshot_id,
            "factorMatrixSha256": prior["matrix"]["sha256"],
            "cadenceBars": args.cadence_bars,
            "directionPolicy": "alternating_non_strategy_probe",
            "codeCommit": args.code_commit,
        },
        prefix="replay_probe",
    )
    connection = connect_registry(args.registry)
    try:
        repository = RegistryRepository(connection)
        snapshot = repository.get_data_snapshot(snapshot_id)
        if snapshot is None:
            raise ValueError(f"DataSnapshot is not registered: {snapshot_id}")
        bars = load_snapshot_frames(
            snapshot,
            canonical_root=Path(args.canonical_root).resolve(),
            timeframe=str(prior["matrix"]["timeframe"]),
        )
        signals = _build_probe_signals(
            matrix,
            source_entity_id=source_entity_id,
            cadence_bars=args.cadence_bars,
        )
        replay = run_historical_replay(
            signals,
            bars_by_instrument=bars,
            config=ReplayConfig(),
        )
        ledger = persist_replay_outcomes(
            replay,
            repository=repository,
            data_snapshot_id=snapshot_id,
            source_entity_type="engine_probe",
            source_entity_id=source_entity_id,
            evidence_class="historical_path_replay_probe",
            code_commit=args.code_commit,
        )
        formal_candidate_count = repository.count("StrategyCandidates")
    finally:
        connection.close()
    trade_rows = [trade.to_dict() for trade in replay.trades]
    skipped_rows = [item.to_dict() for item in replay.skippedSignals]
    report = {
        "reportId": "v13_18_historical_path_replay_report",
        "version": "V13.18.0",
        "status": "completed_engine_probe_no_formal_candidate",
        "generatedAt": _utc_now(),
        "codeCommit": args.code_commit,
        "dataSnapshotId": snapshot_id,
        "factorMatrixSha256": prior["matrix"]["sha256"],
        "evidenceClass": "historical_path_replay_probe",
        "engineProbeOnly": True,
        "probeSignalPolicy": "fixed_cadence_alternating_direction_not_a_strategy",
        "probeSignalCount": len(signals),
        "skippedSignalCount": len(skipped_rows),
        "skipReasons": dict(Counter(item["reason"] for item in skipped_rows)),
        "probeMetrics": _metrics(trade_rows),
        "probeTradeSample": trade_rows[:20],
        "outcomeLedger": ledger,
        "formalStrategyCandidateCount": formal_candidate_count,
        "formalStrategyReplayCount": 0,
        "formalPromotionEligible": False,
        "blockers": [
            "v13_17_no_formal_strategy_candidate",
            "engine_probe_is_not_strategy_evidence",
            *prior.get("blockers", []),
        ],
        "legacySandboxPolicy": {
            "evidenceClass": "legacy_synthetic",
            "includedInFormalTraining": False,
            "includedInProfitabilityClaims": False,
        },
        "safetyBoundary": {
            "localHistoricalReplayOnly": True,
            "apiKeyUsed": False,
            "accountRead": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "orderCreated": False,
            "demoReleaseCreated": False,
            "liveTradingEnabled": False,
        },
    }
    contract = {
        "schemaVersion": "local_replay_console_contract_v1",
        "stage": "local_replay",
        "status": "engine_ready_waiting_formal_candidate",
        "dataSnapshotId": snapshot_id,
        "formalStrategyReplayCount": 0,
        "engineProbeOutcomeCount": ledger["outcomeCount"],
        "engineProbeIsStrategyPerformance": False,
        "reportPath": str(Path(args.report).resolve()),
        "executionEnabled": False,
        "createsOrders": False,
    }
    write_json_atomic(Path(args.report), report)
    write_json_atomic(Path(args.contract), contract)
    Path(args.summary).write_text(_summary(report), encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "reportId": report["reportId"],
                "version": report["version"],
                "status": report["status"],
                "probeSignals": report["probeSignalCount"],
                "closedProbePaths": report["probeMetrics"]["closedTradeCount"],
                "outcomeLedgerRows": ledger["outcomeCount"],
                "formalStrategyReplayCount": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
