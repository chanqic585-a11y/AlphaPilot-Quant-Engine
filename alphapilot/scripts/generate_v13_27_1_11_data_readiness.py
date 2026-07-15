"""Generate the fail-closed V13.27.1.11 derivatives-data evidence bundle."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.derivatives_data.data_readiness_reports import (
    generate_data_readiness_reports,
)


def _command_output(command: str, cwd: Path | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=cwd,
        shell=True,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Audit existing public derivatives data and stop before campaign execution "
            "when fewer than two top-level directions are formally data-ready."
        )
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--external-data-root", type=Path, required=True)
    parser.add_argument("--checked-at")
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    generator: Callable[..., dict[str, Any]] = generate_data_readiness_reports,
) -> int:
    args = _parser().parse_args(argv)
    checked_at = args.checked_at or datetime.now(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    result = generator(
        repo_root=args.repo_root.resolve(),
        external_data_root=args.external_data_root.resolve(),
        checked_at=checked_at,
        command_output=_command_output,
        python_executable=sys.executable,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
