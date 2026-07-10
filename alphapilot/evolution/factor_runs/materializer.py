"""Materialize factor and >=2R label artifacts from one immutable DataSnapshot."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.data_foundation.okx_public import TIMEFRAME_MILLISECONDS
from alphapilot.evolution.data_lineage.snapshot_registry import verify_data_snapshot
from alphapilot.evolution.factor_dsl import (
    canonical_expression,
    expression_id,
    parse_expression,
    validate_factor_expression,
)
from alphapilot.evolution.factor_dsl.ast import ast_to_dict
from alphapilot.evolution.factor_dsl.canonicalizer import canonicalize
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    DataSnapshotRecord,
    FactorDefinitionRecord,
    FactorRunRecord,
)

from .definitions import DEFAULT_FACTOR_SPECS, FACTOR_FIELD_TYPES, FactorSpec
from .evaluator import evaluate_factor_expression
from .labels import DirectionalLabelConfig, build_directional_labels


@dataclass(frozen=True)
class MaterializedFactorMatrix:
    dataSnapshotId: str
    timeframe: str
    path: str
    sha256: str
    configHash: str
    rowCount: int
    timestampCount: int
    instruments: tuple[str, ...]
    featureColumns: tuple[str, ...]
    factorDefinitionIds: tuple[str, ...]
    factorRunIds: tuple[str, ...]
    pointInTimeValidated: bool
    formalPromotionEligible: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _load_snapshot_frames(
    snapshot: DataSnapshotRecord,
    *,
    canonical_root: Path,
    timeframe: str,
) -> dict[str, pd.DataFrame]:
    if timeframe not in TIMEFRAME_MILLISECONDS:
        raise ValueError(f"Unsupported timeframe: {timeframe}")
    verification = verify_data_snapshot(snapshot.manifest, root=canonical_root)
    if not verification["valid"]:
        raise ValueError(f"DataSnapshot verification failed: {verification['errors']}")
    by_instrument: dict[str, list[pd.DataFrame]] = {}
    for item in snapshot.manifest.get("files") or []:
        relative = Path(str(item.get("path") or ""))
        parts = relative.parts
        if len(parts) < 6 or relative.suffix.lower() != ".parquet":
            continue
        if parts[-2].lower() != timeframe:
            continue
        instrument_id = parts[-3].upper()
        path = (canonical_root / relative).resolve()
        try:
            path.relative_to(canonical_root.resolve())
        except ValueError as exc:
            raise ValueError(f"Snapshot path escapes canonical root: {relative}") from exc
        frame = pd.read_parquet(
            path,
            columns=["timestamp_ms", "date", "open", "high", "low", "close", "volume"],
        )
        by_instrument.setdefault(instrument_id, []).append(frame)
    if not by_instrument:
        raise ValueError(f"Snapshot contains no {timeframe} OHLCV files")

    cutoff_ms = int(pd.Timestamp(snapshot.pointInTimeCutoff).timestamp() * 1000)
    interval_ms = TIMEFRAME_MILLISECONDS[timeframe]
    output: dict[str, pd.DataFrame] = {}
    for instrument_id, fragments in sorted(by_instrument.items()):
        frame = pd.concat(fragments, ignore_index=True)
        frame["timestamp_ms"] = pd.to_numeric(frame["timestamp_ms"], errors="coerce")
        frame = frame.dropna(subset=["timestamp_ms"]).copy()
        frame["timestamp_ms"] = frame["timestamp_ms"].astype("int64")
        frame = frame[frame["timestamp_ms"] <= cutoff_ms]
        frame = frame.sort_values("timestamp_ms").reset_index(drop=True)
        if frame["timestamp_ms"].duplicated().any():
            raise ValueError(f"Duplicate timestamps in snapshot group: {instrument_id}:{timeframe}")
        differences = frame["timestamp_ms"].diff().dropna()
        if not differences.empty and not bool((differences == interval_ms).all()):
            raise ValueError(f"Non-contiguous snapshot group: {instrument_id}:{timeframe}")
        for column in ("open", "high", "low", "close", "volume"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["date"] = pd.to_datetime(frame["timestamp_ms"], unit="ms", utc=True)
        output[instrument_id] = frame
    return output


def _register_definition(
    spec: FactorSpec,
    repository: RegistryRepository,
) -> tuple[FactorDefinitionRecord, Any, str]:
    parsed = parse_expression(spec.expression)
    canonical = canonicalize(parsed)
    validation = validate_factor_expression(canonical, field_types=FACTOR_FIELD_TYPES)
    if not validation.valid:
        raise ValueError(f"Invalid factor {spec.factorId}: {validation.issues}")
    canonical_text = canonical_expression(canonical)
    factor_expression_id = expression_id(canonical)
    definition = {
        "schemaVersion": "point_in_time_factor_definition_v1",
        "factorId": spec.factorId,
        "name": spec.name,
        "version": spec.version,
        "expression": spec.expression,
        "canonicalExpression": canonical_text,
        "expressionId": factor_expression_id,
        "canonicalAst": ast_to_dict(canonical),
        "requiredFields": validation.requiredFields,
        "domainRequirements": validation.domainRequirements,
        "pointInTimeOnly": True,
        "futureOffsetsAllowed": False,
        "researchOnly": True,
    }
    definition_id = stable_hash(
        {
            "factorId": spec.factorId,
            "version": spec.version,
            "canonicalExpression": canonical_text,
        },
        prefix="factor_definition",
    )
    record = repository.create_factor_definition(
        FactorDefinitionRecord(
            factorDefinitionId=definition_id,
            name=spec.name,
            version=spec.version,
            expression=spec.expression,
            definition=definition,
            contentHash=stable_hash(definition),
        )
    )
    return record, canonical, factor_expression_id


def materialize_factor_matrix(
    *,
    snapshot: DataSnapshotRecord,
    repository: RegistryRepository,
    canonical_root: Path | str = "data/market/canonical",
    output_root: Path | str = "data/market/factor_runs",
    timeframe: str = "4h",
    factor_specs: Iterable[FactorSpec] = DEFAULT_FACTOR_SPECS,
    label_config: DirectionalLabelConfig | None = None,
    code_commit: str | None = None,
) -> MaterializedFactorMatrix:
    settings = label_config or DirectionalLabelConfig()
    settings.validate()
    specs = tuple(factor_specs)
    if not specs:
        raise ValueError("At least one factor specification is required")
    definitions = [_register_definition(spec, repository) for spec in specs]
    frames = _load_snapshot_frames(
        snapshot,
        canonical_root=Path(canonical_root).resolve(),
        timeframe=timeframe,
    )
    feature_columns = tuple(f"factor_{spec.factorId}" for spec in specs)
    raw_non_null = {column: 0 for column in feature_columns}
    raw_row_count = 0
    materialized_parts: list[pd.DataFrame] = []
    source_rows: dict[str, int] = {}
    for instrument_id, source in frames.items():
        frame = source.copy()
        source_rows[instrument_id] = len(frame)
        raw_row_count += len(frame)
        for spec, (_, expression, _) in zip(specs, definitions, strict=True):
            column = f"factor_{spec.factorId}"
            frame[column] = evaluate_factor_expression(expression, frame)
            raw_non_null[column] += int(frame[column].notna().sum())
        risk_distance = frame["factor_atr_pct_14"] * frame["close"]
        frame = pd.concat(
            [
                frame,
                build_directional_labels(
                    frame,
                    risk_distance=risk_distance,
                    config=settings,
                ),
            ],
            axis=1,
        )
        frame["instrument_id"] = instrument_id
        frame["timeframe"] = timeframe
        availability_columns = [
            "label_long_available",
            "label_short_available",
            "label_long_delayed_available",
            "label_short_delayed_available",
        ]
        finite = np.isfinite(frame[list(feature_columns)].to_numpy(dtype="float64")).all(axis=1)
        available = frame[availability_columns].all(axis=1)
        materialized_parts.append(frame.loc[finite & available].copy())
    panel = pd.concat(materialized_parts, ignore_index=True)
    panel = panel.sort_values(["timestamp_ms", "instrument_id"]).reset_index(drop=True)
    if panel.empty:
        raise ValueError("No complete point-in-time factor and label rows were materialized")

    config_payload = {
        "schemaVersion": "factor_matrix_config_v1",
        "dataSnapshotId": snapshot.dataSnapshotId,
        "timeframe": timeframe,
        "factors": [
            {
                "factorId": spec.factorId,
                "version": spec.version,
                "expression": spec.expression,
                "factorDefinitionId": definition.factorDefinitionId,
            }
            for spec, (definition, _, _) in zip(specs, definitions, strict=True)
        ],
        "labelConfig": asdict(settings),
        "entryRule": "decision_at_t_entry_at_next_bar_open",
        "sameBarAmbiguity": "stop_first",
    }
    config_hash = stable_hash(config_payload, prefix="factor_matrix_config")
    output = Path(output_root).resolve() / snapshot.dataSnapshotId / timeframe
    output.mkdir(parents=True, exist_ok=True)
    matrix_path = output / f"factor-matrix-{config_hash.split('_')[-1][:16]}.parquet"
    temporary = matrix_path.with_name(f"{matrix_path.name}.tmp")
    panel.to_parquet(temporary, index=False, compression="zstd")
    os.replace(temporary, matrix_path)
    matrix_sha = sha256_file(matrix_path)
    formal_eligible = bool(snapshot.manifest.get("metadata", {}).get("formalPromotionEligible"))
    factor_run_ids: list[str] = []
    definition_ids: list[str] = []
    for spec, (definition, _, factor_expression_id), column in zip(
        specs, definitions, feature_columns, strict=True
    ):
        definition_ids.append(definition.factorDefinitionId)
        coverage = raw_non_null[column] / raw_row_count if raw_row_count else 0.0
        payload = {
            "schemaVersion": "materialized_factor_run_v1",
            "factorId": spec.factorId,
            "expressionId": factor_expression_id,
            "resultColumn": column,
            "dataSnapshotId": snapshot.dataSnapshotId,
            "timeframe": timeframe,
            "sourceRowCount": raw_row_count,
            "materializedRowCount": len(panel),
            "timestampCount": int(panel["timestamp_ms"].nunique()),
            "instrumentCount": int(panel["instrument_id"].nunique()),
            "coverage": coverage,
            "nullRate": 1 - coverage,
            "pointInTimeValidated": True,
            "futureOffsetsUsed": False,
            "labelConfig": asdict(settings),
            "evidenceClass": (
                "formal_market_data"
                if formal_eligible
                else "engineering_smoke_provenance_blocked"
            ),
            "formalPromotionEligible": formal_eligible,
            "createsOrders": False,
        }
        run_id = stable_hash(
            {
                "factorDefinitionId": definition.factorDefinitionId,
                "dataSnapshotId": snapshot.dataSnapshotId,
                "configHash": config_hash,
                "resultSha256": matrix_sha,
            },
            prefix="factor_run",
        )
        repository.create_factor_run(
            FactorRunRecord(
                factorRunId=run_id,
                factorDefinitionId=definition.factorDefinitionId,
                dataSnapshotId=snapshot.dataSnapshotId,
                codeCommit=code_commit,
                configHash=config_hash,
                resultPath=str(matrix_path),
                resultSha256=matrix_sha,
                status="completed",
                payload=payload,
                contentHash=stable_hash(payload),
            )
        )
        factor_run_ids.append(run_id)
    manifest = {
        "schemaVersion": "materialized_factor_matrix_v1",
        "dataSnapshotId": snapshot.dataSnapshotId,
        "timeframe": timeframe,
        "path": str(matrix_path),
        "sha256": matrix_sha,
        "configHash": config_hash,
        "rowCount": len(panel),
        "timestampCount": int(panel["timestamp_ms"].nunique()),
        "instruments": sorted(panel["instrument_id"].unique().tolist()),
        "featureColumns": list(feature_columns),
        "sourceRows": source_rows,
        "factorDefinitionIds": definition_ids,
        "factorRunIds": factor_run_ids,
        "pointInTimeValidated": True,
        "formalPromotionEligible": formal_eligible,
        "rawSourceProvenance": snapshot.manifest.get("metadata", {}).get("provenanceStatus"),
        "createsOrders": False,
    }
    write_json_atomic(matrix_path.with_suffix(".manifest.json"), manifest)
    return MaterializedFactorMatrix(
        dataSnapshotId=snapshot.dataSnapshotId,
        timeframe=timeframe,
        path=str(matrix_path),
        sha256=matrix_sha,
        configHash=config_hash,
        rowCount=len(panel),
        timestampCount=int(panel["timestamp_ms"].nunique()),
        instruments=tuple(manifest["instruments"]),
        featureColumns=feature_columns,
        factorDefinitionIds=tuple(definition_ids),
        factorRunIds=tuple(factor_run_ids),
        pointInTimeValidated=True,
        formalPromotionEligible=formal_eligible,
    )
