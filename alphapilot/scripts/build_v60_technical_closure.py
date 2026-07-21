"""Build V60.2 Adaptive Learning technical-closure evidence without side effects."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.adaptive_learning.v60_technical_closure import (
    build_v60_technical_closure_evidence,
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def _latest_model(path: Path) -> dict[str, Any]:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        row = connection.execute(
            """
            SELECT modelId, status, artifactPath, artifactSha256, payloadJson
            FROM Models
            ORDER BY createdAt DESC, modelId DESC
            LIMIT 1
            """
        ).fetchone()
    finally:
        connection.close()
    if row is None:
        raise ValueError("Model registry contains no model records")
    payload = json.loads(row[4])
    artifact = payload.get("artifact")
    if not isinstance(artifact, dict):
        raise ValueError(f"Model {row[0]} has no artifact payload")
    return {
        "modelId": row[0],
        "status": row[1],
        "artifactPath": row[2],
        "artifactSha256": row[3],
        "artifact": artifact,
    }


def _read_payload_rows(
    connection: sqlite3.Connection,
    *,
    table: str,
    columns: Sequence[str],
) -> list[dict[str, Any]]:
    available = {
        str(row[1])
        for row in connection.execute(f'PRAGMA table_info("{table}")').fetchall()
    }
    if not available:
        return []
    selected = [column for column in columns if column in available]
    if "payloadJson" not in selected and "payloadJson" in available:
        selected.append("payloadJson")
    rows: list[dict[str, Any]] = []
    for values in connection.execute(
        f'SELECT {", ".join(selected)} FROM "{table}"'
    ).fetchall():
        record = dict(zip(selected, values, strict=True))
        payload = record.pop("payloadJson", None)
        parsed = json.loads(payload) if isinstance(payload, str) and payload else {}
        if not isinstance(parsed, dict):
            parsed = {}
        rows.append({**parsed, **record})
    return rows


def _adaptive_evidence(path: Path | None) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    if path is None or not path.is_file():
        return [], []
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        decisions = _read_payload_rows(
            connection,
            table="AdaptiveModelDecisions",
            columns=("modelDecisionId", "modelMode", "environment", "payloadJson"),
        )
        samples = _read_payload_rows(
            connection,
            table="AdaptiveLearningSamples",
            columns=("learningSampleId", "modelDecisionId", "sourceEnvironment", "payloadJson"),
        )
    finally:
        connection.close()
    return decisions, samples


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--production-registry", type=Path, required=True)
    parser.add_argument("--prior-readiness", type=Path, required=True)
    parser.add_argument("--model-registry-db", type=Path, required=True)
    parser.add_argument("--factor-campaign", type=Path, required=True)
    parser.add_argument("--registry-audit", type=Path, required=True)
    parser.add_argument("--factor-benchmark", type=Path, required=True)
    parser.add_argument("--qlib-readiness", type=Path, required=True)
    parser.add_argument("--adaptive-db", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)

    generated_at = args.generated_at or datetime.now(UTC).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    decisions, outcomes = _adaptive_evidence(
        args.adaptive_db.expanduser().resolve() if args.adaptive_db else None
    )
    result = build_v60_technical_closure_evidence(
        output_dir=args.output_dir,
        generated_at=generated_at,
        production_registry=_load_json(args.production_registry.expanduser().resolve()),
        prior_readiness=_load_json(args.prior_readiness.expanduser().resolve()),
        model_record=_latest_model(args.model_registry_db.expanduser().resolve()),
        factor_campaign=_load_json(args.factor_campaign.expanduser().resolve()),
        registry_audit=_load_json(args.registry_audit.expanduser().resolve()),
        factor_benchmark=_load_json(args.factor_benchmark.expanduser().resolve()),
        qlib_readiness=_load_json(args.qlib_readiness.expanduser().resolve()),
        decisions=decisions,
        reconciled_outcomes=outcomes,
    )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
