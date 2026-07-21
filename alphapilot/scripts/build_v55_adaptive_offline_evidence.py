"""Create a truthful V55.1 binding to existing factor and Qlib evidence."""

from __future__ import annotations

import argparse
import json
from collections.abc import Sequence
from pathlib import Path

from alphapilot.adaptive_learning.offline_evidence import build_offline_evidence
from alphapilot.data_foundation.checkpoint import write_json_atomic


def _read(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--factor-benchmark", type=Path)
    parser.add_argument("--factor-shortlist", type=Path)
    parser.add_argument("--qlib-preflight", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    root = args.repo_root.expanduser().resolve()
    factor_benchmark = args.factor_benchmark or root / "reports/factor_lab/factor_benchmark_report.json"
    factor_shortlist = args.factor_shortlist or root / "reports/factor_lab/factor_shortlist.json"
    qlib_preflight = args.qlib_preflight or root / "reports/v13_27_1_12/qlib_preflight.json"
    output = args.output or root / "reports/v55_1_adaptive_learning/offline_evidence_binding.json"
    result = build_offline_evidence(
        factor_benchmark=_read(factor_benchmark),
        factor_shortlist=_read(factor_shortlist),
        qlib_preflight=_read(qlib_preflight),
    )
    write_json_atomic(output, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
