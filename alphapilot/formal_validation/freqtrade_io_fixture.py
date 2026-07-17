"""Build Phase 2 fixture-only evidence for the formal Freqtrade I/O guard."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping

from .freqtrade_io_guard import (
    audit_freqtrade_access_log,
    build_freqtrade_io_contract,
    guarded_read_bytes,
)


RUNTIME_IMAGE = (
    "freqtradeorg/freqtrade@"
    "sha256:87aa5c6d65359b34e9d99a0bb260a38c0efe0315253811e6f48c2afe8f278a6a"
)
FROZEN_START = "2021-01-22T04:00:00Z"
FROZEN_END = "2026-05-15T04:00:00Z"
FIXTURE_NAME = "ETH_USDT_USDT-4h-futures.feather"
FIXTURE_CONTENT = b"alphapilot-phase2-synthetic-non-holdout-fixture-v1\n"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    temporary.replace(path)


def build_phase2_io_fixture_evidence(
    *,
    fixture_root: Path,
    evidence_root: Path,
    forbidden_locked_oos_root: Path,
) -> dict[str, Any]:
    """Create a tiny non-performance fixture and prove guarded access to it."""

    fixture_root = Path(fixture_root).resolve(strict=False)
    evidence_root = Path(evidence_root).resolve(strict=False)
    forbidden_locked_oos_root = Path(forbidden_locked_oos_root).resolve(strict=False)
    fixture_root.mkdir(parents=True, exist_ok=True)
    evidence_root.mkdir(parents=True, exist_ok=True)

    fixture_file = fixture_root / FIXTURE_NAME
    if fixture_file.exists() and fixture_file.read_bytes() != FIXTURE_CONTENT:
        raise RuntimeError("Phase 2 fixture exists with unexpected content")
    fixture_file.write_bytes(FIXTURE_CONTENT)

    contract = build_freqtrade_io_contract(
        input_root=fixture_root,
        allowed_files=[fixture_file],
        output_root=evidence_root,
        requested_start=FROZEN_START,
        requested_end=FROZEN_END,
        allowed_start=FROZEN_START,
        allowed_end=FROZEN_END,
        forbidden_roots=[forbidden_locked_oos_root],
        runtime_image=RUNTIME_IMAGE,
        runtime_command=[
            "freqtrade",
            "backtesting",
            "--strategy",
            "AlphaPilotS01BearRecovery4H",
            "--timerange",
            "20210122-20260515",
        ],
    )

    raw_access_log = evidence_root / "freqtrade_io_fixture_access_log.jsonl"
    raw_access_log.unlink(missing_ok=True)
    guarded_read_bytes(
        contract,
        fixture_file,
        raw_access_log,
        purpose="phase2_fixture_guard_smoke",
    )
    access_audit = audit_freqtrade_access_log(contract, raw_access_log)
    if access_audit["status"] != "passed":
        raise RuntimeError("Phase 2 fixture access audit did not pass")

    events = [
        json.loads(line)
        for line in raw_access_log.read_text(encoding="utf-8").splitlines()
        if line
    ]
    manifest = {
        "schemaVersion": "alphapilot_non_holdout_fixture_manifest_v1",
        "status": "ready",
        "fixtureOnly": True,
        "notFormalMarketData": True,
        "inputRoot": contract["inputRoot"],
        "allowedStart": contract["allowedStart"],
        "allowedEndExclusive": contract["allowedEndExclusive"],
        "allowedFileCount": contract["allowedFileCount"],
        "files": contract["allowedFiles"],
        "contractHash": contract["contractHash"],
    }
    access_report = {
        "schemaVersion": "alphapilot_freqtrade_io_fixture_access_log_v1",
        **access_audit,
        "events": events,
    }
    readiness = {
        "schemaVersion": "alphapilot_freqtrade_io_guard_readiness_v1",
        "status": "passed",
        "fixtureOnly": True,
        "contractHash": contract["contractHash"],
        "runtimeImage": contract["runtimeImage"],
        "networkMode": contract["networkMode"],
        "repositoryReadOnly": contract["repositoryReadOnly"],
        "lockedOosMounted": contract["lockedOosMounted"],
        "accessAudit": access_audit,
        "formalResultCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    _write_json(evidence_root / "non_holdout_data_root_manifest.json", manifest)
    _write_json(evidence_root / "freqtrade_io_fixture_access_log.json", access_report)
    _write_json(evidence_root / "freqtrade_io_guard_readiness.json", readiness)
    return readiness


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(
        description="Build fixture-only Phase 2 Freqtrade I/O guard evidence."
    )
    parser.add_argument(
        "--fixture-root",
        type=Path,
        default=repo_root
        / "reports"
        / "formal_validation"
        / "v13_27_1_17_s01_phase2_fixture_data",
    )
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=repo_root
        / "reports"
        / "formal_validation"
        / "v13_27_1_17_s01_phase2_readiness",
    )
    parser.add_argument(
        "--forbidden-locked-oos-root",
        type=Path,
        default=repo_root / "research" / "locked_oos",
    )
    args = parser.parse_args()
    result = build_phase2_io_fixture_evidence(
        fixture_root=args.fixture_root,
        evidence_root=args.evidence_root,
        forbidden_locked_oos_root=args.forbidden_locked_oos_root,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
