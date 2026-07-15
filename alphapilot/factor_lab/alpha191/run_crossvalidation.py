from __future__ import annotations

import argparse
from pathlib import Path

from .numeric_crossvalidation import write_numeric_crossvalidation


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/factor_lab/alpha191_numeric_crossvalidation.json"),
    )
    args = parser.parse_args()
    report = write_numeric_crossvalidation(args.output)
    return 1 if report["unexpectedMismatchCount"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
