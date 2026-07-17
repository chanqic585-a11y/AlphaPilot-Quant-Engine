"""Non-mutating sidecar evidence for the frozen V17 terminal route."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash


OUTPUT_ROOT = Path("reports/v13_27_1_17_closeout_supplement")
SOURCE_PATHS = (
    Path("research/preregistrations/advisory_r_v17_s01_formal_walk_forward.json"),
    Path("reports/formal_validation/advisory_r_v17/campaign_summary.json"),
    Path("reports/formal_validation/advisory_r_v17/route_decision.json"),
    Path("reports/formal_validation/advisory_r_v17/formal_execution_contract_audit.json"),
    Path("reports/v13_27_1_17_evidence_delivery/final_self_check.json"),
)
EVIDENCE_ZIP_PATHS = (
    Path(
        "reports/v13_27_1_17_evidence_delivery/"
        "AlphaPilot-V13.27.1.17-core-evidence.zip"
    ),
    Path(
        "reports/v13_27_1_17_evidence_delivery/"
        "AlphaPilot-V13.27.1.17-event-and-return-evidence.zip"
    ),
    Path(
        "reports/v13_27_1_17_evidence_delivery/"
        "AlphaPilot-V13.27.1.17-source-runtime-evidence.zip"
    ),
)


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def build_v17_closeout_supplement(
    repo_root: Path,
    *,
    original_evidence_commit: str,
    final_closeout_commit: str,
    local_tag: str,
    tag_target: str,
    upstream_commit: str | None,
    remote_tag_exists: bool,
    branch_push_status: str,
    external_publication_review_status: str,
) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    summary = _read_json(
        repo_root / "reports/formal_validation/advisory_r_v17/campaign_summary.json"
    )
    artifacts = [
        {
            "path": path.as_posix(),
            "sha256": sha256_file(repo_root / path),
            "byteCount": (repo_root / path).stat().st_size,
        }
        for path in SOURCE_PATHS
    ]
    evidence_zip_hashes = [
        {
            "path": path.as_posix(),
            "sha256": sha256_file(repo_root / path),
            "byteCount": (repo_root / path).stat().st_size,
        }
        for path in EVIDENCE_ZIP_PATHS
    ]
    published = (
        upstream_commit == final_closeout_commit
        and remote_tag_exists
        and branch_push_status == "published"
    )
    provenance: dict[str, Any] = {
        "schemaVersion": "v17_closeout_provenance_sidecar_v1",
        "campaignId": summary["campaignId"],
        "route": summary["route"],
        "status": summary["status"],
        "blockerCodes": summary["blockerCodes"],
        "formalRunCount": summary["formalRunCount"],
        "resultReadCount": summary["resultReadCount"],
        "lockedOosAccessCount": summary["lockedOosAccessCount"],
        "releaseCount": summary["releaseCount"],
        "demoArm": summary["demoArm"],
        "orderCount": summary["orderCount"],
        "originalEvidenceCommit": original_evidence_commit,
        "finalCloseoutCommit": final_closeout_commit,
        "localTag": local_tag,
        "tagTarget": tag_target,
        "upstreamCommit": upstream_commit,
        "remoteTagExists": remote_tag_exists,
        "branchPushStatus": branch_push_status,
        "externalPublicationReviewStatus": external_publication_review_status,
        "remoteFreezeStatus": "published" if published else "not_published",
        "originalArtifactsModified": False,
        "artifactHashes": artifacts,
        "evidenceZipHashes": evidence_zip_hashes,
        "supersededByCampaignFamily": "advisory_r_v18_s01_capital_policy_correction",
        "formalResultsExist": False,
        "safetyBoundary": {
            "lockedOosAccessCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    }
    provenance["sidecarHash"] = stable_hash(
        provenance, prefix="v17_closeout_provenance_sidecar"
    )
    issue_resolution: dict[str, Any] = {
        "schemaVersion": "v17_closeout_issue_resolution_sidecar_v1",
        "campaignId": summary["campaignId"],
        "P2-02": "status_resolved_at_final_closeout",
        "finalTestManifest": {
            "passed": 817,
            "skipped": 0,
            "source": "reports/v13_27_1_17_evidence_delivery/test_manifest.json",
        },
        "historicalLineEndingEvidence": "historical_preserved",
        "originalLedgerModified": False,
        "originalEvidenceModified": False,
        "resolutionScope": "non_result_closeout_metadata_only",
    }
    issue_resolution["sidecarHash"] = stable_hash(
        issue_resolution, prefix="v17_closeout_issue_resolution_sidecar"
    )
    return {
        "schemaVersion": "v17_closeout_supplement_bundle_v1",
        "provenance": provenance,
        "issueResolution": issue_resolution,
    }


def write_v17_closeout_supplement(
    payload: dict[str, Any], repo_root: Path
) -> dict[str, Path]:
    output = Path(repo_root).resolve() / OUTPUT_ROOT
    provenance = payload["provenance"]
    issue_resolution = payload["issueResolution"]
    provenance_path = output / "v17_closeout_provenance_sidecar.json"
    issue_resolution_path = output / "v17_closeout_issue_resolution_sidecar.json"
    write_json_atomic(provenance_path, provenance)
    write_json_atomic(issue_resolution_path, issue_resolution)
    manifest_payload: dict[str, Any] = {
        "schemaVersion": "v17_closeout_supplement_artifact_manifest_v1",
        "artifacts": [
            {
                "path": path.name,
                "sha256": sha256_file(path),
                "byteCount": path.stat().st_size,
            }
            for path in (provenance_path, issue_resolution_path)
        ],
        "originalEvidenceModified": False,
    }
    manifest_payload["manifestHash"] = stable_hash(
        manifest_payload, prefix="v17_closeout_supplement_artifact_manifest"
    )
    manifest_path = output / "artifact_manifest.json"
    write_json_atomic(manifest_path, manifest_payload)
    readme_path = output / "README.md"
    readme_path.write_text(
        "\n".join(
            [
                "# V17 Immutable Closeout Supplement",
                "",
                "This sidecar records the terminal V17 pre-run route without modifying frozen V17 evidence.",
                "",
                f"- Route: `{provenance['route']}`",
                f"- Formal run count: `{provenance['formalRunCount']}`",
                f"- Locked OOS access count: `{provenance['lockedOosAccessCount']}`",
                f"- Release / Demo ARM / order: `{provenance['releaseCount']} / {provenance['demoArm']} / {provenance['orderCount']}`",
                f"- Remote freeze: `{provenance['remoteFreezeStatus']}`",
                "- V18 may correct only the missing capital-policy execution definitions in a new campaign.",
                "",
            ]
        ),
        encoding="utf-8",
        newline="\n",
    )
    return {
        "provenance": provenance_path,
        "issueResolution": issue_resolution_path,
        "manifest": manifest_path,
        "readme": readme_path,
    }
