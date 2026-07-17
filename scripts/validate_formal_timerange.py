"""Validate formal input hashes, timerange bounds, and output isolation."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.formal_validation.timerange_io_guard import build_formal_io_contract


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--input", dest="inputs", type=Path, action="append", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--requested-start", required=True)
    parser.add_argument("--requested-end", required=True)
    parser.add_argument("--allowed-start", required=True)
    parser.add_argument("--allowed-end", required=True)
    parser.add_argument("--forbidden-root", type=Path, action="append", default=[])
    parser.add_argument("--contract-output", type=Path)
    args = parser.parse_args()
    contract = build_formal_io_contract(
        input_root=args.input_root,
        input_paths=args.inputs,
        output_root=args.output_root,
        requested_start=args.requested_start,
        requested_end=args.requested_end,
        allowed_start=args.allowed_start,
        allowed_end=args.allowed_end,
        forbidden_roots=args.forbidden_root,
    )
    if args.contract_output:
        write_json_atomic(args.contract_output, contract)
    print(json.dumps(contract, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
