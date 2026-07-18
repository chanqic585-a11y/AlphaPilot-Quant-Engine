"""Run the V18.3 real-signal structural certification before preregistration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from alphapilot.formal_validation.candidate_adapters import get_candidate_adapter
from alphapilot.formal_validation.formal_input import load_formal_input
from alphapilot.formal_validation.v18_2_contracts import verify_v18_2_preregistration
from alphapilot.formal_validation.v18_3_structural_certification import (
    certify_signal_evidence_structure,
    write_signal_evidence_structural_certification,
)


def certify(
    *,
    repo_root: Path,
    data_root: Path,
    preregistration_path: Path,
    candidate_id: str,
    output_root: Path,
) -> dict[str, object]:
    root = Path(repo_root).resolve(strict=True)
    adapter = get_candidate_adapter(candidate_id)
    bundle = load_formal_input(
        repo_root=root,
        data_root=Path(data_root).resolve(strict=True),
        preregistration_path=Path(preregistration_path).resolve(strict=True),
        candidate_id=candidate_id,
        candidate_adapter=adapter,
        preregistration_validator=verify_v18_2_preregistration,
    )
    result = certify_signal_evidence_structure(
        bundle=bundle, candidate_adapter=adapter
    )
    write_signal_evidence_structural_certification(
        output_root=output_root, certification=result
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--preregistration", type=Path, required=True)
    parser.add_argument("--candidate-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args(argv)
    result = certify(
        repo_root=args.repo_root,
        data_root=args.data_root,
        preregistration_path=args.preregistration,
        candidate_id=args.candidate_id,
        output_root=args.output_root,
    )
    print(
        json.dumps(
            {
                "status": result["status"],
                "route": result["route"],
                "rawEventCount": result["rawEventCount"],
                "assignedValidationEventCount": result[
                    "assignedValidationEventCount"
                ],
                "rankingEvidenceRecordCoveragePct": result[
                    "rankingEvidenceRecordCoveragePct"
                ],
                "rankingEvidenceStatusCoveragePct": result[
                    "rankingEvidenceStatusCoveragePct"
                ],
                "rankingEvidenceParityPct": result[
                    "rankingEvidenceParityPct"
                ],
                "blockers": result["blockers"],
            },
            ensure_ascii=True,
            sort_keys=True,
        )
    )
    return 0 if result["status"] == "certified" else 2


if __name__ == "__main__":
    raise SystemExit(main())

