"""Resumable V37B reference-package campaign orchestration."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.research_screening.campaign_contract import build_campaign_preregistration
from alphapilot.research_screening.campaign_preregistration import calculate_time_boundaries
from alphapilot.research_screening.campaign_runner import run_campaign

from .candidates import build_selected_candidates
from .data_audit import audit_candidate_data
from .inventory import build_candidate_inventory
from .package_loader import load_reference_package
from .workflow_state import WorkflowStateStore


_IMPLEMENTATION_SOURCES = (
    "alphapilot/reference_strategy_research/package_loader.py",
    "alphapilot/reference_strategy_research/inventory.py",
    "alphapilot/reference_strategy_research/candidates.py",
    "alphapilot/reference_strategy_research/data_audit.py",
    "alphapilot/reference_strategy_research/gap_downloader.py",
    "alphapilot/reference_strategy_research/signals.py",
    "alphapilot/reference_strategy_research/workflow_state.py",
    "alphapilot/reference_strategy_research/workflow.py",
    "alphapilot/research_screening/campaign_runner.py",
    "alphapilot/exit_policy/schema.py",
)


def _payload_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected a JSON object: {path}")
    return value


def _single(directory: Path, pattern: str) -> Path:
    rows = sorted(directory.glob(pattern))
    if len(rows) != 1:
        raise RuntimeError(f"expected exactly one {pattern} in {directory}, found {len(rows)}")
    return rows[0]


def _write_immutable_json(path: Path, payload: dict[str, Any]) -> None:
    if path.exists():
        if _payload_hash(_load_json(path)) != _payload_hash(payload):
            raise RuntimeError(f"immutable artifact drift: {path}")
        return
    write_json_atomic(path, payload)


def _write_immutable_text(path: Path, content: str) -> None:
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise RuntimeError(f"immutable artifact drift: {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _csv(rows: Iterable[dict[str, Any]], columns: tuple[str, ...]) -> str:
    import io

    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(columns), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column) for column in columns})
    return buffer.getvalue()


def _advance(store: WorkflowStateStore, stage: str, artifact: Path) -> None:
    if not artifact.is_file():
        raise RuntimeError(f"stage artifact is missing: {artifact}")
    store.complete(stage, artifact_hash=sha256_file(artifact))


def _source_hashes(repo: Path) -> dict[str, str]:
    return {name: sha256_file(repo / name) for name in _IMPLEMENTATION_SOURCES}


def run_reference_workflow(
    *,
    repo_root: str | Path,
    package_path: str | Path,
    code_commit: str,
    execute_campaign: bool,
) -> dict[str, Any]:
    repo = Path(repo_root).resolve()
    package = load_reference_package(package_path)
    run_id = f"v37b-reference-{package.archiveSha256[:12]}-{code_commit[:12]}"
    output = repo / "reports" / "backtest_screening" / "reference_strategy_research" / run_id
    output.mkdir(parents=True, exist_ok=True)
    store = WorkflowStateStore(output / "workflow_state.json", run_id=run_id)

    source_verification = {
        "schemaVersion": "reference_strategy_source_verification_v1",
        "runId": run_id,
        "archivePath": package.archivePath,
        "archiveSha256": package.archiveSha256,
        "manifestHash": package.manifest["manifestHash"],
        "sourceArchiveSha256": package.manifest["sourceArchiveSha256"],
        "candidateCount": len(package.candidates),
        "sourceFilesLoaded": package.sourceFilesLoaded,
        "status": "verified_metadata_only",
    }
    source_path = output / "source_verification.json"
    _write_immutable_json(source_path, source_verification)
    _advance(store, "source_verified", source_path)

    inventory = build_candidate_inventory(package.candidates)
    inventory_payload = {
        "schemaVersion": "reference_strategy_candidate_inventory_v1",
        "runId": run_id,
        "candidateCount": len(inventory),
        "candidates": inventory,
    }
    inventory_path = output / "candidate_inventory.json"
    _write_immutable_json(inventory_path, inventory_payload)
    _advance(store, "inventory_written", inventory_path)

    dedupe_columns = (
        "candidateId",
        "familyId",
        "timeframe",
        "disposition",
        "overlapWith",
        "semanticFingerprint",
        "reason",
    )
    dedupe_path = output / "semantic_dedupe_matrix.csv"
    _write_immutable_text(dedupe_path, _csv(inventory, dedupe_columns))
    _advance(store, "dedupe_complete", dedupe_path)

    selected_sources = [
        dict(candidate)
        for candidate in package.candidates
        if next(row for row in inventory if row["candidateId"] == candidate["candidateId"])[
            "disposition"
        ]
        == "selected_bounded_research"
    ]
    candidates = build_selected_candidates(selected_sources)
    if len(candidates) != 4:
        raise RuntimeError(f"expected four directional candidates, found {len(candidates)}")

    shortlist = _load_json(_single(repo / "research" / "factor_shortlists", "factor_shortlist_*.json"))
    snapshot_id = str(shortlist["dataSnapshotHash"])
    snapshot = _load_json(repo / "research" / "data_snapshots" / f"{snapshot_id}.json")
    catalog_path = repo / "reports" / "backtest_screening" / "data_readiness" / "dataset_catalog.json"
    catalog = _load_json(catalog_path)
    if snapshot.get("dataManifestHash") != catalog.get("dataManifestHash"):
        raise RuntimeError("frozen data snapshot does not match the active dataset catalog")
    instruments = tuple(str(value) for value in snapshot["instruments"])
    data_audit = audit_candidate_data(
        candidates=candidates,
        catalog=catalog,
        instruments=instruments,
    )
    data_audit.update(
        {
            "schemaVersion": "reference_strategy_data_gap_audit_v1",
            "runId": run_id,
            "catalogPath": str(catalog_path),
            "catalogManifestHash": catalog["dataManifestHash"],
            "networkCalls": 0,
        }
    )
    data_audit_path = output / "data_gap_audit.json"
    _write_immutable_json(data_audit_path, data_audit)
    if not data_audit["ready"]:
        return {
            "status": "blocked_data_gaps",
            "runId": run_id,
            "output": str(output),
            "dataAudit": data_audit,
            "nextStage": store.next_stage(),
        }
    _advance(store, "data_audit_complete", data_audit_path)

    candidate_payload = {
        "schemaVersion": "reference_strategy_selected_candidates_v1",
        "runId": run_id,
        "parentCandidateCount": len(selected_sources),
        "directionalCandidateCount": len(candidates),
        "candidates": [candidate.to_dict() for candidate in candidates],
    }
    candidate_path = output / "selected_candidates.json"
    _write_immutable_json(candidate_path, candidate_payload)

    source_hashes = _source_hashes(repo)
    implementation_payload = {
        "schemaVersion": "reference_strategy_implementation_evidence_v1",
        "runId": run_id,
        "codeCommit": code_commit,
        "sourceHashes": source_hashes,
        "selectedCandidatesSha256": sha256_file(candidate_path),
        "testsRequired": [
            "tests/reference_strategy_research",
            "tests/research_screening/test_campaign_runner.py",
            "tests/exit_policy/test_models_and_validation.py",
        ],
    }
    implementation_path = output / "implementation_evidence.json"
    _write_immutable_json(implementation_path, implementation_payload)
    _advance(store, "implementation_verified", implementation_path)

    preregistration = build_campaign_preregistration(
        external_reference_manifest_hash=str(package.manifest["manifestHash"]),
        data_snapshot_hash=snapshot_id,
        factor_shortlist_hash=str(shortlist["factorShortlistId"]),
        factor_registry_hash=str(shortlist["factorRegistryHash"]),
        candidates=candidates,
        time_boundaries=calculate_time_boundaries(catalog, {row.timeframe for row in candidates}),
        code_commit=code_commit,
        universe_policy={
            "mode": "frozen_time_series_instruments",
            "instruments": list(instruments),
            "pitStatus": snapshot.get("pitStatus"),
            "crossSectionalUse": "disabled",
        },
        implementation_source_hashes=source_hashes,
    )
    prereg_path = repo / "research" / "preregistrations" / f"{preregistration['campaignId']}.json"
    _write_immutable_json(prereg_path, preregistration)
    _advance(store, "preregistered", prereg_path)

    if not execute_campaign:
        return {
            "status": "preregistered",
            "runId": run_id,
            "campaignId": preregistration["campaignId"],
            "preregistration": str(prereg_path),
            "output": str(output),
            "nextStage": store.next_stage(),
        }

    campaign_start = {
        "schemaVersion": "reference_strategy_campaign_start_v1",
        "runId": run_id,
        "campaignId": preregistration["campaignId"],
        "preregistrationHash": preregistration["preregistrationHash"],
        "resultRunNetworkPolicy": "offline_enforced",
    }
    campaign_start_path = output / "campaign_start.json"
    _write_immutable_json(campaign_start_path, campaign_start)
    _advance(store, "campaign_running", campaign_start_path)
    campaign_result = run_campaign(repo, prereg_path)
    campaign_output = Path(campaign_result["output"])
    campaign_manifest = campaign_output / "artifact_manifest.json"
    _advance(store, "campaign_complete", campaign_manifest)

    summary = campaign_result["summary"]
    dispositions: dict[str, int] = {}
    for row in inventory:
        key = str(row["disposition"])
        dispositions[key] = dispositions.get(key, 0) + 1
    closeout = {
        "schemaVersion": "reference_strategy_campaign_closeout_v1",
        "runId": run_id,
        "campaignId": preregistration["campaignId"],
        "packageCandidateCount": len(inventory),
        "inventoryDispositions": dispositions,
        "selectedParentCount": len(selected_sources),
        "directionalCandidateCount": len(candidates),
        "dataGapCount": len(data_audit["missing"]),
        "networkDownloads": 0,
        "campaignSummary": summary,
        "forcedWinner": False,
        "demoReleaseCount": 0,
        "ordersCreated": 0,
        "status": "completed",
    }
    closeout_path = output / "closeout.json"
    _write_immutable_json(closeout_path, closeout)
    closeout_md = (
        f"# V37B Reference Strategy Campaign\n\n"
        f"- Run: `{run_id}`\n"
        f"- Campaign: `{preregistration['campaignId']}`\n"
        f"- Package candidates inventoried: {len(inventory)}\n"
        f"- Parent hypotheses selected: {len(selected_sources)}\n"
        f"- Directional candidates tested: {len(candidates)}\n"
        f"- Data gaps: {len(data_audit['missing'])}\n"
        f"- Prescreen passes: {summary['prescreenPassCount']}\n"
        f"- Formal passes: {summary['formalPassCount']}\n"
        f"- Demo releases: 0\n"
        f"- Orders created: 0\n\n"
        "Zero survivors is an accepted research outcome; no candidate was forced through a gate.\n"
    )
    _write_immutable_text(output / "closeout.md", closeout_md)
    _advance(store, "closeout_complete", closeout_path)

    artifacts = sorted(
        path
        for path in output.rglob("*")
        if path.is_file() and path.name != "workflow_artifact_manifest.json"
    )
    workflow_manifest = {
        "schemaVersion": "reference_strategy_workflow_artifact_manifest_v1",
        "runId": run_id,
        "artifacts": [
            {
                "path": str(path.relative_to(repo)).replace("\\", "/"),
                "sha256": sha256_file(path),
            }
            for path in artifacts
        ],
    }
    workflow_manifest["manifestHash"] = stable_hash(
        workflow_manifest,
        prefix="reference_strategy_workflow_artifacts",
    )
    write_json_atomic(output / "workflow_artifact_manifest.json", workflow_manifest)
    return {
        "status": "completed",
        "runId": run_id,
        "campaignId": preregistration["campaignId"],
        "output": str(output),
        "campaignOutput": str(campaign_output),
        "summary": summary,
        "nextStage": store.next_stage(),
    }
