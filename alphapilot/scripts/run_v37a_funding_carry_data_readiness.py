"""Generate V37A data-only readiness evidence for funding-carry research."""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.data_foundation.funding_carry_catalog import (
    FundingCarryCatalog,
    FundingHistoryConsolidator,
    OkxSpotHistoryCollector,
)
from alphapilot.data_foundation.funding_carry_data import (
    FundingCarryDataPolicy,
    build_causal_funding_carry_panel,
)
from alphapilot.data_foundation.funding_carry_readiness import (
    DualLegCostStressPolicy,
    evaluate_funding_carry_readiness,
)
from alphapilot.data_foundation.okx_public import OkxPublicClient
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash


REQUIRED_ALIGNED_DATA = {
    "same_exchange_spot",
    "same_exchange_perpetual",
    "funding_rate",
    "dual_leg_cost_and_capacity",
}


def _hash_digest(value: str, *, length: int) -> str:
    return value.rsplit("_", 1)[-1][:length]


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--warehouse-root", type=Path, required=True)
    parser.add_argument("--report-root", type=Path, required=True)
    parser.add_argument("--preregistration-path", type=Path, required=True)
    parser.add_argument("--asset", action="append", dest="assets")
    parser.add_argument("--begin", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--observed-at")
    parser.add_argument("--minimum-aligned-rows", type=int, default=1_000)
    parser.add_argument("--minimum-coverage-days", type=int, default=730)
    parser.add_argument("--collect-missing-spot", action="store_true")
    parser.add_argument("--base-url", default="https://openapi.okx.com")
    return parser


def _timestamp_ms(value: str) -> int:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return int(timestamp.value // 1_000_000)


def _validate_preregistration(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"funding_carry_preregistration_missing:{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("familyId") != "crypto_funding_carry_v1":
        raise ValueError("funding_carry_family_id_mismatch")
    if set(payload.get("requiredAlignedData", [])) != REQUIRED_ALIGNED_DATA:
        raise ValueError("funding_carry_required_data_contract_mismatch")
    zero_fields = {
        "executionCandidateCount": 0,
        "lockedOosReadCount": 0,
        "releaseCount": 0,
        "orderCount": 0,
    }
    if any(payload.get(key) != value for key, value in zero_fields.items()):
        raise ValueError("funding_carry_preregistration_has_side_effects")
    if payload.get("demoArm") is not False:
        raise ValueError("funding_carry_preregistration_demo_arm_not_false")
    return payload


def _decorate_candles(
    frame: pd.DataFrame, *, instrument_id: str
) -> pd.DataFrame:
    decorated = frame.copy()
    if "exchange" in decorated.columns:
        if set(decorated["exchange"].dropna().astype(str)) != {"OKX"}:
            raise ValueError("funding_carry_candle_exchange_mismatch")
    else:
        decorated["exchange"] = "OKX"
    if "instrumentId" in decorated.columns:
        if set(decorated["instrumentId"].dropna().astype(str)) != {
            instrument_id
        }:
            raise ValueError("funding_carry_candle_instrument_mismatch")
    else:
        decorated["instrumentId"] = instrument_id
    return decorated


def _forward_order_book_evidence(
    warehouse_root: Path, *, asset: str
) -> bool:
    root = warehouse_root / "okx_official_v1" / "forward_collection"
    required = {f"{asset}-USDT", f"{asset}-USDT-SWAP"}
    observed: set[str] = set()
    for path in root.rglob("*.json"):
        if "order_book_summary" not in str(path):
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if payload.get("publicDataOnly") is not True:
            continue
        for record in payload.get("records", []):
            if (
                isinstance(record, dict)
                and record.get("instrumentId") in required
                and float(record.get("bestBid") or 0) > 0
                and float(record.get("bestAsk") or 0) > 0
            ):
                observed.add(str(record["instrumentId"]))
    return observed == required


def _write_panel(
    *, warehouse_root: Path, asset: str, panel: pd.DataFrame
) -> dict[str, Any]:
    identity = stable_hash(
        {
            "asset": asset,
            "rows": panel.to_dict(orient="records"),
        },
        prefix="v37a_funding_carry_panel",
    )
    output = (
        warehouse_root
        / "okx_official_v1"
        / "funding_carry_v37a"
        / "canonical"
        / "aligned_panel"
        / asset
        / f"panel-{_hash_digest(identity, length=20)}.parquet"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    if not output.is_file():
        temporary = output.with_suffix(".parquet.tmp")
        panel.to_parquet(temporary, index=False, compression="zstd")
        temporary.replace(output)
    return {
        "asset": asset,
        "path": str(output.resolve()),
        "sha256": sha256_file(output),
        "rowCount": int(len(panel)),
        "startTimestampMs": int(panel["decisionTimestampMs"].min()),
        "endTimestampMs": int(panel["decisionTimestampMs"].max()),
        "zeroFillUsed": False,
        "joinDirection": "backward_asof",
    }


def _markdown(readiness: dict[str, Any], run_id: str) -> str:
    research_status = (
        "READY" if readiness["formalResearchDataReady"] else "BLOCKED"
    )
    forward_status = (
        "READY" if readiness["forwardExecutionEvidenceReady"] else "BLOCKED"
    )
    lines = [
        "# V37A Funding Carry Data Readiness",
        "",
        f"- Run ID: `{run_id}`",
        f"- Historical research: `{readiness['historicalResearchReady']}`",
        f"- Formal data: `{readiness['formalResearchDataReady']}`",
        f"- Forward execution evidence: `{readiness['forwardExecutionEvidenceReady']}`",
        f"- Historical / Formal decision: **{research_status}**",
        f"- Forward execution evidence: **{forward_status}**",
        "- Scope: data capability only; no candidate, Formal run, Release, Demo ARM, or order.",
        "",
        "## Blockers",
        "",
    ]
    blockers = readiness["formalBlockers"] + readiness["forwardBlockers"]
    lines.extend(f"- `{blocker}`" for blocker in blockers)
    if not blockers:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Cost And Capacity Semantics",
            "",
            "- Costs are preregistered dual-leg stress assumptions, not account fee claims.",
            "- Historical capacity uses minimum Spot/Perpetual quote turnover.",
            "- Historical OHLCV is not historical order-book evidence.",
            "",
        ]
    )
    return "\n".join(lines)


def run(
    argv: Sequence[str] | None = None,
    *,
    client: Any | None = None,
) -> dict[str, Any]:
    args = _parser().parse_args(argv)
    warehouse_root = args.warehouse_root.resolve()
    report_root = args.report_root.resolve()
    preregistration_path = args.preregistration_path.resolve()
    _validate_preregistration(preregistration_path)
    observed_at = args.observed_at or datetime.now(UTC).replace(
        microsecond=0
    ).isoformat()
    begin_ms = _timestamp_ms(args.begin)
    end_ms = _timestamp_ms(args.end)
    if begin_ms >= end_ms:
        raise ValueError("funding_carry_time_range_invalid")
    policy = FundingCarryDataPolicy.default(
        assets=tuple(args.assets or ("BTC", "ETH", "SOL")),
        minimum_aligned_rows=args.minimum_aligned_rows,
        minimum_coverage_days=args.minimum_coverage_days,
    )
    policy = replace(policy, history_start=pd.Timestamp(begin_ms, unit="ms", tz="UTC").isoformat())
    cost_policy = DualLegCostStressPolicy.default()
    catalog = FundingCarryCatalog(warehouse_root)
    public_client = client
    panels: dict[str, pd.DataFrame] = {}
    panel_artifacts: list[dict[str, Any]] = []
    source_artifacts: list[dict[str, Any]] = []
    source_blockers: list[str] = []

    for asset in policy.assets:
        spot_instrument = f"{asset}-USDT"
        perpetual_instrument = f"{asset}-USDT-SWAP"
        perpetual_artifact = None
        spot_artifact = None
        funding_artifact = None
        try:
            perpetual_artifact = catalog.perpetual_partition(
                instrument_id=perpetual_instrument,
                timeframe=policy.timeframe,
            )
        except (OSError, RuntimeError, ValueError) as error:
            source_blockers.append(
                f"source_preparation_failed:{asset}:perpetual:"
                f"{type(error).__name__}:{str(error)}"
            )

        try:
            spot_artifact = catalog.spot_partition(
                instrument_id=spot_instrument,
                timeframe=policy.timeframe,
            )
        except FileNotFoundError as error:
            if not args.collect_missing_spot:
                source_blockers.append(
                    f"source_preparation_failed:{asset}:spot:"
                    f"{type(error).__name__}:{str(error)}"
                )
            else:
                try:
                    public_client = public_client or OkxPublicClient(
                        base_url=args.base_url
                    )
                    spot_artifact = OkxSpotHistoryCollector(
                        warehouse_root=warehouse_root,
                        client=public_client,
                        timeframe=policy.timeframe,
                        requested_start_ms=begin_ms,
                    ).collect(spot_instrument, observed_at=observed_at).artifact
                except (OSError, RuntimeError, ValueError) as collection_error:
                    source_blockers.append(
                        f"source_preparation_failed:{asset}:spot_collection:"
                        f"{type(collection_error).__name__}:{str(collection_error)}"
                    )
        except (OSError, RuntimeError, ValueError) as error:
            source_blockers.append(
                f"source_preparation_failed:{asset}:spot:"
                f"{type(error).__name__}:{str(error)}"
            )

        try:
            funding_artifact = catalog.funding_partition(
                instrument_id=perpetual_instrument
            )
        except FileNotFoundError:
            try:
                funding_artifact = FundingHistoryConsolidator(
                    warehouse_root
                ).consolidate(
                    perpetual_instrument, observed_at=observed_at
                ).artifact
            except (OSError, RuntimeError, ValueError) as error:
                source_blockers.append(
                    f"source_preparation_failed:{asset}:funding_consolidation:"
                    f"{type(error).__name__}:{str(error)}"
                )
        except (OSError, RuntimeError, ValueError) as error:
            source_blockers.append(
                f"source_preparation_failed:{asset}:funding:"
                f"{type(error).__name__}:{str(error)}"
            )

        artifacts = (spot_artifact, perpetual_artifact, funding_artifact)
        for artifact in artifacts:
            if artifact is None:
                continue
            source_artifacts.append(
                {
                    "asset": asset,
                    "sourceType": artifact.source_type,
                    "path": str(artifact.path),
                    "sha256": artifact.sha256,
                    "manifestPath": str(artifact.manifest_path),
                    "manifestSha256": artifact.manifest_sha256,
                    "rowCount": artifact.row_count,
                }
            )
        if any(artifact is None for artifact in artifacts):
            continue

        try:
            spot = _decorate_candles(
                pd.read_parquet(spot_artifact.path),
                instrument_id=spot_instrument,
            )
            perpetual = _decorate_candles(
                pd.read_parquet(perpetual_artifact.path),
                instrument_id=perpetual_instrument,
            )
            funding = pd.read_parquet(funding_artifact.path)
            panel = build_causal_funding_carry_panel(
                asset=asset,
                spot=spot,
                perpetual=perpetual,
                funding=funding,
                maximum_lag_seconds=policy.maximum_lag_seconds,
            )
            panel = panel.loc[
                (panel["decisionTimestampMs"] >= begin_ms)
                & (panel["decisionTimestampMs"] <= end_ms)
            ].reset_index(drop=True)
            if panel.empty:
                raise ValueError("aligned_panel_empty_in_requested_range")
            panels[asset] = panel
            panel_artifacts.append(
                _write_panel(
                    warehouse_root=warehouse_root, asset=asset, panel=panel
                )
            )
        except (OSError, RuntimeError, ValueError) as error:
            source_blockers.append(
                f"source_preparation_failed:{asset}:alignment:"
                f"{type(error).__name__}:{str(error)}"
            )

    forward_evidence = {
        asset: _forward_order_book_evidence(warehouse_root, asset=asset)
        for asset in policy.assets
    }
    readiness = evaluate_funding_carry_readiness(
        policy=policy,
        cost_policy=cost_policy,
        panels=panels,
        forward_order_book_evidence=forward_evidence,
        additional_historical_blockers=tuple(source_blockers),
    )
    preregistration_sha = sha256_file(preregistration_path)
    run_id = stable_hash(
        {
            "policyHash": policy.policy_hash,
            "costPolicyHash": cost_policy.policy_hash,
            "preregistrationSha256": preregistration_sha,
            "beginMs": begin_ms,
            "endMs": end_ms,
            "panels": panel_artifacts,
        },
        prefix="v37a_funding_carry_data_readiness",
    )
    output = report_root / (
        f"v37a-funding-carry-{_hash_digest(run_id, length=20)}"
    )
    output.mkdir(parents=True, exist_ok=True)
    readiness.update(
        {
            "runId": run_id,
            "observedAt": observed_at,
            "preregistrationPath": str(preregistration_path),
            "preregistrationSha256": preregistration_sha,
            "requestedBeginMs": begin_ms,
            "requestedEndMs": end_ms,
        }
    )
    readiness["readinessHash"] = stable_hash(
        {key: value for key, value in readiness.items() if key != "readinessHash"},
        prefix="v37a_funding_readiness",
    )
    write_json_atomic(output / "funding_carry_data_readiness.json", readiness)
    (output / "funding_carry_data_readiness.md").write_text(
        _markdown(readiness, run_id), encoding="utf-8"
    )
    pd.DataFrame(readiness["perAsset"]).to_csv(
        output / "coverage_matrix.csv", index=False, encoding="utf-8"
    )
    write_json_atomic(
        output / "cost_capacity_evidence.json",
        {
            "schemaVersion": "v37a_cost_capacity_evidence_v1",
            "costEvidence": readiness["costEvidence"],
            "capacityEvidence": readiness["capacityEvidence"],
            "sideEffects": readiness["sideEffects"],
        },
    )
    request_records = list(
        getattr(public_client, "request_audit_records", []) if public_client else []
    )
    write_json_atomic(
        output / "request_audit.json",
        {
            "schemaVersion": "v37a_public_request_audit_v1",
            "collectionEnabled": bool(args.collect_missing_spot),
            "requestCount": len(request_records),
            "records": request_records,
            "credentialsUsed": False,
            "privateEndpointUsed": False,
        },
    )
    report_files = [
        path
        for path in output.iterdir()
        if path.is_file() and path.name != "artifact_manifest.json"
    ]
    artifact_manifest = {
        "schemaVersion": "v37a_funding_carry_artifact_manifest_v1",
        "runId": run_id,
        "dataOnly": True,
        "preregistrationPath": str(preregistration_path),
        "preregistrationSha256": preregistration_sha,
        "dataPolicyHash": policy.policy_hash,
        "costPolicyHash": cost_policy.policy_hash,
        "sourceArtifacts": source_artifacts,
        "panelArtifacts": panel_artifacts,
        "reportArtifacts": [
            {
                "path": str(path.resolve()),
                "sha256": sha256_file(path),
            }
            for path in sorted(report_files)
        ],
        "sideEffects": readiness["sideEffects"],
    }
    write_json_atomic(output / "artifact_manifest.json", artifact_manifest)
    return {
        "status": "completed",
        "runId": run_id,
        "reportDirectory": str(output.resolve()),
        "historicalResearchReady": readiness["historicalResearchReady"],
        "formalResearchDataReady": readiness["formalResearchDataReady"],
        "forwardExecutionEvidenceReady": readiness[
            "forwardExecutionEvidenceReady"
        ],
        "sideEffects": readiness["sideEffects"],
    }


def main() -> None:
    print(json.dumps(run(), ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
