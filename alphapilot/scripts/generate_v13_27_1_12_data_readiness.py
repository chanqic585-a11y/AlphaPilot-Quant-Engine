"""Generate the V13.27.1.12 public-data readiness closeout."""

from __future__ import annotations

import argparse
import hashlib
import json
import urllib.error
import urllib.request
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.derivatives_data.v13_27_1_12_reports import (
    generate_v13_27_1_12_reports,
)


def _public_probe(url: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url, headers={"User-Agent": "AlphaPilot-public-readiness-audit/13.27.1.12"}
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read()
            payload = json.loads(body)
            return {
                "url": url,
                "ok": 200 <= response.status < 300,
                "statusCode": response.status,
                "responseBytes": len(body),
                "responseSha256": hashlib.sha256(body).hexdigest(),
                "topLevelType": type(payload).__name__,
                "topLevelKeys": sorted(payload) if isinstance(payload, dict) else [],
            }
    except (OSError, TimeoutError, urllib.error.URLError, json.JSONDecodeError) as exc:
        return {
            "url": url,
            "ok": False,
            "statusCode": None,
            "errorType": type(exc).__name__,
            "error": str(exc)[:300],
        }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Publish V13.27.1.12 data-readiness decisions without running a campaign."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--checked-at")
    parser.add_argument(
        "--run",
        action="store_true",
        help="Write the canonical closeout reports. Without this flag the command is plan-only.",
    )
    return parser


def main(
    argv: Sequence[str] | None = None,
    *,
    generator: Callable[..., dict[str, Any]] = generate_v13_27_1_12_reports,
) -> int:
    args = _parser().parse_args(argv)
    if not args.run:
        print(
            json.dumps(
                {
                    "status": "plan_only",
                    "repoRoot": str(args.repo_root.resolve()),
                    "dataRoot": str(args.data_root.resolve()),
                    "campaignWillRun": False,
                },
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
        )
        return 0

    checked_at = args.checked_at or datetime.now(UTC).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )
    result = generator(
        repo_root=args.repo_root.resolve(),
        data_root=args.data_root.resolve(),
        checked_at=checked_at,
        probe=_public_probe,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
