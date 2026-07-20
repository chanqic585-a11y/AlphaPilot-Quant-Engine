"""Run the offline V37D source-fidelity and candidate-status audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.reference_strategy_research.source_fidelity import (
    build_candidate_status_inventory,
    build_source_admission,
)
from alphapilot.reference_strategy_research.source_semantics import audit_source_semantics


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(value, encoding="utf-8", newline="\n")
    temporary.replace(path)


def _source_matrix_csv(admission: dict[str, Any]) -> str:
    buffer = io.StringIO(newline="")
    fields = (
        "candidateId",
        "sourceStatus",
        "sourceFaithfulReady",
        "sourceIdentityVerified",
        "equivalenceStatus",
        "translationClass",
        "sourceCount",
        "materialGapCount",
    )
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for candidate in admission["candidates"]:
        writer.writerow(
            {
                "candidateId": candidate["candidateId"],
                "sourceStatus": candidate["sourceStatus"],
                "sourceFaithfulReady": str(candidate["sourceFaithfulReady"]).lower(),
                "sourceIdentityVerified": str(candidate["sourceIdentityVerified"]).lower(),
                "equivalenceStatus": candidate["equivalenceStatus"],
                "translationClass": candidate["translationClass"],
                "sourceCount": len(candidate["sources"]),
                "materialGapCount": len(candidate["materialGaps"]),
            }
        )
    return buffer.getvalue()


def _verify_package(package: Path, verification: dict[str, Any]) -> str:
    observed = sha256_file(package)
    expected = str(verification.get("archiveSha256") or "")
    if not expected or observed != expected:
        raise RuntimeError("reference package hash does not match V37B source verification")
    return observed


def _verify_v37c_manifest(run_dir: Path) -> dict[str, Any]:
    manifest_path = run_dir / "artifact_manifest.json"
    if not manifest_path.is_file():
        return {"manifestPresent": False, "verifiedArtifactCount": 0}
    manifest = _load_json(manifest_path)
    verified = 0
    for row in manifest.get("artifacts") or []:
        target = run_dir / str(row.get("path") or "")
        if not target.is_file() or sha256_file(target) != row.get("sha256"):
            raise RuntimeError(f"V37C artifact drift: {target}")
        verified += 1
    return {
        "manifestPresent": True,
        "manifestSha256": sha256_file(manifest_path),
        "verifiedArtifactCount": verified,
    }


def run_v37d_source_fidelity_audit(
    *,
    repo_root: str | Path,
    package_path: str | Path,
    v36_run_dir: str | Path,
    v37b_run_dir: str | Path,
    v37c_run_dir: str | Path,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Generate a deterministic audit without rerunning strategy economics."""

    repo = Path(repo_root).resolve()
    package = Path(package_path).resolve()
    v36 = Path(v36_run_dir).resolve()
    v37b = Path(v37b_run_dir).resolve()
    v37c = Path(v37c_run_dir).resolve()

    v36_summary_path = v36 / "campaign_summary.json"
    v36_selection_path = v36 / "neighborhood_selection.json"
    v37b_source_path = v37b / "source_verification.json"
    v37b_closeout_path = v37b / "closeout.json"
    v37c_source_path = v37c / "source_lineage_audit.json"
    v37c_reassessment_path = v37c / "v37b_reassessment.json"

    v36_summary = _load_json(v36_summary_path)
    v36_selection = _load_json(v36_selection_path)
    v37b_source = _load_json(v37b_source_path)
    v37b_closeout = _load_json(v37b_closeout_path)
    frozen_source_audit = _load_json(v37c_source_path)
    v37c_reassessment = _load_json(v37c_reassessment_path)

    package_hash = _verify_package(package, v37b_source)
    v37c_manifest_verification = _verify_v37c_manifest(v37c)
    reproduced_source_audit = audit_source_semantics(package)
    if _canonical_json(reproduced_source_audit) != _canonical_json(frozen_source_audit):
        raise RuntimeError("source audit drift detected between V37C and V37D")

    source_admission = build_source_admission(reproduced_source_audit)
    inventory = build_candidate_status_inventory(
        v36_summary=v36_summary,
        v36_selection=v36_selection,
        v37b_closeout=v37b_closeout,
        v37c_reassessment=v37c_reassessment,
    )
    input_identity = {
        "packageSha256": package_hash,
        "v36CampaignSummarySha256": sha256_file(v36_summary_path),
        "v36SelectionSha256": sha256_file(v36_selection_path),
        "v37bSourceVerificationSha256": sha256_file(v37b_source_path),
        "v37bCloseoutSha256": sha256_file(v37b_closeout_path),
        "v37cSourceAuditSha256": sha256_file(v37c_source_path),
        "v37cReassessmentSha256": sha256_file(v37c_reassessment_path),
        "v37cManifestVerification": v37c_manifest_verification,
    }
    identity_hash = hashlib.sha256(_canonical_json(input_identity).encode("utf-8")).hexdigest()
    run_id = f"v37d-source-fidelity-{package_hash[:12]}-{identity_hash[:12]}"
    root = (
        Path(output_root).resolve()
        if output_root is not None
        else repo / "reports" / "backtest_screening" / "reference_strategy_source_fidelity"
    )
    output = root / run_id
    output.mkdir(parents=True, exist_ok=True)

    comparison = {
        "schemaVersion": "reference_strategy_normalized_vs_source_comparison_v1",
        "sourceEquivalenceEstablished": source_admission["sourceFaithfulReadyCount"] > 0,
        "v37cProductionOracleParityPassed": bool(v37c_reassessment.get("executableParityPassed")),
        "v37cGateReachabilityPassed": bool(v37c_reassessment.get("gatesReachable")),
        "normalizedCandidateCount": len(v37c_reassessment.get("candidates") or []),
        "normalizedFormalPassCount": inventory["formalPassCount"],
        "conclusion": (
            "V37C validates the normalized AlphaPilot executable and its reachable gates. "
            "It does not establish equivalence to the original external strategy semantics."
        ),
    }
    reproduction_plan = {
        "schemaVersion": "reference_strategy_reproduction_plan_v1",
        "sourceFaithfulCandidateCount": source_admission["sourceFaithfulReadyCount"],
        "actions": [
            {
                "candidateId": candidate["candidateId"],
                "sourceStatus": candidate["sourceStatus"],
                "disposition": (
                    "eligible_for_frozen_source_faithful_reproduction"
                    if candidate["sourceFaithfulReady"]
                    else "retain_as_bounded_normalized_research"
                    if candidate["sourceStatus"] == "normalization_only"
                    else "blocked_until_execution_semantics_are_frozen"
                ),
                "materialGaps": candidate["materialGaps"],
            }
            for candidate in source_admission["candidates"]
        ],
        "economicGateChanges": 0,
        "forcedWinner": False,
        "nextFormalRunAuthorized": False,
    }

    write_json_atomic(output / "source_admission.json", source_admission)
    _write_text(output / "source_identity_matrix.csv", _source_matrix_csv(source_admission))
    write_json_atomic(output / "normalized_vs_source_comparison.json", comparison)
    write_json_atomic(output / "candidate_status_inventory.json", inventory)
    write_json_atomic(output / "reproduction_plan.json", reproduction_plan)

    status = (
        "completed_with_source_faithful_candidates"
        if source_admission["sourceFaithfulReadyCount"]
        else "completed_no_source_faithful_candidates"
    )
    conclusion = (
        "# V37D Source-Faithful Reproduction Audit\n\n"
        f"- Run: `{run_id}`\n"
        f"- Status: `{status}`\n"
        f"- Research eligible: {inventory['researchEligibleCount']}\n"
        f"- Development stable: {inventory['developmentStableCount']}\n"
        f"- Formal pass: {inventory['formalPassCount']}\n"
        f"- Demo ready: {inventory['demoReadyCount']}\n"
        f"- Source-faithful ready: {source_admission['sourceFaithfulReadyCount']}\n\n"
        "## Conclusion\n\n"
        "Two V36 candidates remain development-stable, but neither has completed frozen Formal "
        "validation or produced an immutable Demo Release. The reference package provides one "
        "deterministic documentation normalization and one source-backed variant with material "
        "execution gaps. Neither may be represented as a source-faithful reproduced strategy.\n\n"
        "No network download, order, Demo mutation, gate change or forced winner occurred.\n"
    )
    _write_text(output / "final_conclusion.md", conclusion)

    artifact_names = (
        "source_identity_matrix.csv",
        "source_admission.json",
        "normalized_vs_source_comparison.json",
        "candidate_status_inventory.json",
        "reproduction_plan.json",
        "final_conclusion.md",
    )
    manifest = {
        "schemaVersion": "v37d_source_fidelity_artifact_manifest_v1",
        "runId": run_id,
        "status": status,
        "inputIdentity": input_identity,
        "safety": {
            "networkDownloads": 0,
            "demoOrLiveMutations": 0,
            "ordersCreated": 0,
            "forcedWinner": False,
            "gateThresholdsChanged": False,
        },
        "artifacts": [
            {"path": name, "sha256": sha256_file(output / name)} for name in artifact_names
        ],
    }
    write_json_atomic(output / "artifact_manifest.json", manifest)
    return {
        "status": status,
        "runId": run_id,
        "output": str(output),
        "researchEligibleCount": inventory["researchEligibleCount"],
        "developmentStableCount": inventory["developmentStableCount"],
        "formalPassCount": inventory["formalPassCount"],
        "demoReadyCount": inventory["demoReadyCount"],
        "sourceFaithfulReadyCount": source_admission["sourceFaithfulReadyCount"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--v36-run-dir", type=Path, required=True)
    parser.add_argument("--v37b-run-dir", type=Path, required=True)
    parser.add_argument("--v37c-run-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_v37d_source_fidelity_audit(
        repo_root=args.repo,
        package_path=args.package,
        v36_run_dir=args.v36_run_dir,
        v37b_run_dir=args.v37b_run_dir,
        v37c_run_dir=args.v37c_run_dir,
        output_root=args.output_root,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
