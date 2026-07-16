"""Create a conservative, reviewable cleanup plan."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Mapping

from .duplicate_classifier import classify_duplicates
from .reference_graph import build_reference_graph
from .retention_policy import duplicate_class_is_safe


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_cleanup_plan(graph: Mapping[str, Any], duplicates: Mapping[str, Any]) -> dict[str, Any]:
    rows = {str(row["path"]): dict(row) for row in graph.get("files", [])}
    candidates: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    seen: set[str] = set()
    for group in duplicates.get("groups", []):
        duplicate_class = str(group.get("duplicateClass") or "")
        authority_path = group.get("authoritativePath")
        authority_sha = group.get("authoritativeSha256")
        for path in group.get("members", []):
            if path == authority_path or path in seen:
                continue
            seen.add(path)
            row = rows.get(str(path))
            reasons: list[str] = []
            if not row:
                reasons.append("missing_reference_graph_row")
            else:
                if int(row.get("referenceCount") or 0) != 0:
                    reasons.append("referenced")
                if bool(row.get("immutableEvidence")):
                    reasons.append("immutable_evidence")
            if not duplicate_class_is_safe(duplicate_class):
                reasons.append("unsafe_duplicate_class")
            if not bool(group.get("contentVerified")):
                reasons.append("content_not_verified")
            if not authority_path or not authority_sha:
                reasons.append("missing_authoritative_copy")
            item = {
                **(row or {"path": path, "sha256": None, "sizeBytes": 0, "referenceCount": None, "immutableEvidence": None}),
                "duplicateClass": duplicate_class,
                "authoritativePath": authority_path,
                "authoritativeSha256": authority_sha,
                "contentVerified": bool(group.get("contentVerified")),
            }
            if reasons:
                blocked.append({**item, "blockedReasons": sorted(set(reasons))})
            else:
                candidates.append(item)
    candidates.sort(key=lambda item: str(item["path"]))
    blocked.sort(key=lambda item: str(item["path"]))
    return {
        "schemaVersion": "storage_cleanup_plan_v1",
        "generatedAt": _utc_now(),
        "dataRoot": graph.get("dataRoot"),
        "applyCleanup": False,
        "candidateCount": len(candidates),
        "blockedCount": len(blocked),
        "reclaimableBytes": sum(int(item.get("sizeBytes") or 0) for item in candidates),
        "candidates": candidates,
        "blocked": blocked,
    }


def audit_and_plan(
    *,
    data_root: Path,
    repository_roots: list[Path],
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    graph = build_reference_graph(
        data_root,
        repository_roots=repository_roots,
        hash_cache_path=output_root / "hash_checkpoint.json",
    )
    duplicates = classify_duplicates(graph, data_root=data_root)
    plan = build_cleanup_plan(graph, duplicates)
    inventory = {
        "schemaVersion": "storage_inventory_v1",
        "dataRoot": graph["dataRoot"],
        "fileCount": graph["fileCount"],
        "totalSizeBytes": sum(int(row["sizeBytes"]) for row in graph["files"]),
        "referencedFileCount": graph["referencedFileCount"],
        "immutableEvidenceFileCount": graph["immutableEvidenceFileCount"],
        "files": graph["files"],
    }
    retention = {
        "schemaVersion": "storage_retention_manifest_v1",
        "rules": {
            "retainReferenced": True,
            "retainImmutableEvidence": True,
            "retainConflicting": True,
            "retainUnknownProvenance": True,
            "safeDuplicateClasses": ["byte_identical", "content_equivalent", "rolling_snapshot_superseded"],
            "rawAnnualVsAllRequiresContentProof": True,
        },
        "retainedFileCount": graph["fileCount"] - plan["candidateCount"],
    }
    reports = {
        "reference_graph.json": graph,
        "storage_inventory.json": inventory,
        "duplicate_groups.json": duplicates,
        "cleanup_dry_run.json": plan,
        "reclaim_estimate.json": {
            "schemaVersion": "storage_reclaim_estimate_v1",
            "candidateCount": plan["candidateCount"],
            "reclaimableBytes": plan["reclaimableBytes"],
        },
        "retention_manifest.json": retention,
    }
    for name, payload in reports.items():
        _write_json(output_root / name, payload)
    (output_root / "reference_graph_summary.md").write_text(
        "# Storage Reference Graph\n\n"
        f"- Files: {graph['fileCount']}\n"
        f"- Referenced: {graph['referencedFileCount']}\n"
        f"- Immutable evidence: {graph['immutableEvidenceFileCount']}\n",
        encoding="utf-8",
    )
    (output_root / "cleanup_dry_run.md").write_text(
        "# Storage Cleanup Dry Run\n\n"
        f"- Authorized root: `{graph['dataRoot']}`\n"
        f"- Candidates: {plan['candidateCount']}\n"
        f"- Reclaimable bytes: {plan['reclaimableBytes']}\n"
        "- No files were deleted by this command.\n",
        encoding="utf-8",
    )
    artifacts = {}
    for path in sorted(output_root.iterdir()):
        if path.is_file() and path.name not in {"hash_checkpoint.json", "artifact_manifest.json"}:
            artifacts[path.name] = {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "sizeBytes": path.stat().st_size,
            }
    artifact_manifest = {
        "schemaVersion": "storage_governance_artifact_manifest_v1",
        "dataRoot": str(data_root.resolve()),
        "artifacts": artifacts,
    }
    _write_json(output_root / "artifact_manifest.json", artifact_manifest)
    return {"graph": graph, "duplicates": duplicates, "plan": plan}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--repo-root", action="append", default=[])
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    result = audit_and_plan(
        data_root=Path(args.data_root),
        repository_roots=[Path(value) for value in args.repo_root],
        output_root=Path(args.output_root),
    )
    print(json.dumps({"candidateCount": result["plan"]["candidateCount"], "reclaimableBytes": result["plan"]["reclaimableBytes"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
