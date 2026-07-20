"""Evidence writers for the offline Demo release replay."""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from .adapters import ReplayResult
from .contracts import DemoReplayContract


def _utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _metric(row: Mapping[str, Any], name: str) -> Any:
    metrics = row.get("metrics", {})
    return metrics.get(name) if isinstance(metrics, Mapping) else None


def _comparison_row(
    contract: DemoReplayContract,
    result: ReplayResult,
    original: Mapping[str, Any],
) -> dict[str, Any]:
    original_approval = original.get("approval")
    originally_approved = original.get("approved")
    if originally_approved is None and isinstance(original_approval, Mapping):
        originally_approved = original_approval.get("passed")
    return {
        "strategyCandidateId": contract.strategy_candidate_id,
        "demoReleaseId": contract.demo_release_id,
        "contractHash": contract.contract_hash,
        "timeframe": contract.timeframe,
        "family": contract.family_key,
        "direction": contract.direction,
        "originalResearchApproved": bool(originally_approved),
        "demoReleaseMode": contract.release_mode,
        "overrideActor": contract.override_actor,
        "bypassedEvidence": ";".join(contract.bypassed_evidence),
        "originalTradeCount": _metric(original, "tradeCount"),
        "replayTradeCount": result.metrics.get("tradeCount"),
        "originalProfitFactor": _metric(original, "profitFactor"),
        "replayProfitFactor": result.metrics.get("profitFactor"),
        "originalExpectancyR": _metric(original, "expectancyR"),
        "replayExpectancyR": result.metrics.get("expectancyR"),
        "originalTotalR": _metric(original, "totalR") or _metric(original, "totalNetR"),
        "replayTotalR": result.metrics.get("totalR"),
        "replayStatus": result.status,
    }


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _artifact_manifest(root: Path) -> dict[str, Any]:
    artifacts = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.name == "artifact_manifest.json":
            continue
        relative = path.relative_to(root).as_posix()
        artifacts.append(
            {
                "path": relative,
                "bytes": path.stat().st_size,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        )
    return {
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
        "generatedAt": _utc_now(),
        "status": "research_replay_only",
    }


def write_replay_evidence(
    output_dir: str | Path,
    contracts: Sequence[DemoReplayContract],
    results: Mapping[str, ReplayResult],
    originals: Mapping[str, Mapping[str, Any]],
    *,
    expected_count: int = 10,
    load_warnings: Sequence[str] = (),
) -> dict[str, Any]:
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    if len(contracts) != expected_count:
        raise ValueError(f"unexpected_contract_count:{len(contracts)}!={expected_count}")
    contract_ids = {row.strategy_candidate_id for row in contracts}
    if set(results) != contract_ids:
        raise ValueError("replay_result_identity_mismatch")
    if not contract_ids.issubset(originals):
        missing = sorted(contract_ids.difference(originals))
        raise ValueError(f"original_evidence_missing:{','.join(missing)}")

    _write_json(root / "contract_inventory.json", [row.to_dict() for row in contracts])
    _write_json(root / "replay_results.json", [results[key].to_dict() for key in sorted(results)])

    ledger_dir = root / "trade_ledgers"
    ledger_dir.mkdir(parents=True, exist_ok=True)
    for candidate_id, result in sorted(results.items()):
        pd.DataFrame(result.trades).to_parquet(ledger_dir / f"{candidate_id}.parquet", index=False)

    comparisons = [
        _comparison_row(contract, results[contract.strategy_candidate_id], originals[contract.strategy_candidate_id])
        for contract in sorted(contracts, key=lambda row: row.strategy_candidate_id)
    ]
    _write_csv(root / "comparison.csv", comparisons)
    _write_json(root / "comparison.json", comparisons)

    summary = {
        "bypassedForwardEvidenceCount": sum(
            "local_forward_samples" in row.bypassed_evidence for row in contracts
        ),
        "contractCount": len(contracts),
        "experimentalOverrideCount": sum(row.release_mode == "experimental_override" for row in contracts),
        "generatedAt": _utc_now(),
        "loadWarnings": list(load_warnings),
        "originalResearchApprovedCount": sum(row["originalResearchApproved"] for row in comparisons),
        "releaseCountCreated": 0,
        "replayCount": len(results),
        "status": "research_replay_only",
        "totalReplayTrades": sum(int(row.metrics.get("tradeCount", 0)) for row in results.values()),
    }
    _write_json(root / "replay_summary.json", summary)
    markdown = [
        "# Demo Release Replay Summary",
        "",
        f"- Status: `{summary['status']}`",
        f"- Contracts replayed: {summary['contractCount']}",
        f"- Originally research-approved: {summary['originalResearchApprovedCount']}",
        f"- Experimental overrides: {summary['experimentalOverrideCount']}",
        f"- Releases created by replay: {summary['releaseCountCreated']}",
        f"- Replay trades: {summary['totalReplayTrades']}",
        "",
        "This run is offline research replay only. It does not modify Console contracts, create a Demo release, or approve live trading.",
    ]
    (root / "replay_summary.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    _write_json(root / "artifact_manifest.json", _artifact_manifest(root))
    return summary
