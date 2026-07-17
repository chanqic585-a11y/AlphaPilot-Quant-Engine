"""Prepare immutable V17 sidecars and V18 pre-result capital-policy evidence."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.reports.v17_closeout_supplement import (
    build_v17_closeout_supplement,
    write_v17_closeout_supplement,
)
from alphapilot.reports.v18_pre_result_artifacts import (
    prepare_v18_pre_result_artifacts,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--original-evidence-commit", required=True)
    parser.add_argument("--final-closeout-commit", required=True)
    parser.add_argument("--local-tag", required=True)
    parser.add_argument("--tag-target", required=True)
    parser.add_argument("--upstream-commit")
    parser.add_argument("--remote-tag-exists", action="store_true")
    parser.add_argument("--branch-push-status", default="not_published")
    parser.add_argument(
        "--external-publication-review-status",
        default="pending_explicit_user_approval",
    )
    parser.add_argument("--remote-code-commit")
    parser.add_argument("--remote-preregistration-commit")
    parser.add_argument("--remote-v18-tag")
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    supplement = build_v17_closeout_supplement(
        repo_root,
        original_evidence_commit=args.original_evidence_commit,
        final_closeout_commit=args.final_closeout_commit,
        local_tag=args.local_tag,
        tag_target=args.tag_target,
        upstream_commit=args.upstream_commit,
        remote_tag_exists=args.remote_tag_exists,
        branch_push_status=args.branch_push_status,
        external_publication_review_status=(
            args.external_publication_review_status
        ),
    )
    sidecars = write_v17_closeout_supplement(supplement, repo_root)
    result = prepare_v18_pre_result_artifacts(
        source_repo_root=repo_root,
        output_repo_root=repo_root,
        v17_provenance_reference=(
            "reports/v13_27_1_17_closeout_supplement/"
            "v17_closeout_provenance_sidecar.json"
        ),
        remote_code_commit=args.remote_code_commit,
        remote_preregistration_commit=args.remote_preregistration_commit,
        remote_tag=args.remote_v18_tag,
    )
    output = {
        "campaignId": result["campaignId"],
        "route": result["route"],
        "campaignRoot": result["campaignRoot"].relative_to(repo_root).as_posix(),
        "preregistrationPath": result["preregistrationPath"]
        .relative_to(repo_root)
        .as_posix(),
        "v17Sidecars": {
            key: path.relative_to(repo_root).as_posix()
            for key, path in sidecars.items()
        },
    }
    print(json.dumps(output, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
