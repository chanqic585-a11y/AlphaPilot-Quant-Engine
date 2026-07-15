"""Generate the V13.27.1.11 public-data readiness evidence bundle."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import urllib.error
import urllib.request
from collections import Counter
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.derivatives_data.api_capability_audit import (
    build_default_capability_audit,
)
from alphapilot.derivatives_data.data_readiness_v2 import evaluate_v2_data_readiness
from alphapilot.derivatives_data.environment_manifest import build_environment_manifest
from alphapilot.evolution.registry.hashing import stable_hash


PUBLIC_PROBE_URLS = (
    "https://www.okx.com/api/v5/public/time",
    "https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP",
    "https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=1",
    "https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT-SWAP&bar=1H&limit=1",
    "https://fapi.binance.com/fapi/v1/time",
    "https://fapi.binance.com/futures/data/openInterestHist?symbol=BTCUSDT&period=1h&limit=1",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_sha(path: Path) -> Path:
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(f"{_sha256(path)}  {path.name}\n", encoding="ascii")
    return sidecar


def _write_json(path: Path, payload: Any) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_sha(path)
    return path


def _flat_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple, set)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_table(path_stem: Path, rows: list[dict[str, Any]], *, parquet_allowed: bool) -> dict[str, str]:
    fields = sorted({field for row in rows for field in row})
    csv_path = path_stem.with_suffix(".csv")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        if fields:
            writer.writeheader()
            for row in rows:
                writer.writerow({field: _flat_value(row.get(field)) for field in fields})
    _write_sha(csv_path)
    outputs = {"csv": str(csv_path), "csvSha256": _sha256(csv_path)}
    if parquet_allowed:
        parquet_path = path_stem.with_suffix(".parquet")
        frame = pd.DataFrame(
            [{field: _flat_value(row.get(field)) for field in fields} for row in rows],
            columns=fields,
        )
        frame.to_parquet(parquet_path, index=False, engine="pyarrow")
        _write_sha(parquet_path)
        outputs.update(
            {"parquet": str(parquet_path), "parquetSha256": _sha256(parquet_path)}
        )
    return outputs


def _default_public_probe(url: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"User-Agent": "AlphaPilot-public-data-audit/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            payload = json.loads(body)
            return {
                "url": url,
                "ok": 200 <= response.status < 300,
                "statusCode": response.status,
                "responseBytes": len(body),
                "responseSha256": hashlib.sha256(body).hexdigest(),
                "topLevelType": type(payload).__name__,
                "topLevelKeys": sorted(payload) if isinstance(payload, dict) else [],
            }
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        return {
            "url": url,
            "ok": False,
            "statusCode": None,
            "errorType": type(exc).__name__,
            "error": str(exc)[:300],
        }


def _verify_catalog(catalog: Mapping[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    verified: list[dict[str, Any]] = []
    errors: list[str] = []
    for dataset in catalog.get("datasets", []):
        row = dict(dataset)
        source = Path(str(row.get("sourcePath") or ""))
        exists = source.is_file()
        actual_hash = _sha256(source) if exists else None
        expected_hash = row.get("contentHash")
        hash_matches = exists and actual_hash == expected_hash
        row.update(
            {
                "sourceExists": exists,
                "actualContentHash": actual_hash,
                "contentHashMatches": hash_matches,
            }
        )
        if not exists:
            errors.append(f"missing:{row.get('datasetId')}")
        elif not hash_matches:
            errors.append(f"hash_mismatch:{row.get('datasetId')}")
        verified.append(row)
    return verified, errors


def _direction_evidence(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    data_types = {str(row.get("dataType")) for row in rows if row.get("sourceExists")}
    verified_ohlcv_exchanges = {
        str(row.get("exchange"))
        for row in rows
        if row.get("dataType") == "ohlcv"
        and row.get("sourceExists")
        and row.get("contentHashMatches")
        and not row.get("isProxy")
        and not str(row.get("exchange", "")).startswith("unverified")
    }
    funding_exchanges = {
        str(row.get("exchange"))
        for row in rows
        if row.get("dataType") == "funding"
        and row.get("sourceExists")
        and row.get("contentHashMatches")
        and not row.get("isProxy")
    }
    oi_exchanges = {
        str(row.get("exchange"))
        for row in rows
        if row.get("dataType") == "open_interest"
        and row.get("sourceExists")
        and row.get("contentHashMatches")
        and not row.get("isProxy")
    }
    basis_exchanges = {
        str(row.get("exchange"))
        for row in rows
        if row.get("dataType") == "basis"
        and row.get("sourceExists")
        and row.get("contentHashMatches")
        and not row.get("isProxy")
    }
    same_exchange_b = sorted(
        verified_ohlcv_exchanges & funding_exchanges & oi_exchanges & basis_exchanges
    )
    liquidation_exchanges = {
        str(row.get("exchange"))
        for row in rows
        if row.get("dataType") == "liquidation"
        and row.get("sourceExists")
        and row.get("contentHashMatches")
        and not row.get("isProxy")
    }
    same_exchange_a1 = sorted(
        verified_ohlcv_exchanges
        & funding_exchanges
        & oi_exchanges
        & liquidation_exchanges
    )
    same_exchange_a2 = sorted(
        verified_ohlcv_exchanges & funding_exchanges & oi_exchanges
    )
    has_pit_universe = all(
        required in data_types
        for required in (
            "pit_tradability",
            "pit_liquidity",
            "listing_delisting",
            "historical_contract_universe",
        )
    )
    has_proxy_ohlcv = any(row.get("dataType") == "ohlcv" for row in rows)
    return {
        "A1": {
            "formalReady": bool(same_exchange_a1),
            "provisionalReady": False,
            "maximumOutcome": "formal_research_pass",
            "sameExchangeCandidates": same_exchange_a1,
            "missing": [
                name
                for name, present in (
                    ("verifiedSameExchangeOhlcv", bool(verified_ohlcv_exchanges)),
                    ("historicalFunding", bool(funding_exchanges)),
                    ("historicalOpenInterest", bool(oi_exchanges)),
                    ("realLiquidation", bool(liquidation_exchanges)),
                    ("sameExchangeCoreFields", bool(same_exchange_a1)),
                )
                if not present
            ],
        },
        "A2": {
            "formalReady": False,
            "provisionalReady": bool(same_exchange_a2),
            "diagnosticReady": has_proxy_ohlcv,
            "maximumOutcome": "provisional_research_pass",
            "sameExchangeCandidates": same_exchange_a2,
            "missing": [
                name
                for name, present in (
                    ("verifiedSameExchangeOhlcv", bool(verified_ohlcv_exchanges)),
                    ("historicalFunding", bool(funding_exchanges)),
                    ("historicalOpenInterest", bool(oi_exchanges)),
                    ("sameExchangeCoreFields", bool(same_exchange_a2)),
                    ("realLiquidation", False),
                )
                if not present
            ],
        },
        "B": {
            "formalReady": bool(same_exchange_b),
            "provisionalReady": False,
            "maximumOutcome": "formal_research_pass",
            "sameExchangeCandidates": same_exchange_b,
            "missing": []
            if same_exchange_b
            else [
                "sameExchangeVerifiedPerpetualOhlcv",
                "sameExchangeHistoricalFunding",
                "sameExchangeHistoricalOpenInterest",
                "sameExchangeHistoricalSpotPerpetualBasis",
            ],
        },
        "C": {
            "formalReady": has_pit_universe,
            "provisionalReady": False,
            "diagnosticReady": has_proxy_ohlcv,
            "maximumOutcome": "formal_research_pass",
            "missing": []
            if has_pit_universe
            else [
                "pitTradability",
                "pitLiquidity",
                "listingDelisting",
                "historicalContractUniverse",
            ],
        },
    }


def _write_markdown_summary(path: Path, readiness: Mapping[str, Any]) -> None:
    lines = [
        "# V13.27.1.11 Data Readiness",
        "",
        f"- Status: `{readiness['status']}`",
        f"- Formal ready directions: `{readiness['formalReadyDirectionCount']}` / `2` required",
        f"- Campaign may run: `{str(readiness['campaignMayRun']).lower()}`",
        "- Decision: public-data evidence is committed; no campaign or holdout is run when data is not ready.",
        "",
        "## Direction Gaps",
        "",
    ]
    for direction, record in readiness["directions"].items():
        missing = ", ".join(record.get("missing", [])) or "none"
        lines.append(f"- `{direction}`: formal={record.get('formalReady', False)}; missing={missing}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    _write_sha(path)


def generate_data_readiness_reports(
    *,
    repo_root: Path,
    external_data_root: Path,
    checked_at: str,
    command_output: Callable[[str, Path | None], str],
    python_executable: str,
    public_probe: Callable[[str], Mapping[str, Any]] = _default_public_probe,
    free_disk_bytes: int | None = None,
) -> dict[str, Any]:
    report_root = repo_root / "reports" / "derivatives_data"
    environment_path = repo_root / "reports" / "reproducibility" / "environment_manifest.json"
    catalog_path = external_data_root / "manifests" / "phase3b_dataset_catalog.json"
    source_audit_path = external_data_root / "manifests" / "phase3b_data_source_audit.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    source_audit = json.loads(source_audit_path.read_text(encoding="utf-8"))
    verified_rows, source_errors = _verify_catalog(catalog)

    environment = build_environment_manifest(
        repo_paths={"quant": repo_root},
        dependency_lock_path=repo_root / "requirements-data.txt",
        command_output=command_output,
        python_executable=python_executable,
        random_seeds=(13, 27, 111),
    )
    _write_json(environment_path, environment)
    parquet_allowed = bool(environment["parquetPolicy"]["allowed"])

    api_audit = build_default_capability_audit(checked_at=checked_at)
    probes = [dict(public_probe(url)) for url in PUBLIC_PROBE_URLS]
    api_audit = {**api_audit, "livePublicProbes": probes}
    _write_json(report_root / "api_capability_audit.json", api_audit)
    api_outputs = _write_table(
        report_root / "api_capability_audit",
        list(api_audit["capabilities"]),
        parquet_allowed=parquet_allowed,
    )

    source_registry = {
        "schemaVersion": "derivatives_data_source_registry_v2",
        "checkedAt": checked_at,
        "externalCatalogPath": str(catalog_path),
        "externalCatalogHash": _sha256(catalog_path),
        "externalCatalogDeclaredHash": catalog.get("dataManifestHash"),
        "sources": verified_rows,
        "sourceErrors": source_errors,
    }
    source_registry["registryHash"] = stable_hash(source_registry, prefix="data_source_registry")
    _write_json(report_root / "data_source_registry.json", source_registry)
    registry_outputs = _write_table(
        report_root / "data_source_registry",
        verified_rows,
        parquet_allowed=parquet_allowed,
    )

    data_manifest = {
        "schemaVersion": "v13_27_1_11_data_manifest_v2",
        "checkedAt": checked_at,
        "sourceCatalogHash": _sha256(catalog_path),
        "sourceAuditHash": _sha256(source_audit_path),
        "sourceFileCount": len(verified_rows),
        "sourceHashMismatchCount": len(source_errors),
        "allSourcesVerified": not source_errors,
        "datasets": verified_rows,
    }
    data_manifest["dataManifestHash"] = stable_hash(data_manifest, prefix="data_manifest")
    _write_json(report_root / "data_manifest.json", data_manifest)
    manifest_outputs = _write_table(
        report_root / "data_manifest",
        verified_rows,
        parquet_allowed=parquet_allowed,
    )

    duplicate_ids = [
        key for key, count in Counter(str(row.get("datasetId")) for row in verified_rows).items() if count > 1
    ]
    duplicate_paths = [
        key for key, count in Counter(str(row.get("sourcePath")) for row in verified_rows).items() if count > 1
    ]
    deduplication = {
        "schemaVersion": "derivatives_deduplication_report_v2",
        "status": "scanned_existing_manifest_no_new_collection",
        "primaryKey": ["exchange", "instrumentId", "dataType", "timestampUtc"],
        "datasetCount": len(verified_rows),
        "duplicateDatasetIds": duplicate_ids,
        "duplicateSourcePaths": duplicate_paths,
        "rowLevelDeduplicationStatus": "not_applicable_no_new_rows_staged",
        "userDataModified": False,
    }
    _write_json(report_root / "deduplication_report.json", deduplication)

    direction_evidence = _direction_evidence(verified_rows)
    readiness = evaluate_v2_data_readiness(direction_evidence)
    readiness.update(
        {
            "checkedAt": checked_at,
            "exchangeChoiceReason": api_audit["exchangeDecision"]["reason"],
            "sameExchangeCoreDataPassed": False,
            "sourceCatalogVerified": not source_errors,
            "sourceAudit": source_audit,
        }
    )
    _write_json(report_root / "data_readiness.json", readiness)
    readiness_rows = [
        {"direction": direction, **record}
        for direction, record in readiness["directions"].items()
    ]
    readiness_outputs = _write_table(
        report_root / "data_readiness",
        readiness_rows,
        parquet_allowed=parquet_allowed,
    )
    _write_markdown_summary(report_root / "data_readiness.md", readiness)

    missing_by_direction = {
        direction: record.get("missing", [])
        for direction, record in readiness["directions"].items()
    }
    gap_repair = {
        "schemaVersion": "derivatives_gap_repair_report_v2",
        "status": "not_started_data_capability_stop",
        "repairAttempted": False,
        "repairPolicy": "scan_existing_then_repair_explicit_gaps_only",
        "unresolvedFormalEvidence": missing_by_direction,
        "userDataModified": False,
        "reason": "no single public exchange source can fill the formal historical evidence gaps",
    }
    _write_json(report_root / "gap_repair_report.json", gap_repair)

    budget = {
        "maximumRequestsPerMinute": 30,
        "maximumRetries": 3,
        "maximumDownloadBytes": 5_000_000_000,
        "minimumFreeDiskBytes": 20_000_000_000,
    }
    disk_free = free_disk_bytes
    if disk_free is None:
        disk_free = shutil.disk_usage(external_data_root).free
    download_resume = {
        "schemaVersion": "download_resume_manifest_v2",
        "status": "no_download_started_due_data_capability_stop",
        "collectorImplementationAvailable": True,
        "checkpointCount": 0,
        "lastVerifiedCursor": None,
        "budgets": budget,
        "livePublicProbes": probes,
        "userDataDeleted": False,
        "userDataModified": False,
    }
    _write_json(report_root / "download_resume_manifest.json", download_resume)

    environment_limit = {
        "schemaVersion": "environment_limit_audit_v2",
        "checkedAt": checked_at,
        "freeDiskBytes": disk_free,
        "minimumFreeDiskBytes": budget["minimumFreeDiskBytes"],
        "minimumFreeDiskPassed": disk_free >= budget["minimumFreeDiskBytes"],
        "pyarrowLocked": environment["parquetPolicy"]["allowed"],
        "dockerCliAvailable": environment.get("dockerVersion") is not None,
        "dockerImageAvailable": environment.get("dockerImageDigest") is not None,
        "campaignBlockedByDataReadiness": not readiness["campaignMayRun"],
    }
    _write_json(report_root / "environment_limit_audit.json", environment_limit)

    data_audit = {
        "schemaVersion": "v13_27_1_11_data_audit_v2",
        "status": readiness["status"],
        "sourceFileCount": len(verified_rows),
        "sourceHashMismatchCount": len(source_errors),
        "dataTypeCounts": dict(Counter(str(row.get("dataType")) for row in verified_rows)),
        "exchangeCounts": dict(Counter(str(row.get("exchange")) for row in verified_rows)),
        "formalReadyDirectionCount": readiness["formalReadyDirectionCount"],
        "sameExchangeCoreDataPassed": False,
        "proxyFieldsNeverPromotedToFormal": True,
        "knownBlockingEvidence": missing_by_direction,
    }
    data_audit["auditHash"] = stable_hash(data_audit, prefix="data_audit")
    _write_json(report_root / "data_audit.json", data_audit)

    exchange_alignment = {
        "schemaVersion": "derivatives_exchange_alignment_v2",
        "checkedAt": checked_at,
        "preferredExchange": "OKX",
        "fallbackExchangeBeforePreregistration": "Binance",
        "selectedFormalExchange": None,
        "sameExchangeCoreDataRequired": True,
        "crossExchangeCoreFieldSplicingAllowed": False,
        "formalAlignmentPassed": False,
        "directions": {
            direction: {
                "formalReady": record.get("formalReady", False),
                "sameExchangeCandidates": record.get("sameExchangeCandidates", []),
                "missing": record.get("missing", []),
            }
            for direction, record in direction_evidence.items()
        },
        "decision": "no_exchange_selected_fewer_than_two_formal_directions",
    }
    exchange_alignment["alignmentHash"] = stable_hash(
        exchange_alignment, prefix="exchange_alignment"
    )
    _write_json(report_root / "exchange_alignment.json", exchange_alignment)

    pit_universe = {
        "schemaVersion": "pit_universe_manifest_v2",
        "checkedAt": checked_at,
        "status": "unavailable_for_formal_research",
        "formalEligible": False,
        "currentTopNBackfillAllowedForFormal": False,
        "requiredFields": [
            "pitTradability",
            "pitLiquidity",
            "listingDelisting",
            "historicalContractUniverse",
        ],
        "availableFields": [],
        "missingFields": direction_evidence["C"]["missing"],
        "maximumOutcome": "diagnostic_only",
        "reason": (
            "The frozen catalog has no historical point-in-time membership, listing, "
            "delisting and liquidity-state evidence."
        ),
    }
    pit_universe["manifestHash"] = stable_hash(
        pit_universe, prefix="pit_universe_manifest"
    )
    _write_json(report_root / "pit_universe_manifest.json", pit_universe)

    stop_decision = {
        "schemaVersion": "v13_27_1_11_campaign_stop_decision_v2",
        "checkedAt": checked_at,
        "status": readiness["status"],
        "reason": "fewer_than_two_formal_data_ready_directions",
        "formalReadyDirectionCount": readiness["formalReadyDirectionCount"],
        "minimumFormalDirectionCount": readiness["minimumFormalDirectionCount"],
        "campaignStarted": False,
        "preregistrationCreated": False,
        "holdoutUnlocked": False,
        "formalTrialsRun": 0,
        "formalPassEvidenceCreated": False,
        "consoleImported": False,
        "demoArmed": False,
        "ordersCreated": False,
        "nextAction": "obtain_same_exchange_historical_derivatives_and_pit_universe_evidence",
    }
    stop_decision["decisionHash"] = stable_hash(
        stop_decision, prefix="campaign_stop_decision"
    )
    stop_path = (
        repo_root
        / "reports"
        / "research_factory_repair"
        / "campaign_stop_decision.json"
    )
    _write_json(stop_path, stop_decision)

    snapshot_core = {
        "schemaVersion": "v13_27_1_11_data_snapshot_descriptor_v2",
        "createdAt": checked_at,
        "immutable": True,
        "campaignEligible": readiness["campaignMayRun"],
        "sourceCatalogHash": _sha256(catalog_path),
        "dataManifestHash": data_manifest["dataManifestHash"],
        "apiCapabilityAuditHash": api_audit["auditHash"],
        "environmentHash": environment["environmentHash"],
        "readinessHash": readiness["readinessHash"],
        "formalReadyDirectionCount": readiness["formalReadyDirectionCount"],
        "status": readiness["status"],
    }
    snapshot_id = stable_hash(snapshot_core, prefix="data_snapshot")
    snapshot = {**snapshot_core, "snapshotId": snapshot_id}
    snapshot_path = repo_root / "research" / "data_snapshots" / f"{snapshot_id}.json"
    _write_json(snapshot_path, snapshot)

    artifact_manifest = {
        "schemaVersion": "derivatives_data_artifact_manifest_v2",
        "status": readiness["status"],
        "artifacts": {
            "apiCapabilityAudit": api_outputs,
            "dataSourceRegistry": registry_outputs,
            "dataManifest": manifest_outputs,
            "dataReadiness": readiness_outputs,
            "dataReadinessSummary": {
                "markdown": str(report_root / "data_readiness.md"),
                "markdownSha256": _sha256(report_root / "data_readiness.md"),
            },
            "deduplicationReport": {
                "json": str(report_root / "deduplication_report.json"),
                "jsonSha256": _sha256(report_root / "deduplication_report.json"),
            },
            "gapRepairReport": {
                "json": str(report_root / "gap_repair_report.json"),
                "jsonSha256": _sha256(report_root / "gap_repair_report.json"),
            },
            "downloadResumeManifest": {
                "json": str(report_root / "download_resume_manifest.json"),
                "jsonSha256": _sha256(report_root / "download_resume_manifest.json"),
            },
            "environmentLimitAudit": {
                "json": str(report_root / "environment_limit_audit.json"),
                "jsonSha256": _sha256(report_root / "environment_limit_audit.json"),
            },
            "dataAudit": {
                "json": str(report_root / "data_audit.json"),
                "jsonSha256": _sha256(report_root / "data_audit.json"),
            },
            "exchangeAlignment": {
                "json": str(report_root / "exchange_alignment.json"),
                "jsonSha256": _sha256(report_root / "exchange_alignment.json"),
            },
            "pitUniverseManifest": {
                "json": str(report_root / "pit_universe_manifest.json"),
                "jsonSha256": _sha256(report_root / "pit_universe_manifest.json"),
            },
            "campaignStopDecision": {
                "json": str(stop_path),
                "jsonSha256": _sha256(stop_path),
            },
            "environmentManifest": {
                "json": str(environment_path),
                "jsonSha256": _sha256(environment_path),
            },
            "dataSnapshot": {
                "json": str(snapshot_path),
                "jsonSha256": _sha256(snapshot_path),
            },
        },
    }
    artifact_manifest["manifestHash"] = stable_hash(
        artifact_manifest, prefix="derivatives_data_artifact_manifest"
    )
    _write_json(report_root / "artifact_manifest.json", artifact_manifest)

    return {
        "status": readiness["status"],
        "campaignMayRun": readiness["campaignMayRun"],
        "formalReadyDirectionCount": readiness["formalReadyDirectionCount"],
        "sourceFileCount": len(verified_rows),
        "sourceHashMismatchCount": len(source_errors),
        "dataSnapshotPath": str(snapshot_path),
        "reportRoot": str(report_root),
    }
