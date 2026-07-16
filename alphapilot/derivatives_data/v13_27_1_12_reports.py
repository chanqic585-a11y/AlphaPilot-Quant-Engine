"""Publish the fail-closed V13.27.1.12 data-readiness closeout bundle."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


PUBLIC_PROBE_URLS = (
    "https://www.okx.com/api/v5/public/time",
    "https://www.okx.com/api/v5/public/open-interest?instType=SWAP&instId=BTC-USDT-SWAP",
    "https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=1",
    "https://www.okx.com/api/v5/market/history-candles?instId=BTC-USDT-SWAP&bar=1H&limit=1",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_sha256(path: Path) -> None:
    sidecar = path.with_name(path.name + ".sha256")
    sidecar.write_text(f"{_sha256(path)}  {path.name}\n", encoding="ascii", newline="\n")


def _write_json(path: Path, payload: Mapping[str, Any] | list[Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _read_required_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required stage evidence is missing: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"required stage evidence must be a JSON object: {path}")
    return payload


def _direction_status(formal_ready: bool, fallback: str) -> str:
    return "formal_ready" if formal_ready else fallback


def _summary_markdown(readiness: Mapping[str, Any], campaign: Mapping[str, Any]) -> str:
    blockers = readiness.get("blockers") or []
    lines = [
        "# AlphaPilot V13.27.1.12 Data Readiness",
        "",
        f"- Status: `{readiness['status']}`",
        f"- A1 stress reversal: `{readiness['A1Status']}`",
        f"- A2 stress proxy: `{readiness['A2Status']}`",
        f"- B short crowding unwind: `{readiness['BStatus']}`",
        f"- C cross-sectional momentum: `{readiness['CStatus']}`",
        f"- Formal top-level directions: `{readiness['formalTopLevelDirectionCount']}`",
        f"- Three-direction campaign may run: `{str(readiness['threeDirectionCampaignMayRun']).lower()}`",
        f"- Qlib campaign may run: `{str(readiness['qlibCampaignMayRun']).lower()}`",
        "",
        "## Fail-Closed Confirmation",
        "",
        f"- Strategy trials: `{campaign['strategyTrialCount']}`",
        f"- Holdout access: `{campaign['holdoutAccessCount']}`",
        f"- Releases: `{campaign['releaseCount']}`",
        f"- Demo ARM: `{campaign['demoArmCount']}`",
        f"- Orders: `{campaign['orderCount']}`",
        "",
        "## Blockers",
        "",
    ]
    lines.extend(f"- `{blocker}`" for blocker in blockers)
    lines.extend(
        [
            "",
            "## Next Action",
            "",
            str(readiness["nextAction"]),
            "",
            "No strategy campaign, model training, holdout read, release, Demo ARM, or order is part of this version.",
            "",
        ]
    )
    return "\n".join(lines)


def _artifact_manifest(report_root: Path, checked_at: str) -> dict[str, Any]:
    paths = sorted(
        path
        for path in report_root.iterdir()
        if path.is_file()
        and path.name != "artifact_manifest.json"
        and not path.name.endswith(".sha256")
        and path.suffix.lower() in {".json", ".csv", ".md"}
    )
    artifacts = [
        {
            "path": path.relative_to(report_root.parent.parent).as_posix(),
            "sha256": _sha256(path),
            "bytes": path.stat().st_size,
        }
        for path in paths
    ]
    core = {
        "schemaVersion": "v13_27_1_12_artifact_manifest_v1",
        "checkedAt": checked_at,
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
    }
    return {**core, "manifestHash": stable_hash(core, prefix="v13_27_1_12_manifest")}


def generate_v13_27_1_12_reports(
    *,
    repo_root: Path,
    data_root: Path,
    checked_at: str,
    probe: Callable[[str], Mapping[str, Any]],
) -> dict[str, Any]:
    """Read stage evidence and publish final decisions without running research."""

    report_root = repo_root / "reports" / "v13_27_1_12"
    family_b = _read_required_json(report_root / "family_b_data_chain.json")
    pit = _read_required_json(report_root / "pit_universe_audit.json")
    qlib_preflight = _read_required_json(report_root / "qlib_preflight.json")
    snapshot_manifest = _read_required_json(report_root / "snapshot_manifest.json")
    download_manifest = _read_required_json(report_root / "download_resume_manifest.json")

    snapshot = dict(snapshot_manifest.get("snapshot") or {})
    if snapshot.get("containsStrategyResults") or snapshot.get("containsHoldoutResults"):
        raise ValueError("the frozen snapshot is not data-only")

    a1_formal = False
    a2_formal = False
    b_formal = family_b.get("status") == "formal_ready" and bool(
        family_b.get("sameExchangeCoreChain")
    )
    c_formal = pit.get("status") == "formal_ready" and bool(
        pit.get("historicalFormalReady")
    )
    stress_formal = a1_formal or a2_formal
    momentum_formal = c_formal
    formal_count = sum((stress_formal, b_formal, momentum_formal))
    three_direction_may_run = formal_count >= 2
    qlib_may_run = bool(qlib_preflight.get("qlibCampaignMayRun")) and c_formal

    blockers = [
        "A1_real_liquidation_history_unavailable",
        "A2_proxy_not_formal_evidence",
    ]
    blockers.extend(
        f"B_missing_{data_type}" for data_type in family_b.get("missingDataTypes", [])
    )
    if not c_formal:
        blockers.append(str(pit.get("reason") or "C_historical_pit_unavailable"))
    blockers.extend(f"Qlib_{item}" for item in qlib_preflight.get("blockers", []))
    blockers = sorted(set(blockers))

    readiness = {
        "schemaVersion": "v13_27_1_12_data_readiness_v1",
        "checkedAt": checked_at,
        "status": "campaign_ready" if three_direction_may_run else "data_not_ready",
        "A1Status": _direction_status(a1_formal, "unavailable"),
        "A2Status": _direction_status(a2_formal, "unavailable"),
        "BStatus": _direction_status(b_formal, str(family_b.get("status") or "unavailable")),
        "CStatus": _direction_status(c_formal, str(pit.get("status") or "unavailable")),
        "stressReversalFormalReady": stress_formal,
        "shortCrowdingUnwindFormalReady": b_formal,
        "crossSectionalMomentumFormalReady": momentum_formal,
        "formalTopLevelDirectionCount": formal_count,
        "minimumFormalTopLevelDirectionCount": 2,
        "threeDirectionCampaignMayRun": three_direction_may_run,
        "qlibCampaignMayRun": qlib_may_run,
        "blockers": blockers,
        "nextAction": (
            "Continue append-only public collection and obtain a verifiable historical "
            "same-exchange derivatives chain plus historical PIT membership before any campaign."
        ),
        "thresholdsChanged": False,
        "currentTopNBackfillAllowedForFormalResearch": False,
        "missingValuesImputedAsZero": False,
    }
    readiness["readinessHash"] = stable_hash(readiness, prefix="v13_27_1_12_readiness")

    campaign = {
        "schemaVersion": "v13_27_1_12_campaign_start_decision_v1",
        "checkedAt": checked_at,
        "status": "allowed" if three_direction_may_run else "blocked",
        "threeDirectionCampaignMayRun": three_direction_may_run,
        "campaignStarted": False,
        "preregistrationCreated": False,
        "strategyTrialCount": 0,
        "holdoutAccessCount": 0,
        "holdoutUnlocked": False,
        "releaseCount": 0,
        "demoArmCount": 0,
        "orderCount": 0,
        "reason": None if three_direction_may_run else "fewer_than_two_formal_top_level_directions",
    }
    campaign["decisionHash"] = stable_hash(campaign, prefix="v13_27_1_12_campaign_decision")

    qlib_decision = {
        "schemaVersion": "v13_27_1_12_qlib_start_decision_v1",
        "checkedAt": checked_at,
        "status": "allowed" if qlib_may_run else "blocked",
        "qlibCampaignMayRun": qlib_may_run,
        "modelCampaignRun": False,
        "installationAttempted": False,
        "holdoutAccessCount": 0,
        "blockers": list(qlib_preflight.get("blockers", [])),
        "pinnedCommit": qlib_preflight.get("qlibCommit"),
    }
    qlib_decision["decisionHash"] = stable_hash(
        qlib_decision, prefix="v13_27_1_12_qlib_decision"
    )

    public_probes = [dict(probe(url)) for url in PUBLIC_PROBE_URLS]
    public_probe_audit = {
        "schemaVersion": "v13_27_1_12_public_probe_audit_v1",
        "checkedAt": checked_at,
        "publicOnly": True,
        "probeCount": len(public_probes),
        "successfulProbeCount": sum(1 for row in public_probes if row.get("ok")),
        "probes": public_probes,
        "rawPayloadPersisted": False,
        "credentialsUsed": False,
    }
    existing_scan = dict(download_manifest.get("existingDataScan") or {})
    bounded_audit = {
        "schemaVersion": "v13_27_1_12_bounded_existing_data_audit_v1",
        "checkedAt": checked_at,
        "dataRoot": str(data_root),
        "dataRootExists": data_root.is_dir(),
        "existingPartitionCount": int(existing_scan.get("partitionCount") or 0),
        "networkCollectionStarted": False,
        "networkCollectionRequestCount": int(download_manifest.get("networkRequestCount") or 0),
        "downloadedBytes": int(download_manifest.get("downloadedBytes") or 0),
        "reason": str(
            download_manifest.get("reason")
            or "no_verified_complete_same_exchange_source_chain"
        ),
        "checkpointsPreserved": True,
        "userDataModified": False,
    }

    _write_json(report_root / "data_readiness.json", readiness)
    _write_json(report_root / "campaign_start_decision.json", campaign)
    _write_json(report_root / "qlib_start_decision.json", qlib_decision)
    _write_json(report_root / "public_probe_audit.json", public_probe_audit)
    _write_json(report_root / "bounded_existing_data_audit.json", bounded_audit)
    (report_root / "data_readiness_summary.md").write_text(
        _summary_markdown(readiness, campaign), encoding="utf-8", newline="\n"
    )

    manifest = _artifact_manifest(report_root, checked_at)
    _write_json(report_root / "artifact_manifest.json", manifest)
    for path in sorted(report_root.iterdir()):
        if path.is_file() and path.suffix.lower() in {".json", ".csv", ".md"}:
            _write_sha256(path)

    return {
        "status": readiness["status"],
        "A1Status": readiness["A1Status"],
        "A2Status": readiness["A2Status"],
        "BStatus": readiness["BStatus"],
        "CStatus": readiness["CStatus"],
        "formalTopLevelDirectionCount": formal_count,
        "threeDirectionCampaignMayRun": three_direction_may_run,
        "qlibCampaignMayRun": qlib_may_run,
        "strategyTrialCount": 0,
        "holdoutAccessCount": 0,
        "releaseCount": 0,
        "demoArmCount": 0,
        "orderCount": 0,
        "reportRoot": str(report_root),
    }
