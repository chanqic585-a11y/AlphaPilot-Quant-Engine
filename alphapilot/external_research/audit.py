"""Generate frozen external-reference and adoption reports without networking."""

from __future__ import annotations

import argparse
import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.evolution.registry.hashing import sha256_file

from .adoption_matrix import AdoptionRecord, validate_adoption_matrix
from .reference_manifest import ExternalReference


def _git_value(path: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(path), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def audit_references(
    *,
    vibe_path: Path,
    alpha101_path: Path,
    alpha191_path: Path,
    output_root: Path,
    notices_path: Path,
    retrieved_at: str | None = None,
) -> dict[str, Any]:
    timestamp = retrieved_at or datetime.now(UTC).isoformat()
    vibe_sha = _git_value(vibe_path, "rev-parse", "HEAD")
    alpha101_sha = _git_value(alpha101_path, "rev-parse", "HEAD")
    alpha191_sha = sha256_file(alpha191_path)
    references = {
        "vibe_trading": ExternalReference.create(
            source_type="git",
            repository_or_file=_git_value(vibe_path, "remote", "get-url", "origin"),
            commit_or_hash=vibe_sha,
            license_status="verified_mit",
            source_path=str(vibe_path),
            retrieved_at=timestamp,
        ),
        "alpha101": ExternalReference.create(
            source_type="git",
            repository_or_file=_git_value(alpha101_path, "remote", "get-url", "origin"),
            commit_or_hash=alpha101_sha,
            license_status="blocked_empty_license_file",
            source_path=str(alpha101_path),
            retrieved_at=timestamp,
        ),
        "alpha191_manual": ExternalReference.create(
            source_type="file",
            repository_or_file=alpha191_path.name,
            commit_or_hash=alpha191_sha,
            license_status="review_required_reference_only",
            source_path=str(alpha191_path),
            retrieved_at=timestamp,
        ),
    }
    for key, reference in references.items():
        filename = {
            "vibe_trading": "vibe_trading_reference_manifest.json",
            "alpha101": "alpha101_reference_manifest.json",
            "alpha191_manual": "alpha191_manual_reference_manifest.json",
        }[key]
        _write_json(output_root / filename, reference.to_dict())

    records = [
        AdoptionRecord(
            source="HKUDS/Vibe-Trading",
            frozen_sha=vibe_sha,
            source_module="factor research workflow and operator semantics",
            target_module="alphapilot.factor_lab and alphapilot.research_screening",
            copied_code=False,
            license_name="MIT",
            status="参考后重写",
            adoption_reason="Use audited concepts behind independent AlphaPilot contracts.",
            rejection_reason="",
            test_plan="Independent fixtures, AST security tests, and numeric cross-checks.",
        ),
        AdoptionRecord(
            source="yydhYYDH/alpha101",
            frozen_sha=alpha101_sha,
            source_module="Alpha101 formula examples",
            target_module="alphapilot.factor_lab.alpha191.external_crosscheck",
            copied_code=False,
            license_name="unverified_empty_license_file",
            status="许可证阻塞",
            adoption_reason="",
            rejection_reason="The repository license file is empty; no code may be copied.",
            test_plan="Reference identity only until a usable license is verified.",
        ),
        AdoptionRecord(
            source="Alpha191 因子公式小白学习手册",
            frozen_sha=alpha191_sha,
            source_module="formula descriptions and educational summaries",
            target_module="alphapilot.factor_lab.alpha191.manual_reference",
            copied_code=False,
            license_name="review_required",
            status="仅文档参考",
            adoption_reason="Record concise formula metadata without reproducing long passages.",
            rejection_reason="",
            test_plan="Manual formula provenance and ambiguity review per factor.",
        ),
    ]
    errors = validate_adoption_matrix(records)
    if errors:
        raise ValueError("; ".join(errors))
    matrix = [record.to_dict() for record in records]
    _write_json(output_root / "external_adoption_matrix.json", matrix)
    summary_lines = [
        "# External Research Adoption Summary",
        "",
        "All references are frozen and read-only. No external runtime dependency or copied strategy code is used.",
        "",
        "| Source | Status | Copied code | License |",
        "|---|---|---:|---|",
    ]
    summary_lines.extend(
        f"| {item.source} | {item.status} | {'yes' if item.copied_code else 'no'} | {item.license_name} |"
        for item in records
    )
    (output_root / "external_adoption_summary.md").write_text(
        "\n".join(summary_lines) + "\n", encoding="utf-8"
    )
    notices_path.write_text(
        "# Third-Party Notices\n\n"
        "AlphaPilot does not bundle code from the frozen research references in this audit.\n\n"
        f"- HKUDS/Vibe-Trading `{vibe_sha}`: MIT, concepts independently reimplemented.\n"
        f"- yydhYYDH/alpha101 `{alpha101_sha}`: empty LICENSE file; code copying blocked.\n"
        f"- Alpha191 manual `{alpha191_sha}`: reference-only metadata; no long text copied.\n",
        encoding="utf-8",
    )
    return {
        "references": {key: value.to_dict() for key, value in references.items()},
        "adoptionMatrix": matrix,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--vibe-path", type=Path, required=True)
    parser.add_argument("--alpha101-path", type=Path, required=True)
    parser.add_argument("--alpha191-path", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, default=Path("reports/external_research"))
    parser.add_argument("--notices-path", type=Path, default=Path("THIRD_PARTY_NOTICES.md"))
    args = parser.parse_args()
    audit_references(
        vibe_path=args.vibe_path,
        alpha101_path=args.alpha101_path,
        alpha191_path=args.alpha191_path,
        output_root=args.output_root,
        notices_path=args.notices_path,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
