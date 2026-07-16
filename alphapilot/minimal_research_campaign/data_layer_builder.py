"""Build the shared minimal data layer from existing canonical Parquet files."""

from __future__ import annotations

import argparse
import csv
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable, Sequence

import pandas as pd
import pyarrow.parquet as pq

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .data_layer import profile_ohlcv_frame, select_core_universe
from .forward_collection import build_forward_collection_plan
from .snapshot import build_snapshot_manifest


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def discover_authoritative_ohlcv(
    data_root: Path | str,
    *,
    timeframes: Sequence[str] = ("1h", "4h", "1d"),
) -> list[dict[str, Any]]:
    """Choose one existing longest canonical file per instrument and timeframe."""

    root = Path(data_root).resolve()
    canonical = root / "_alphapilot" / "canonical"
    candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for provider in ("okx", "user_local"):
        ohlcv_root = canonical / provider / "swap" / "ohlcv"
        if not ohlcv_root.is_dir():
            continue
        for timeframe in timeframes:
            for path in ohlcv_root.glob(f"*/{timeframe}/*.parquet"):
                try:
                    rows = int(pq.ParquetFile(path).metadata.num_rows)
                except Exception:
                    continue
                instrument = path.parent.parent.name
                candidates.setdefault((instrument, timeframe), []).append(
                    {
                        "instrumentId": instrument,
                        "timeframe": timeframe,
                        "provider": provider,
                        "path": str(path.resolve()),
                        "relativePath": path.resolve().relative_to(root).as_posix(),
                        "rowCount": rows,
                    }
                )
    selected: list[dict[str, Any]] = []
    for key in sorted(candidates):
        selected.append(
            max(
                candidates[key],
                key=lambda row: (
                    int(row["rowCount"]),
                    1 if row["provider"] == "okx" else 0,
                    str(row["path"]),
                ),
            )
        )
    return selected


def _read_profile(reference: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(reference["path"]))
    frame = pd.read_parquet(path)
    profile = profile_ohlcv_frame(
        frame,
        instrument_id=str(reference["instrumentId"]),
        timeframe=str(reference["timeframe"]),
        file_path=str(reference["relativePath"]),
        file_hash="pending_selection",
    )
    provider = str(reference["provider"])
    profile["provider"] = provider
    profile["exchange"] = "okx" if provider == "okx" else "unverified_local_exchange"
    profile["provenanceStatus"] = (
        "okx_public_canonical" if provider == "okx" else "user_confirmed_local_proxy"
    )
    return profile


