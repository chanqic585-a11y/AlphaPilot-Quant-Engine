"""Resolve historical Phase 3/4 evidence without guessing or placeholders."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


PHASE3_CAMPAIGN_ID = (
    "phase3c_campaign_dece86da86243317f47c517466acc1b9e901553fe80b802c8ce71d5c7e7cfc50"
)
PHASE3_DATA_SNAPSHOT_ID = (
    "data_snapshot_7e094bf71a54e5bd25d07427ff813e12c45f3f90866dc27e4f196efa891a2c0a"
)
PHASE3_FACTOR_SHORTLIST_ID = (
    "factor_shortlist_5bdaeea71852321b56ba85c3890e4a497dccb5002c0ea4fd0b7d04e3be77a416"
)

REQUIRED_LOGICAL_ROLES = (
    "phase3CampaignSummary",
    "phase3GateMatrix",
    "phase3FailureAttribution",
    "phase3ExperimentBudget",
    "phase3ArtifactManifest",
    "phase3CandidateResults",
    "phase3Preregistration",
    "phase3DataSnapshot",
    "phase3FactorShortlist",
    "phase3DataAudit",
    "phase3DataManifest",
    "phase3FamilyEligibility",
    "phase3FactorBenchmark",
    "phase3FactorTrialLedger",
    "phase3FactorClusters",
    "phase3FactorMechanismMatrix",
    "phase4AcceptanceStatus",
    "phase4ReleaseStatus",
    "phase4DemoStatus",
    "phase3Phase4EvidenceBundle",
    "phase3Phase4AnalysisReport",
)


class InputArtifactMappingError(RuntimeError):
    """Raised when a required historical evidence role cannot be resolved safely."""


def default_phase34_role_specs(
    *,
    repository_root: Path,
    analysis_report_path: Path,
) -> dict[str, dict[str, Any]]:
    """Return the explicit V2 mapping contract for the closed Phase 3/4 baseline."""

    root = repository_root.resolve()
    campaign = root / "reports" / "backtest_screening" / PHASE3_CAMPAIGN_ID
    data_readiness = root / "reports" / "backtest_screening" / "data_readiness"
    factor_lab = root / "reports" / "factor_lab"
    release_summary = campaign / "candidate_releases" / "generation_summary.json"

    paths = {
        "phase3CampaignSummary": campaign / "campaign_summary.json",
        "phase3GateMatrix": campaign / "gate_matrix.json",
        "phase3FailureAttribution": campaign / "failure_attribution.json",
        "phase3ExperimentBudget": campaign / "experiment_budget.json",
        "phase3ArtifactManifest": campaign / "artifact_manifest.json",
        "phase3CandidateResults": campaign / "candidate_results.parquet",
        "phase3Preregistration": root
        / "research"
        / "preregistrations"
        / f"{PHASE3_CAMPAIGN_ID}.json",
        "phase3DataSnapshot": root
        / "research"
        / "data_snapshots"
        / f"{PHASE3_DATA_SNAPSHOT_ID}.json",
        "phase3FactorShortlist": root
        / "research"
        / "factor_shortlists"
        / f"{PHASE3_FACTOR_SHORTLIST_ID}.json",
        # Historical names are mapped explicitly; the source evidence remains immutable.
        "phase3DataAudit": data_readiness / "data_source_audit.json",
        "phase3DataManifest": data_readiness / "dataset_catalog.json",
        "phase3FamilyEligibility": data_readiness / "phase3b_exit_gate.json",
        "phase3FactorBenchmark": factor_lab / "factor_benchmark_report.json",
        "phase3FactorTrialLedger": factor_lab / "factor_trial_ledger.json",
        "phase3FactorClusters": factor_lab / "factor_clusters.json",
        "phase3FactorMechanismMatrix": factor_lab / "factor_market_mechanism_matrix.json",
        # Phase 4 closed with zero releases. These artifacts are the authoritative zero-state.
        "phase4AcceptanceStatus": release_summary,
        "phase4ReleaseStatus": release_summary,
        "phase4DemoStatus": campaign / "console_projection.json",
        "phase3Phase4EvidenceBundle": campaign / "artifact_manifest.json",
        "phase3Phase4AnalysisReport": analysis_report_path.resolve(),
    }
    return {
        role: {
            "required": True,
            "explicitPaths": [paths[role]],
            "exactFileNames": [paths[role].name],
        }
        for role in REQUIRED_LOGICAL_ROLES
    }


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    return {
        ".json": "json",
        ".md": "markdown",
        ".csv": "csv",
        ".parquet": "parquet",
        ".sqlite": "sqlite",
    }.get(suffix, suffix.removeprefix(".") or "unknown")


def schema_fingerprint(path: Path) -> str:
    """Return a deterministic, cheap schema identity without mutating the artifact."""

    file_type = _file_type(path)
    if file_type == "json":
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return "json:unreadable"
        if isinstance(payload, dict):
            version = str(payload.get("schemaVersion", "unknown"))
            return f"json:{version}:{','.join(sorted(str(key) for key in payload))}"
        return f"json:{type(payload).__name__}"
    if file_type == "markdown":
        headings: list[str] = []
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.startswith("#"):
                    headings.append(line.lstrip("#").strip())
        except (OSError, UnicodeDecodeError):
            return "markdown:unreadable"
        heading_hash = hashlib.sha256("\n".join(headings).encode("utf-8")).hexdigest()
        return f"markdown:headings:{heading_hash}"
    if file_type == "parquet":
        try:
            with path.open("rb") as stream:
                magic = stream.read(4)
        except OSError:
            return "parquet:unreadable"
        return "parquet:magic:PAR1" if magic == b"PAR1" else "parquet:invalid_magic"
    return f"{file_type}:content:{_sha256(path)}"


def _all_files(search_roots: Iterable[Path]) -> list[Path]:
    files: set[Path] = set()
    for root in search_roots:
        candidate = Path(root).expanduser()
        if candidate.is_file():
            files.add(candidate.resolve())
        elif candidate.is_dir():
            files.update(path.resolve() for path in candidate.rglob("*") if path.is_file())
    return sorted(files, key=lambda path: str(path).lower())


def _existing_paths(values: Sequence[object] | None) -> list[Path]:
    paths: list[Path] = []
    for value in values or ():
        path = Path(value).expanduser()
        if path.is_file():
            paths.append(path.resolve())
    return paths


def _record(
    *,
    logical_role: str,
    path: Path | None,
    selected_by: str | None,
    reason: str,
    ambiguous: Sequence[Path] = (),
) -> dict[str, Any]:
    return {
        "logicalRole": logical_role,
        "actualPath": str(path) if path is not None else None,
        "exists": path is not None and path.is_file(),
        "contentHash": _sha256(path) if path is not None else None,
        "fileType": _file_type(path) if path is not None else None,
        "schemaFingerprint": schema_fingerprint(path) if path is not None else None,
        "selectedBy": selected_by,
        "selectionReason": reason,
        "ambiguousMatches": [str(item) for item in ambiguous],
    }


def _ambiguous(role: str, stage: str, candidates: Sequence[Path]) -> InputArtifactMappingError:
    rendered = ", ".join(str(path) for path in candidates)
    return InputArtifactMappingError(f"ambiguous required role {role} at {stage}: {rendered}")


def build_input_artifact_mapping(
    *,
    role_specs: Mapping[str, Mapping[str, Any]],
    search_roots: Sequence[Path],
) -> dict[str, Any]:
    """Resolve roles in the V2 priority order and fail closed on uncertainty."""

    searchable = _all_files(Path(root) for root in search_roots)
    mappings: dict[str, dict[str, Any]] = {}

    for role, spec in role_specs.items():
        required = bool(spec.get("required", True))
        explicit = _existing_paths(spec.get("explicitPaths"))
        if explicit:
            selected = explicit[0]
            mappings[role] = _record(
                logical_role=role,
                path=selected,
                selected_by="explicit_user_path",
                reason="Selected from the ordered explicit user path list.",
                ambiguous=explicit[1:],
            )
            continue

        manifest_paths = _existing_paths(spec.get("manifestPaths"))
        if len(manifest_paths) > 1:
            raise _ambiguous(role, "artifact_manifest", manifest_paths)
        if manifest_paths:
            mappings[role] = _record(
                logical_role=role,
                path=manifest_paths[0],
                selected_by="artifact_manifest_path",
                reason="Selected from an artifact manifest registered path.",
            )
            continue

        fingerprints = set(str(value) for value in spec.get("schemaFingerprints", ()))
        schema_matches = [path for path in searchable if schema_fingerprint(path) in fingerprints]
        if len(schema_matches) > 1:
            raise _ambiguous(role, "schema_fingerprint", schema_matches)
        if schema_matches:
            mappings[role] = _record(
                logical_role=role,
                path=schema_matches[0],
                selected_by="unique_schema_fingerprint",
                reason="Selected by a unique registered schema fingerprint.",
            )
            continue

        exact_names = set(str(value) for value in spec.get("exactFileNames", ()))
        exact_matches = [path for path in searchable if path.name in exact_names]
        if len(exact_matches) > 1:
            raise _ambiguous(role, "exact_file_name", exact_matches)
        if exact_matches:
            mappings[role] = _record(
                logical_role=role,
                path=exact_matches[0],
                selected_by="exact_file_name",
                reason="Selected by one unambiguous exact filename match.",
            )
            continue

        mappings[role] = _record(
            logical_role=role,
            path=None,
            selected_by=None,
            reason="No admissible artifact matched this logical role.",
        )
        if required:
            raise InputArtifactMappingError(f"missing required role {role}")

    core = {
        "schemaVersion": "research_factory_input_artifact_mapping_v1",
        "status": "complete",
        "mappings": mappings,
    }
    canonical = json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return {**core, "mappingHash": hashlib.sha256(canonical.encode("utf-8")).hexdigest()}


def write_input_artifact_mapping_reports(
    *,
    mapping: Mapping[str, Any],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "input_artifact_mapping.json"
    markdown_path = output_dir / "input_artifact_mapping.md"
    json_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# Research Factory Input Artifact Mapping",
        "",
        f"Status: `{mapping.get('status')}`",
        f"Mapping hash: `{mapping.get('mappingHash')}`",
        "",
        "| Logical role | Selected by | Actual path | SHA-256 |",
        "| --- | --- | --- | --- |",
    ]
    for role, record in sorted(mapping.get("mappings", {}).items()):
        lines.append(
            "| {role} | {selected} | `{path}` | `{digest}` |".format(
                role=role,
                selected=record.get("selectedBy") or "unresolved",
                path=record.get("actualPath") or "--",
                digest=record.get("contentHash") or "--",
            )
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, markdown_path


def run_default_phase34_mapping(
    *,
    repository_root: Path,
    analysis_report_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    specs = default_phase34_role_specs(
        repository_root=repository_root,
        analysis_report_path=analysis_report_path,
    )
    mapping = build_input_artifact_mapping(
        role_specs=specs,
        search_roots=[repository_root],
    )
    write_input_artifact_mapping_reports(mapping=mapping, output_dir=output_dir)
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repository-root", type=Path, default=Path.cwd())
    parser.add_argument("--analysis-report", type=Path, required=True)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("reports/research_factory_repair"),
    )
    args = parser.parse_args()
    mapping = run_default_phase34_mapping(
        repository_root=args.repository_root,
        analysis_report_path=args.analysis_report,
        output_dir=args.output_dir,
    )
    print(json.dumps({"status": mapping["status"], "mappingHash": mapping["mappingHash"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
