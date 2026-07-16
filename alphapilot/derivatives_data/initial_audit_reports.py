"""Write the fail-closed input mapping and public capability audit reports."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.derivatives_data.api_capability_audit import (
    build_default_capability_audit,
)
from alphapilot.derivatives_data.input_artifact_mapping import map_required_artifacts


DEFAULT_INPUT_ROLE_CANDIDATES: dict[str, tuple[str, ...]] = {
    "baselineArtifactManifest": ("reports/derivatives_data/artifact_manifest.json",),
    "baselineCampaignStopDecision": (
        "reports/research_factory_repair/campaign_stop_decision.json",
    ),
    "baselineCloseout": (
        "docs/V13.27.1.11-research-factory-data-readiness-closeout.md",
    ),
    "baselineDataReadiness": ("reports/derivatives_data/data_readiness.json",),
    "baselineEnvironmentManifest": (
        "reports/reproducibility/environment_manifest.json",
    ),
}


def _mapping_markdown(mapping: dict[str, Any]) -> str:
    lines = [
        "# V13.27.1.12 Input Artifact Mapping",
        "",
        f"Status: `{mapping['status']}`",
        "",
        "| Logical role | Actual path | Exists | Selection | SHA-256 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in mapping["artifacts"]:
        lines.append(
            "| {role} | {path} | {exists} | {selection} | {digest} |".format(
                role=row["logicalRole"],
                path=row["actualPath"] or "--",
                exists="yes" if row["exists"] else "no",
                selection=row["selectedBy"],
                digest=row["contentHash"] or "--",
            )
        )
    lines.extend(
        [
            "",
            "A missing or ambiguous required input blocks all downstream readiness work.",
            "",
        ]
    )
    return "\n".join(lines)


def _capability_markdown(audit: dict[str, Any]) -> str:
    lines = [
        "# V13.27.1.12 Public Data Capability Audit",
        "",
        f"Checked at: `{audit['checkedAt']}`",
        "",
        "Only public market-data sources are listed. Candidate availability does not count as formal evidence until a probe and completeness audit pass.",
        "",
        "| Exchange | Data type | Endpoint or archive | Historical completeness | PIT semantics | Probe |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for row in audit["capabilities"]:
        lines.append(
            "| {exchange} | {data_type} | {endpoint} | {completeness} | {pit} | {probe} |".format(
                exchange=row["exchange"],
                data_type=row["dataType"],
                endpoint=row["endpointOrArchive"],
                completeness=row["historicalCompleteness"],
                pit=row["pointInTimeSemantics"],
                probe=row["probeStatus"],
            )
        )
    lines.extend(
        [
            "",
            "Formal source chains must be complete on one exchange; cross-exchange core-field splicing is prohibited.",
            "",
        ]
    )
    return "\n".join(lines)


def generate_initial_audit_reports(
    *,
    repo_root: Path,
    output_root: Path,
    checked_at: str,
    role_candidates: Mapping[str, Sequence[str]] = DEFAULT_INPUT_ROLE_CANDIDATES,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    mapping = map_required_artifacts(repo_root=repo_root, role_candidates=role_candidates)
    mapping_json = output_root / "input_artifact_mapping.json"
    mapping_md = output_root / "input_artifact_mapping.md"
    write_json_atomic(mapping_json, mapping)
    mapping_md.write_text(_mapping_markdown(mapping), encoding="utf-8", newline="\n")
    if mapping["status"] != "mapped":
        return {
            "status": "blocked_input_mapping",
            "inputArtifactMapping": str(mapping_json),
        }

    audit = build_default_capability_audit(checked_at=checked_at)
    capability_json = output_root / "api_capability_audit.json"
    capability_md = output_root / "api_capability_summary.md"
    write_json_atomic(capability_json, audit)
    capability_md.write_text(_capability_markdown(audit), encoding="utf-8", newline="\n")
    return {
        "status": "completed",
        "inputArtifactMapping": str(mapping_json),
        "apiCapabilityAudit": str(capability_json),
    }
