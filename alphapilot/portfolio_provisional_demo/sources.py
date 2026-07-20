"""Read-only source loaders for the V46 provisional Demo evidence patch."""

from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.portfolio_rescue.contracts import RiskPolicy
from alphapilot.portfolio_rescue.replay import replay_policy


def sha256_file(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def verify_patch_instruction(
    instruction_path: str | Path, manifest_path: str | Path
) -> dict[str, Any]:
    instruction = Path(instruction_path)
    manifest = json.loads(Path(manifest_path).read_text(encoding="utf-8"))
    actual = sha256_file(instruction)
    expected = str(manifest.get("sha256") or "")
    if not expected or actual != expected:
        raise ValueError("patch_instruction_hash_mismatch")
    return {
        "filename": instruction.name,
        "sha256": actual,
        "manifestFilename": Path(manifest_path).name,
        "verified": True,
    }


def _okx_instrument_id(pair: str) -> str:
    base, separator, quote = pair.partition("/USDT:USDT")
    if separator != "/USDT:USDT" or quote or not base:
        raise ValueError(f"unsupported_research_pair:{pair}")
    return f"{base.upper()}-USDT-SWAP"


def load_research_instruments(policy_ledger: str | Path) -> list[str]:
    frame = pd.read_parquet(Path(policy_ledger), columns=["pair"])
    return sorted({_okx_instrument_id(str(value)) for value in frame["pair"].dropna()})


def load_demo_universe_snapshot(database_path: str | Path) -> dict[str, Any]:
    database = Path(database_path).resolve()
    uri = database.as_uri() + "?mode=ro&immutable=1"
    with sqlite3.connect(uri, uri=True) as connection:
        row = connection.execute(
            """
            SELECT publicManifestHash, authenticatedInstrumentHash,
                   projectionJson, generatedAt
              FROM DemoInstrumentUniverseCache
             WHERE environment = 'demo'
             ORDER BY generatedAt DESC
             LIMIT 1
            """
        ).fetchone()
    if row is None:
        raise ValueError("demo_universe_snapshot_missing")
    projection = json.loads(row[2])
    blockers = list(projection.get("blockers") or [])
    if projection.get("status") != "usable" or blockers:
        raise ValueError("demo_universe_snapshot_not_usable")
    runtime = sorted(
        {
            str(value).upper().strip()
            for value in projection.get("eligibleInstrumentIds") or []
            if str(value).strip()
        }
    )
    if not runtime:
        raise ValueError("demo_runtime_universe_empty")
    runtime_core = {"generatedAt": row[3], "eligibleInstrumentIds": runtime}
    return {
        "generatedAt": row[3],
        "publicSnapshotHash": row[0],
        "publicCount": int(projection.get("publicUniverseCount") or 0),
        "authenticatedHash": row[1],
        "authenticatedCount": int(projection.get("demoAccountInstrumentCount") or 0),
        "authenticatedExactListRetained": False,
        "runtimeSnapshotHash": stable_hash(
            runtime_core, prefix="demo_runtime_universe_snapshot"
        ),
        "runtimeInstruments": runtime,
        "runtimeCount": len(runtime),
        "sourceDatabaseSha256": sha256_file(database),
        "readOnly": True,
    }


def _normalize_record(row: Mapping[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in row.items():
        if pd.isna(value):
            normalized[key] = None
        elif isinstance(value, pd.Timestamp):
            normalized[key] = value.isoformat()
        elif hasattr(value, "item"):
            normalized[key] = value.item()
        else:
            normalized[key] = value
    return normalized


def _ledger_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    ordered = frame.sort_values(["entryDate", "candidateId", "pair"]).reset_index(
        drop=True
    )
    return [_normalize_record(row) for row in ordered.to_dict(orient="records")]


def build_replay_parity_audit(
    *, v46_report_dir: str | Path, selected_policy_ledger: str | Path
) -> dict[str, Any]:
    report = Path(v46_report_dir).resolve()
    preregistration = json.loads(
        (report / "preregistration.json").read_text(encoding="utf-8")
    )
    policy_results = json.loads(
        (report / "policy_results.json").read_text(encoding="utf-8")
    )
    selected = next(
        row
        for row in policy_results
        if (row.get("policy") or {}).get("policy_id") == "pair_14d_cooldown"
    )
    policy_payload = dict(selected["policy"])
    policy = RiskPolicy(
        policy_id=str(policy_payload["policy_id"]),
        pair_cooldown_days=int(policy_payload["pair_cooldown_days"]),
        maximum_concurrent_positions=int(policy_payload["maximum_concurrent_positions"]),
        same_direction_cap=int(policy_payload["same_direction_cap"]),
        losing_pair_cooldown_days=int(policy_payload["losing_pair_cooldown_days"]),
        additional_cost_stress_r=tuple(
            float(value) for value in policy_payload["additional_cost_stress_r"]
        ),
        version=str(policy_payload["version"]),
    )
    source_rows: list[dict[str, Any]] = []
    ledger_receipts = []
    for item in preregistration["ledgers"]:
        source_path = Path(item["path"])
        if not source_path.exists():
            source_path = (
                report.parents[1]
                / "demo_release_replay"
                / "v13_27_1_46_20260720"
                / "trade_ledgers"
                / f"{item['candidateId']}.parquet"
            )
        actual_sha = sha256_file(source_path)
        if actual_sha != item["sha256"]:
            raise ValueError(f"source_ledger_hash_mismatch:{item['candidateId']}")
        frame = pd.read_parquet(source_path)
        source_rows.extend(frame.to_dict(orient="records"))
        ledger_receipts.append(
            {
                "candidateId": item["candidateId"],
                "sourcePath": source_path.name,
                "sha256": actual_sha,
                "tradeCount": len(frame),
                "verified": True,
            }
        )

    replayed = replay_policy(source_rows, policy)
    frozen_frame = pd.read_parquet(Path(selected_policy_ledger))
    replayed_frame = pd.DataFrame(replayed.accepted_trades)
    frozen_records = _ledger_records(frozen_frame)
    replayed_records = _ledger_records(replayed_frame)
    frozen_hash = stable_hash(frozen_records, prefix="frozen_policy_ledger")
    replayed_hash = stable_hash(replayed_records, prefix="replayed_policy_ledger")
    checks = {
        "selectedPolicyHashExact": policy.policy_hash == policy_payload["policy_hash"],
        "acceptedLedgerExact": replayed_records == frozen_records,
        "metricsExact": replayed.metrics == selected["metrics"],
        "stressMetricsExact": replayed.stress_metrics == selected["stressMetrics"],
        "rejectionCountsExact": replayed.rejection_counts == selected["rejectionCounts"],
    }
    passed = all(checks.values())
    return {
        "schemaVersion": "v46_portfolio_replay_parity_audit_v1",
        "status": "passed" if passed else "failed",
        "parityPercent": 100.0 if passed else 0.0,
        "checks": checks,
        "sourceLedgers": ledger_receipts,
        "sourceTradeCount": len(source_rows),
        "replayedAcceptedTradeCount": len(replayed_records),
        "frozenAcceptedTradeCount": len(frozen_records),
        "replayedLedgerHash": replayed_hash,
        "frozenLedgerHash": frozen_hash,
        "selectedPolicyId": policy.policy_id,
        "selectedPolicyHash": policy.policy_hash,
    }