def _write_csv(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    records = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "instrumentId",
        "exchange",
        "marketType",
        "effectiveBacktestStart",
        "commonCutoff",
        "historyMonths",
        "coveragePct",
        "missingRatePct",
        "liquidityScore",
        "included",
        "reasonZh",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in records:
            item = dict(row)
            common = item.get("commonCutoff")
            item["commonCutoff"] = json.dumps(common, ensure_ascii=False, sort_keys=True) if isinstance(common, dict) else common
            writer.writerow(item)


def _render_selection(core: dict[str, Any], profiles: list[dict[str, Any]]) -> str:
    lines = [
        "# Minimal Fixed Core Universe",
        "",
        f"- Core members: `{core['memberCount']}`",
        f"- Cohort type: `{core['cohortType']}`",
        "- Historical PIT universe: `false`",
        "- Selection uses strategy returns: `false`",
        f"- Profile count: `{len(profiles)}`",
        "",
        "The cohort is fixed before the campaign. It is suitable for bounded single-instrument time-series research, but it must not be described as a historical point-in-time universe.",
        "",
        "## Common Cutoff",
        "",
    ]
    for timeframe, cutoff in sorted(core["commonCutoffByTimeframe"].items()):
        lines.append(f"- `{timeframe}`: `{cutoff}`")
    lines.extend(["", "## Members", ""])
    for row in core["members"]:
        lines.append(
            f"- `{row['instrumentId']}`: history `{row['historyMonths']:.1f}` months, coverage `{row['coveragePct']:.2f}%`, liquidity score `{row['liquidityScore']:.4f}`"
        )
    return "\n".join(lines) + "\n"


def _funding_available(data_root: Path, selected_ids: set[str]) -> bool:
    canonical = data_root / "_alphapilot" / "canonical"
    return any(
        any((canonical / provider / "swap" / "funding" / instrument).glob("*.parquet"))
        for provider in ("okx", "user_local")
        for instrument in selected_ids
    )


def build_minimal_data_layer(
    *,
    data_root: Path | str,
    repo_root: Path | str,
    target_size: int = 20,
    minimum_history_months: float = 24.0,
    git_commit: str,
) -> dict[str, Any]:
    """Build reports and a shared manifest without mutating or copying data."""

    data = Path(data_root).resolve()
    repo = Path(repo_root).resolve()
    discovered = discover_authoritative_ohlcv(data)
    profiles: list[dict[str, Any]] = []
    profile_errors: list[dict[str, str]] = []
    for reference in discovered:
        try:
            profiles.append(_read_profile(reference))
        except Exception as exc:
            profile_errors.append(
                {
                    "instrumentId": str(reference["instrumentId"]),
                    "timeframe": str(reference["timeframe"]),
                    "path": str(reference["relativePath"]),
                    "error": str(exc),
                }
            )
    core = select_core_universe(
        profiles,
        target_size=target_size,
        required_timeframes=("1h", "4h"),
        minimum_history_months=minimum_history_months,
    )
    selected_ids = {str(row["instrumentId"]) for row in core["members"]}
    reference_by_key = {
        (str(row["instrumentId"]), str(row["timeframe"])): row
        for row in discovered
    }
    dataset_references: list[dict[str, Any]] = []
    for member in core["members"]:
        for timeframe, profile in sorted(member["profiles"].items()):
            reference = reference_by_key[(str(member["instrumentId"]), timeframe)]
            path = Path(str(reference["path"]))
            file_hash = sha256_file(path)
            profile["sha256"] = file_hash
            dataset_references.append(
                {
                    "instrumentId": str(member["instrumentId"]),
                    "timeframe": timeframe,
                    "path": str(reference["relativePath"]),
                    "sha256": file_hash,
                    "rowCount": int(reference["rowCount"]),
                    "provider": str(reference["provider"]),
                    "effectiveBacktestStart": str(profile["effectiveBacktestStart"]),
                    "latestConfirmed": str(profile["latestConfirmed"]),
                }
            )
    # Hashes are part of the frozen core identity, so recompute it after selection.
    core_without_hash = {key: value for key, value in core.items() if key != "coreUniverseHash"}
    core["coreUniverseHash"] = stable_hash(core_without_hash, prefix="minimal_fixed_core_universe")
    snapshot = build_snapshot_manifest(core, dataset_references, git_commit=git_commit)
    generated_at = _utc_now()
    snapshot["createdAt"] = generated_at

    output_root = repo / "reports" / "minimal_data_layer"
    output_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output_root / "core_universe.json", core)
    _write_csv(output_root / "core_universe.csv", core["selectionRows"])
    (output_root / "core_universe_selection.md").write_text(
        _render_selection(core, profiles), encoding="utf-8"
    )
    by_timeframe = {
        timeframe: {
            "profileCount": sum(row["timeframe"] == timeframe for row in profiles),
            "selectedCoreCoverageCount": sum(
                row["timeframe"] == timeframe and row["instrumentId"] in selected_ids
                for row in profiles
            ),
            "formalResearchReady": timeframe in {"1h", "4h"} and core["memberCount"] >= 8,
        }
        for timeframe in ("1h", "4h", "1d")
    }
    data_audit = {
        "schemaVersion": "minimal_data_audit_v1",
        "generatedAt": generated_at,
        "dataRoot": str(data),
        "readOnlyBuild": True,
        "discoveredAuthoritativeFileCount": len(discovered),
        "profileCount": len(profiles),
        "profileErrors": profile_errors,
        "coverageByTimeframe": by_timeframe,
        "selectionUsesStrategyReturns": False,
    }
    write_json_atomic(output_root / "data_audit.json", data_audit)
    family_eligibility = {
        "schemaVersion": "minimal_family_eligibility_v1",
        "fixedCoreTimeSeries4h": {
            "formalEligible": core["memberCount"] >= 8,
            "reason": "fixed core has sufficient 4h coverage; cohort limitation must be disclosed",
        },
        "fixedCoreTimeSeries1h": {
            "formalEligible": core["memberCount"] >= 8,
            "reason": "fixed core has sufficient 1h coverage; no 1h hypothesis is preregistered in this campaign",
        },
        "fixedCoreCrossSectional1d": {
            "formalEligible": False,
            "diagnosticOnly": True,
            "reason": "historical PIT membership is unavailable and 1d core coverage is incomplete",
        },
        "fiveMinuteResearchEnabled": False,
    }
    write_json_atomic(output_root / "family_eligibility.json", family_eligibility)

    snapshot_path = repo / "research" / "data_snapshots" / f"{snapshot['snapshotId']}.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    write_json_atomic(snapshot_path, snapshot)

    available = {"OHLCV"}
    if _funding_available(data, selected_ids):
        available.add("Funding")
    forward_plan = build_forward_collection_plan(
        available_data_types=available,
        start_at=generated_at,
    )
    forward_root = repo / "reports" / "forward_collection"
    forward_root.mkdir(parents=True, exist_ok=True)
    write_json_atomic(forward_root / "collection_plan.json", forward_plan)
    forward_status = {
        "schemaVersion": "minimal_forward_collection_status_v1",
        "generatedAt": generated_at,
        "collectorStarted": False,
        "networkRequestsMade": 0,
        "forwardDataCannotBackfillHistory": True,
        "statusByDataType": {
            key: value["status"] for key, value in forward_plan["dataTypes"].items()
        },
    }
    write_json_atomic(forward_root / "collection_status.json", forward_status)
    return {
        "coreUniverse": core,
        "sharedSnapshot": snapshot,
        "dataAudit": data_audit,
        "familyEligibility": family_eligibility,
        "forwardCollectionPlan": forward_plan,
        "forwardCollectionStatus": forward_status,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the V13.27.1.13 minimal shared data layer.")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--repo-root", default=".")
    parser.add_argument("--target-size", type=int, default=20)
    parser.add_argument("--minimum-history-months", type=float, default=24.0)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    result = build_minimal_data_layer(
        data_root=args.data_root,
        repo_root=args.repo_root,
        target_size=args.target_size,
        minimum_history_months=args.minimum_history_months,
        git_commit=args.git_commit,
    )
    print(
        json.dumps(
            {
                "coreMemberCount": result["coreUniverse"]["memberCount"],
                "snapshotId": result["sharedSnapshot"]["snapshotId"],
                "physicalCopiesCreated": 0,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
