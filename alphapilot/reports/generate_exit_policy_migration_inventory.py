"""Inventory fixed-target references before the Advisory-R migration."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable, Mapping

REFERENCE_PATTERN = re.compile(
    r"minimumTargetR|targetRewardRiskRatio|targetR|remaining[_A-Za-z]*target[_A-Za-z]*r|(?:^|[^0-9])2R(?:[^A-Za-z]|$)",
    re.IGNORECASE,
)
TEXT_SUFFIXES = {".py", ".js", ".ts", ".tsx", ".json", ".md", ".ps1", ".html", ".css"}
IGNORED_PARTS = {".git", ".worktrees", ".venv", "__pycache__", "node_modules", "third_party"}
GENERATED_INVENTORY_PATHS = {
    "reports/exit_policy/migration_inventory.json",
    "reports/exit_policy/migration_inventory.md",
    "reports/exit_policy/migration_summary.md",
}

ACTIVE_LOGIC_PREFIXES = (
    "alphapilot/research_screening/",
    "alphapilot_control_console/strategy_validation_release_store.py",
    "alphapilot_control_console/demo_evidence.py",
    "alphapilot_control_console/demo_workflow_service.py",
    "alphapilot_control_console/demo_release_scanner.py",
)


def _classify(relative_path: str) -> tuple[str, str, bool]:
    normalized = relative_path.replace("\\", "/")
    lower = normalized.lower()
    if lower.startswith("reports/") or lower.startswith("research/preregistrations/"):
        return "historical_evidence", "preserve_bytes", False
    if lower.startswith("tests/"):
        return "test_contract", "update_test_if_behavior_changes", False
    if lower.endswith("readme.md") or lower.startswith("docs/") or "/prompts/" in lower:
        return "documentation", "update_current_wording_only", False
    if "live_" in lower or "/live" in lower:
        return "live_boundary", "preserve_live_admission", False
    if normalized.startswith(ACTIVE_LOGIC_PREFIXES):
        return "active_logic", "migrate", True
    if normalized == "web/app.js":
        return "active_ui_mixed", "review_active_demo_sections", False
    return "legacy_or_unreviewed_code", "review_without_global_replacement", False


def _iter_text_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        relative = path.relative_to(root)
        if any(part in IGNORED_PARTS for part in relative.parts):
            continue
        if relative.as_posix() in GENERATED_INVENTORY_PATHS:
            continue
        yield path


def scan_exit_policy_references(repo_roots: Mapping[str, Path]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for repo_name, root_value in sorted(repo_roots.items()):
        root = Path(root_value).resolve()
        for path in _iter_text_files(root):
            relative_path = path.relative_to(root).as_posix()
            classification, action, active_hard_gate = _classify(relative_path)
            try:
                lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                continue
            for line_number, line in enumerate(lines, start=1):
                if not REFERENCE_PATTERN.search(line):
                    continue
                rows.append(
                    {
                        "repo": repo_name,
                        "relativePath": relative_path,
                        "lineNumber": line_number,
                        "classification": classification,
                        "action": action,
                        "activeHardGate": active_hard_gate,
                        "line": line.strip()[:500],
                    }
                )
    return rows


def summarize_inventory(rows: Iterable[Mapping[str, object]]) -> dict[str, object]:
    materialized = list(rows)
    classifications = Counter(str(row["classification"]) for row in materialized)
    return {
        "totalHits": len(materialized),
        "activeHardGateHits": sum(bool(row.get("activeHardGate")) for row in materialized),
        "historicalHitsPreserved": classifications.get("historical_evidence", 0),
        "liveBoundaryHitsPreserved": classifications.get("live_boundary", 0),
        "classificationCounts": dict(sorted(classifications.items())),
    }


def write_inventory(
    repo_roots: Mapping[str, Path], output_root: Path
) -> tuple[Path, Path, dict[str, object]]:
    rows = scan_exit_policy_references(repo_roots)
    summary = summarize_inventory(rows)
    payload = {
        "schemaVersion": "exit_policy_migration_inventory_v1",
        "summary": summary,
        "references": rows,
    }
    output_root.mkdir(parents=True, exist_ok=True)
    json_path = output_root / "migration_inventory.json"
    markdown_path = output_root / "migration_inventory.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        "\n".join(
            [
                "# Advisory-R Exit Policy Migration Inventory",
                "",
                f"- Total references: {summary['totalHits']}",
                f"- Active research/Demo hard-gate references to migrate: {summary['activeHardGateHits']}",
                f"- Historical references preserved byte-for-byte: {summary['historicalHitsPreserved']}",
                f"- Live-boundary references intentionally preserved: {summary['liveBoundaryHitsPreserved']}",
                "",
                "Global replacement is forbidden. Follow each row's classification and action.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return json_path, markdown_path, payload


def _parse_repo(value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition("=")
    if not separator or not name or not raw_path:
        raise argparse.ArgumentTypeError("repo must use NAME=PATH")
    return name, Path(raw_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", action="append", type=_parse_repo, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    repo_roots = dict(args.repo)
    json_path, markdown_path, payload = write_inventory(repo_roots, args.output_root)
    print(
        json.dumps(
            {
                "json": str(json_path),
                "markdown": str(markdown_path),
                "summary": payload["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
