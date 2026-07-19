"""Audit V36 TSMOM Formal readiness before preregistration or Formal reads."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from alphapilot.standard_replication.tsmom_engine import SELECTED_TSMOM_TRIALS
from alphapilot.standard_replication.tsmom_formal_readiness import (
    build_tsmom_formal_readiness,
    write_tsmom_formal_readiness_artifacts,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campaign-input", type=Path, required=True)
    parser.add_argument("--funding-root", type=Path)
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--candidate-id", action="append", dest="candidate_ids")
    parser.add_argument("--formal-start")
    parser.add_argument("--fold-count", type=int, default=3)
    parser.add_argument("--minimum-test-bars", type=int, default=60)
    parser.add_argument("--generated-at")
    parser.add_argument("--source-commit")
    parser.add_argument("--source-branch")
    return parser


def run(argv: Sequence[str] | None = None) -> dict[str, object]:
    args = _parser().parse_args(argv)
    campaign_path = args.campaign_input.resolve()
    campaign = json.loads(campaign_path.read_text(encoding="utf-8"))
    snapshot_path = Path(
        str((campaign.get("developmentReplay") or {}).get("snapshotManifestPath"))
    ).resolve()
    formal_start = args.formal_start or str(
        (campaign.get("comparisonPanel") or {}).get("developmentEnd") or ""
    )
    if not formal_start:
        raise ValueError("formal_start_missing")
    data_root = snapshot_path.parents[2]
    funding_root = (
        args.funding_root.resolve()
        if args.funding_root
        else data_root / "_alphapilot" / "canonical" / "okx" / "swap" / "funding"
    )
    campaign_id = str(campaign.get("campaignId") or campaign_path.stem)
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir
        else Path.cwd()
        / "reports"
        / "formal_validation"
        / "v36_tsmom_formal_handoff"
        / campaign_id
    )
    report = build_tsmom_formal_readiness(
        snapshot_manifest_path=snapshot_path,
        funding_root=funding_root,
        candidate_ids=args.candidate_ids or sorted(SELECTED_TSMOM_TRIALS),
        formal_start=formal_start,
        fold_count=args.fold_count,
        minimum_test_bars=args.minimum_test_bars,
        generated_at=args.generated_at,
        campaign_id=campaign_id,
        source_commit=args.source_commit,
        source_branch=args.source_branch,
    )
    written = write_tsmom_formal_readiness_artifacts(
        report, output_dir=output_dir
    )
    return {
        "status": report["status"],
        "campaignId": campaign_id,
        "readinessHash": report["readinessHash"],
        "formalReadyCandidateCount": report["formalReadyCandidateCount"],
        "blockedCandidateCount": report["blockedCandidateCount"],
        "formalRunCount": report["formalRunCount"],
        "formalInputReadCount": report["formalInputReadCount"],
        "resultReadCount": report["resultReadCount"],
        "lockedOosAccessCount": report["lockedOosAccessCount"],
        "releaseCount": report["releaseCount"],
        "artifacts": {name: str(path) for name, path in written.items()},
    }


def main() -> None:
    print(json.dumps(run(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
