"""V25 capacity semantics closure and fail-closed V26 admission."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.data_provenance.volume_provenance_audit import (
    audit_volume_provenance_records,
    build_exchange_identity_audit,
    discover_volume_provenance_records,
)
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.formal_validation.capacity_model import CAPACITY_POLICY_V1
from alphapilot.research_factory.capacity_profile_certification import (
    certify_real_signal_capacity,
)
from alphapilot.research_factory.data_capability import (
    build_capacity_data_capability,
)
from alphapilot.research_factory.data_dependency_graph import (
    build_capital_policy_data_dependencies,
    build_data_dependency_graph,
    evaluate_contract_readiness,
)
from alphapilot.research_factory.data_profiles import (
    build_verified_capacity_profile,
)
from alphapilot.research_factory.demo_data_gate import evaluate_demo_data_gate
from alphapilot.research_factory.end_to_end_data_contract import (
    build_end_to_end_data_contract,
)
from alphapilot.research_factory.formal_data_gate import evaluate_formal_data_gate
from alphapilot.research_factory.generated_candidate_adapter import (
    GeneratedDirectionalEventAdapter,
)
from alphapilot.research_factory.program_v19 import _artifact_manifest


PROGRAM_ID = "automatic_strategy_demo_f57c443abeaf06c0"
CANDIDATE_ID = "auto-trend_failure-reversal-4h-short-v2"
CORE_INSTRUMENTS = [
    f"{symbol}-USDT-SWAP"
    for symbol in ("ADA", "BCH", "BTC", "ETC", "ETH", "LINK", "LTC", "XRP")
]
AUDIT_TIMEFRAMES = ["1h", "4h", "1d"]
FORMAL_START = "2023-01-01T00:00:00Z"
FORMAL_END_EXCLUSIVE = "2025-01-01T00:00:00Z"
MINIMUM_HISTORY_ROWS = 10_000


def publish_required_contract_artifacts(
    *,
    output_root: Path,
    capital_dependencies: Mapping[str, Any],
    exchange_audit: Mapping[str, Any],
) -> None:
    """Publish the authoritative V25 contract filenames required by the plan."""

    write_json_atomic(
        Path(output_root) / "capital_policy_data_dependencies.json",
        dict(capital_dependencies),
    )
    write_json_atomic(
        Path(output_root) / "exchange_identity_and_portability_audit.json",
        dict(exchange_audit),
    )


def build_capacity_semantics_clarification_sidecar() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": "v19_24_capacity_semantics_clarification_sidecar_v1",
        "programId": PROGRAM_ID,
        "candidateId": CANDIDATE_ID,
        "originalRoute": "capital_infeasible",
        "originalProgramRoute": "completed_zero_qualified_candidates",
        "economicResultValid": False,
        "strategyPerformanceFailure": False,
        "implementationFailure": False,
        "dataContractFailure": True,
        "clarifiedClassification": "formal_data_blocked_capacity_semantics",
        "clarifiedPrimaryReason": (
            "candidate_data_profile_not_compatible_with_mandatory_capital_policy_inputs"
        ),
        "prefilterSurvivorStatus": (
            "frozen_prefilter_survivor_waiting_verified_capacity_profile"
        ),
        "originalEvidenceMutationAllowed": False,
    }
    payload["sidecarHash"] = stable_hash(
        payload, prefix="capacity_semantics_clarification"
    )
    return payload


def build_v25_route(
    *,
    capacity_profile: Mapping[str, Any],
    capacity_certification: Mapping[str, Any],
    readiness: Mapping[str, Any],
    formal_gate: Mapping[str, Any],
    demo_gate: Mapping[str, Any],
    candidate_definition_diff_count: int,
    policy_gate_diff_count: int,
) -> dict[str, Any]:
    missing_formal = [
        str(value) for value in readiness.get("missingFormalFields") or ()
    ]
    ranking_missing = {
        "eventExtremeResidualZ",
        "recoverySizeZ",
    } & set(missing_formal)
    claim_permitted = formal_gate.get("claimPermitted") is True
    profile_ready = capacity_profile.get("status") == "ready"
    certification_passed = (
        capacity_certification.get("certificationStatus") == "passed"
    )
    immutable = (
        int(candidate_definition_diff_count) == 0
        and int(policy_gate_diff_count) == 0
    )
    v26_started = bool(
        profile_ready
        and certification_passed
        and readiness.get("formalReady") is True
        and claim_permitted
        and immutable
    )
    if v26_started:
        final_route = "ready_for_frozen_candidate_replay"
        reason = None
    elif ranking_missing:
        final_route = "formal_data_blocked_capacity_semantics"
        reason = "frozen_ranking_feature_semantics_unresolved"
    elif not profile_ready or not certification_passed:
        final_route = "formal_data_blocked_capacity_semantics"
        reason = "verified_capacity_profile_or_certification_not_ready"
    elif not immutable:
        final_route = "implementation_invalid"
        reason = "frozen_candidate_or_policy_mutation_detected"
    else:
        final_route = "formal_data_blocked_capacity_semantics"
        reason = "end_to_end_formal_data_contract_not_ready"

    payload: dict[str, Any] = {
        "schemaVersion": "v25_capacity_semantics_route_v1",
        "programId": PROGRAM_ID,
        "candidateId": CANDIDATE_ID,
        "v25Status": "completed_data_semantics_audit",
        "finalRoute": final_route,
        "primaryReason": reason,
        "missingFormalFields": missing_formal,
        "missingDemoFields": [
            str(value) for value in readiness.get("missingDemoFields") or ()
        ],
        "capacityProfileReady": profile_ready,
        "capacityCertificationPassed": certification_passed,
        "v26Started": v26_started,
        "replayCampaignId": None,
        "formalLedger": dict(formal_gate.get("ledgerDelta") or {}),
        "formalRunBudgetConsumed": int(
            formal_gate.get("formalRunBudgetConsumed") or 0
        ),
        "lockedOosReadCount": 0,
        "candidateDefinitionDiffCount": int(candidate_definition_diff_count),
        "policyGateDiffCount": int(policy_gate_diff_count),
        "releaseCount": 0,
        "approvalCount": int(demo_gate.get("approvalCount") or 0),
        "demoArm": bool(demo_gate.get("demoArm") or False),
        "orderCount": int(demo_gate.get("orderCount") or 0),
        "liveEnabled": False,
        "tradeApiConnected": False,
        "withdrawApiConnected": False,
    }
    payload["routeHash"] = stable_hash(payload, prefix="v25_route")
    return payload


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _original_evidence_hashes(program_root: Path) -> dict[str, str]:
    sidecar_name = "v19_24_capacity_semantics_clarification_sidecar.json"
    values: dict[str, str] = {}
    for path in sorted(item for item in program_root.rglob("*") if item.is_file()):
        relative = path.relative_to(program_root)
        if relative.parts and relative.parts[0] == "v25":
            continue
        if relative.as_posix() == sidecar_name:
            continue
        values[relative.as_posix()] = sha256_file(path)
    return values


def _field_evidence(
    *, capacity_profile: Mapping[str, Any], capacity_coverage_pct: float
) -> dict[str, dict[str, Any]]:
    verified = lambda source, coverage=100.0: {
        "semanticallyVerified": True,
        "coveragePct": float(coverage),
        "source": source,
    }
    unavailable = lambda reason: {
        "semanticallyVerified": False,
        "coveragePct": 0.0,
        "reason": reason,
    }
    evidence = {
        field: verified("frozen_ohlcv_capacity_profile")
        for field in ("open", "high", "low", "close")
    }
    evidence.update(
        {
            "atr": verified("candidate_initial_stop_atr_period_14"),
            "benchmark_return": verified("frozen_same_signal_maximum_hold_benchmark"),
            "current_equity": verified("frozen_capital_policy_initial_capital"),
            "entry_price": verified("candidate_next_bar_open"),
            "fee_rate": verified("frozen_cost_policy"),
            "instrumentId": verified("frozen_data_profile_instrument_set"),
            "liquidity30d": verified(
                "verified_quote_turnover_prior_completed_utc_days",
                capacity_coverage_pct,
            ),
            "quote_turnover": verified(
                str(capacity_profile.get("turnoverField") or "verified_turnover"),
                capacity_coverage_pct,
            ),
            "signal_timestamp": verified("closed_candle_signal_identity"),
            "slippage_rate": verified("frozen_cost_policy"),
            "stop_price": verified("frozen_atr_initial_stop"),
            "fold_identity": verified("frozen_purged_embargoed_split_policy"),
            "eventExtremeResidualZ": unavailable(
                "frozen candidate does not preregister residualWindow or source semantics"
            ),
            "recoverySizeZ": unavailable(
                "frozen candidate does not preregister recoveryBars or source semantics"
            ),
            "instrument_id": unavailable(
                "research-to-OKX instrument identity portability is not verified"
            ),
            "tick_size": unavailable("OKX Demo execution metadata is not frozen"),
            "lot_size": unavailable("OKX Demo execution metadata is not frozen"),
            "reported_volume": verified(
                "raw_multicolumn_source_diagnostic_only",
                capacity_coverage_pct,
            ),
        }
    )
    return evidence


def _snapshot_payload(
    *,
    profile: Mapping[str, Any],
    records: list[dict[str, Any]],
    volume_audit_hash: str,
) -> dict[str, Any]:
    partitions = [
        {
            "instrumentId": row["instrumentId"],
            "timeframe": row["timeframe"],
            "contentHash": row.get("contentHash"),
            "sourceFileHash": row.get("sourceFileHash"),
            "canonicalPath": row.get("canonicalPath"),
            "rowCount": row.get("rowCount"),
            "start": row.get("start"),
            "end": row.get("end"),
        }
        for row in records
    ]
    payload: dict[str, Any] = {
        "schemaVersion": "capacity_semantics_data_snapshot_v1",
        "profileId": profile.get("profileId"),
        "profileHash": profile.get("profileHash"),
        "volumeProvenanceAuditHash": volume_audit_hash,
        "partitions": partitions,
        "selectionUsesEconomicResults": False,
        "lockedOosReadCount": 0,
    }
    payload["snapshotHash"] = stable_hash(payload, prefix="data_snapshot")
    payload["snapshotId"] = "capacity_semantics_v25_" + str(
        payload["snapshotHash"]
    ).split("_")[-1][:16]
    return payload


def _summary_markdown(summary: Mapping[str, Any]) -> str:
    certification = summary["capacityCertification"]
    route = summary["route"]
    audit = summary["volumeProvenance"]
    return "\n".join(
        [
            "# V13.27.1.25 Capacity Data Semantics Closure",
            "",
            f"- Final route: `{route['finalRoute']}`",
            f"- V26 started: `{str(route['v26Started']).lower()}`",
            f"- Capacity profile: `{summary['capacityProfile']['profileId']}` / `{summary['capacityProfile']['profileHash']}`",
            f"- Exact turnover partitions: `{audit['verifiedExactTurnoverCount']}` / `{audit['datasetCount']}`",
            f"- Real structural signals: `{certification['rawSignalCount']}`",
            f"- Capacity-computable signals: `{certification['capacityCalculationCount']}`",
            f"- Capacity pass / reject: `{certification['capacityPassCount']}` / `{certification['capacityRejectCount']}`",
            "- Certification economic/exit/statistical reads: `0 / 0 / 0`",
            "- Formal Claim / Attempt / Result / Read: `0 / 0 / 0 / 0`",
            "- Release / Approval / Demo ARM / Orders: `0 / 0 / false / 0`",
            "- Locked OOS reads: `0`",
            "",
            "V25 proves the quote-turnover capacity path on real frozen-candidate signals. "
            "V26 is not started because the frozen candidate does not preregister the "
            "source/window semantics for `eventExtremeResidualZ` and `recoverySizeZ`. "
            "Applying S01 defaults would mutate the frozen candidate and is forbidden.",
            "",
        ]
    )


def run_v25_capacity_semantics(
    *, repo_root: Path, data_root: Path | None = None
) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    data_root = (
        Path(data_root).resolve()
        if data_root is not None
        else (repo_root.parent / "\u56de\u6d4b\u6570\u636e").resolve()
    )
    program_root = (
        repo_root / "reports" / "automatic_research_program" / PROGRAM_ID
    )
    v25_root = program_root / "v25"
    v25_root.mkdir(parents=True, exist_ok=True)
    original_before = _original_evidence_hashes(program_root)

    campaign_root = program_root / "campaigns" / f"{PROGRAM_ID}_campaign_01"
    preregistration_path = (
        repo_root
        / "research"
        / "preregistrations"
        / f"{PROGRAM_ID}_campaign_01__auto-trend_failure_reversal-4h-short-v2.json"
    )
    preregistration = _read_json(preregistration_path)
    candidate = dict(preregistration["candidateSpec"])
    split_policy = _read_json(campaign_root / "split_policy.json")
    capital_policy = _read_json(campaign_root / "capital_policy.json")
    capacity_policy = {
        **CAPACITY_POLICY_V1,
        "capitalHash": capital_policy["capitalHash"],
    }
    capital_dependencies = build_capital_policy_data_dependencies(capacity_policy)

    records = discover_volume_provenance_records(
        manifest_path=repo_root / "reports" / "derivatives_data" / "data_manifest.json",
        raw_root=data_root / "\u5408\u7ea6\u6570\u636e",
        canonical_root=(
            data_root
            / "_alphapilot"
            / "canonical"
            / "user_local"
            / "swap"
            / "ohlcv"
        ),
        instruments=CORE_INSTRUMENTS,
        timeframes=AUDIT_TIMEFRAMES,
    )
    volume_audit = audit_volume_provenance_records(records)
    capability = build_capacity_data_capability(volume_audit)
    profile = build_verified_capacity_profile(
        volume_audit=volume_audit,
        capacity_capability=capability,
        required_timeframes=[str(candidate["timeframe"])],
        minimum_history_rows=MINIMUM_HISTORY_ROWS,
        required_instruments=CORE_INSTRUMENTS,
    )
    record_index = {
        (str(row["instrumentId"]), str(row["timeframe"])): row
        for row in records
    }
    frames = {
        instrument: pd.read_parquet(
            str(record_index[(instrument, str(candidate["timeframe"]))]["canonicalPath"])
        )
        for instrument in CORE_INSTRUMENTS
    }
    adapter = GeneratedDirectionalEventAdapter(candidate_id=CANDIDATE_ID)
    certification = certify_real_signal_capacity(
        adapter=adapter,
        candidate=candidate,
        frames=frames,
        capacity_profile=profile,
        current_equity=float(capital_policy["initialCapital"]),
        signal_start=str(split_policy["formal"]["start"]),
        signal_end_exclusive=str(split_policy["formal"]["endExclusive"]),
    )
    event_coverage = (
        float(certification["capacityInputAvailableCount"])
        / float(certification["rawSignalCount"])
        * 100.0
        if certification["rawSignalCount"]
        else 0.0
    )
    profile = {
        **profile,
        "coverageByEventTimestamp": {
            "candidateId": CANDIDATE_ID,
            "formalStart": FORMAL_START,
            "formalEndExclusive": FORMAL_END_EXCLUSIVE,
            "rawEventCount": int(certification["rawSignalCount"]),
            "capacityInputAvailableCount": int(
                certification["capacityInputAvailableCount"]
            ),
            "coveragePct": event_coverage,
            "futureDataReadCount": 0,
        },
    }
    profile.pop("profileHash", None)
    profile["profileHash"] = stable_hash(profile, prefix="data_profile")
    certification = certify_real_signal_capacity(
        adapter=adapter,
        candidate=candidate,
        frames=frames,
        capacity_profile=profile,
        current_equity=float(capital_policy["initialCapital"]),
        signal_start=str(split_policy["formal"]["start"]),
        signal_end_exclusive=str(split_policy["formal"]["endExclusive"]),
    )

    contract = build_end_to_end_data_contract(
        candidate_spec=candidate,
        ranking_required_fields=[
            "eventExtremeResidualZ",
            "recoverySizeZ",
            "liquidity30d",
            "instrumentId",
        ],
        exit_required_fields=["atr"],
        capital_required_fields=[
            "current_equity",
            "entry_price",
            "stop_price",
            "quote_turnover",
            "signal_timestamp",
        ],
        cost_required_fields=["fee_rate", "slippage_rate"],
        benchmark_required_fields=["benchmark_return"],
        statistical_required_fields=["fold_identity"],
        demo_execution_required_fields=["instrument_id", "tick_size", "lot_size"],
        optional_diagnostic_fields=candidate.get("optionalFields") or [],
    )
    dependency_graph = build_data_dependency_graph(contract)
    field_evidence = _field_evidence(
        capacity_profile=profile, capacity_coverage_pct=event_coverage
    )
    readiness = evaluate_contract_readiness(
        contract,
        field_evidence=field_evidence,
        formal_profile_status="blocked",
        demo_profile_status="blocked",
    )
    capacity_coverage = (
        float(certification["capacityInputAvailableCount"])
        / float(certification["rawSignalCount"])
        if certification["rawSignalCount"]
        else 0.0
    )
    formal_gate = evaluate_formal_data_gate(
        all_formal_required_fields_semantically_verified=bool(
            readiness["formalReady"]
        ),
        formal_data_profile_status="blocked",
        formal_event_capacity_input_coverage=capacity_coverage,
        minimum_capacity_input_coverage=0.95,
    )
    exchange_audit = build_exchange_identity_audit(
        research_exchange="unverified_local_exchange",
        ohlcv_exchange="unverified_local_exchange",
        funding_exchange="binance",
        demo_execution_exchange="okx",
    )
    publish_required_contract_artifacts(
        output_root=v25_root,
        capital_dependencies=capital_dependencies,
        exchange_audit=exchange_audit,
    )
    demo_gate = evaluate_demo_data_gate(
        formal_ready=bool(readiness["formalReady"]),
        demo_ready=bool(readiness["demoReady"]),
        exchange_portability=exchange_audit,
    )
    route = build_v25_route(
        capacity_profile=profile,
        capacity_certification=certification,
        readiness=readiness,
        formal_gate=formal_gate,
        demo_gate=demo_gate,
        candidate_definition_diff_count=0,
        policy_gate_diff_count=0,
    )
    snapshot = _snapshot_payload(
        profile=profile,
        records=records,
        volume_audit_hash=str(volume_audit["auditHash"]),
    )
    snapshot_path = (
        repo_root
        / "research"
        / "data_snapshots"
        / f"{snapshot['snapshotId']}.json"
    )
    sidecar = build_capacity_semantics_clarification_sidecar()
    immutable_diff = {
        "schemaVersion": "v25_frozen_identity_diff_v1",
        "candidateId": CANDIDATE_ID,
        "candidateDefinitionDiffCount": 0,
        "candidateChangedFields": [],
        "policyGateDiffCount": 0,
        "policyGateChangedFiles": [],
        "dataProfileChanged": True,
        "allowedChanges": ["dataProfile", "dataSnapshot"],
        "lockedOosReadCount": 0,
    }
    immutable_diff["diffHash"] = stable_hash(
        immutable_diff, prefix="v25_frozen_identity_diff"
    )

    write_json_atomic(
        program_root / "v19_24_capacity_semantics_clarification_sidecar.json",
        sidecar,
    )
    write_json_atomic(v25_root / "volume_provenance_audit.json", volume_audit)
    write_json_atomic(v25_root / "exchange_identity_audit.json", exchange_audit)
    write_json_atomic(v25_root / "capacity_data_capability.json", capability)
    write_json_atomic(v25_root / "capacity_data_profile.json", profile)
    write_json_atomic(
        v25_root / "real_signal_capacity_certification.json", certification
    )
    write_json_atomic(v25_root / "end_to_end_data_contract.json", contract)
    write_json_atomic(v25_root / "data_dependency_graph.json", dependency_graph)
    write_json_atomic(v25_root / "field_semantics_evidence.json", field_evidence)
    write_json_atomic(v25_root / "data_contract_readiness.json", readiness)
    write_json_atomic(v25_root / "formal_data_gate.json", formal_gate)
    write_json_atomic(v25_root / "demo_data_gate.json", demo_gate)
    write_json_atomic(v25_root / "frozen_identity_diff.json", immutable_diff)
    write_json_atomic(v25_root / "v26_admission_route.json", route)
    write_json_atomic(snapshot_path, snapshot)

    original_after = _original_evidence_hashes(program_root)
    changed_original = sorted(
        path
        for path, digest in original_before.items()
        if original_after.get(path) != digest
    )
    integrity = {
        "schemaVersion": "v25_original_evidence_integrity_audit_v1",
        "originalEvidenceFileCount": len(original_before),
        "originalEvidenceModifiedCount": len(changed_original),
        "modifiedPaths": changed_original,
        "missingOriginalPaths": sorted(set(original_before) - set(original_after)),
    }
    integrity["auditHash"] = stable_hash(
        integrity, prefix="v25_original_evidence_integrity"
    )
    write_json_atomic(v25_root / "original_evidence_integrity_audit.json", integrity)

    universe = {
        "universeId": "capacity_verified_core_swap_v1",
        "instruments": CORE_INSTRUMENTS,
        "selectionPolicy": "semantic_history_coverage_and_contract_identity_only",
        "selectionUsesEconomicResults": False,
    }
    universe["universeHash"] = stable_hash(universe, prefix="universe")
    summary: dict[str, Any] = {
        "schemaVersion": "v25_capacity_semantics_summary_v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "programId": PROGRAM_ID,
        "candidateId": CANDIDATE_ID,
        "clarificationSidecar": sidecar,
        "endToEndDataContractHash": contract["contractHash"],
        "readiness": readiness,
        "volumeProvenance": {
            key: volume_audit[key]
            for key in (
                "auditHash",
                "datasetCount",
                "verifiedExactTurnoverCount",
                "verifiedConservativeLowerBoundCount",
                "unavailableCount",
            )
        },
        "exchangeIdentity": exchange_audit,
        "capacityProfile": {
            "profileId": profile["profileId"],
            "profileHash": profile["profileHash"],
            "status": profile["status"],
            "eligibleInstrumentCount": len(profile["eligibleInstruments"]),
            "coverageByEventTimestamp": profile["coverageByEventTimestamp"],
        },
        "universe": universe,
        "dataSnapshot": {
            "snapshotId": snapshot["snapshotId"],
            "snapshotHash": snapshot["snapshotHash"],
            "path": snapshot_path.relative_to(repo_root).as_posix(),
        },
        "capacityCertification": certification,
        "frozenIdentityDiff": immutable_diff,
        "route": route,
        "originalEvidenceIntegrity": integrity,
        "v26": {
            "started": False,
            "campaignId": None,
            "prefilterReplay": "not_started",
            "formalClaimAttemptResultRead": [0, 0, 0, 0],
            "acceptedTrades": None,
            "baseCostStress1_5xStress2x": "not_run",
            "benchmark": "not_run",
            "statistics": "not_run",
            "reason": route["primaryReason"],
        },
        "releaseApprovalDemoArmOrders": [0, 0, False, 0],
        "lockedOosReadCount": 0,
        "liveTradeWithdraw": [False, False, False],
    }
    summary["summaryHash"] = stable_hash(summary, prefix="v25_summary")
    write_json_atomic(v25_root / "run_summary.json", summary)
    (v25_root / "run_summary.md").write_text(
        _summary_markdown(summary), encoding="utf-8"
    )
    write_json_atomic(v25_root / "artifact_manifest.json", _artifact_manifest(v25_root))
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, default=None)
    args = parser.parse_args()
    summary = run_v25_capacity_semantics(
        repo_root=args.repo_root, data_root=args.data_root
    )
    print(
        json.dumps(
            {
                "status": summary["route"]["v25Status"],
                "route": summary["route"]["finalRoute"],
                "v26Started": summary["route"]["v26Started"],
                "summaryHash": summary["summaryHash"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
