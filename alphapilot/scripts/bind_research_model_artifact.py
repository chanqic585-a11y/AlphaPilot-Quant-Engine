"""Bind immutable research-model bytes to a new shadow registry record."""

from __future__ import annotations

import argparse
import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.evolution.models.model_registry import register_model_artifact
from alphapilot.evolution.models.trainer import TrainedModelArtifact
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _artifact_from_payload(payload: dict[str, Any]) -> TrainedModelArtifact:
    return TrainedModelArtifact(
        modelType=str(payload["modelType"]),
        featureNames=tuple(str(value) for value in payload["featureNames"]),
        parameters=dict(payload["parameters"]),
        metrics=dict(payload["metrics"]),
        trainingEvidence=dict(payload["trainingEvidence"]),
        modelHash=str(payload["modelHash"]),
        researchOnly=payload.get("researchOnly") is True,
    )


def _backup_registry(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    source_connection = sqlite3.connect(source)
    destination_connection = sqlite3.connect(destination)
    try:
        source_connection.backup(destination_connection)
    finally:
        destination_connection.close()
        source_connection.close()


def bind_research_model_artifact(
    *,
    registry_path: Path,
    model_id: str,
    artifact_path: Path,
    backup_path: Path,
    generated_at: str,
) -> dict[str, Any]:
    """Create a new immutable binary-bound record and preserve the source row."""

    registry_path = registry_path.expanduser().resolve()
    artifact_path = artifact_path.expanduser().resolve()
    backup_path = backup_path.expanduser().resolve()
    if not registry_path.is_file():
        raise ValueError(f"Model registry does not exist: {registry_path}")
    _backup_registry(registry_path, backup_path)

    connection = connect_registry(registry_path)
    try:
        repository = RegistryRepository(connection)
        source = repository.get_model(model_id)
        if source is None:
            raise ValueError(f"Model is not registered: {model_id}")
        artifact_payload = source.payload.get("artifact")
        if not isinstance(artifact_payload, dict):
            raise ValueError(f"Model has no artifact payload: {model_id}")
        artifact = _artifact_from_payload(artifact_payload)
        if artifact.researchOnly is not True:
            raise ValueError("Only research-only models may be bound by this command")
        bound = register_model_artifact(
            repository=repository,
            experiment_id=source.experimentId,
            artifact=artifact,
            status="shadow_candidate",
            artifact_path=artifact_path,
        )
        preserved = repository.get_model(model_id)
    finally:
        connection.close()

    receipt_core = {
        "schemaVersion": "v60_2_research_model_registry_binding_v1",
        "generatedAt": generated_at,
        "status": "completed_research_only",
        "sourceModelId": model_id,
        "sourceModelPreserved": preserved == source,
        "boundModelId": bound.modelId,
        "modelHash": artifact.modelHash,
        "artifactPath": bound.artifactPath,
        "artifactSha256": bound.artifactSha256,
        "artifactDigestVerified": bound.artifactSha256 == sha256_file(artifact_path),
        "registryBackupPath": str(backup_path),
        "lifecycleBoundary": "shadow_only",
        "researchOnly": True,
        "liveEligible": False,
        "grantsLiveAuthority": False,
        "createsOrders": False,
    }
    return {
        **receipt_core,
        "receiptHash": stable_hash(receipt_core, prefix="research_model_binding"),
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--generated-at")
    args = parser.parse_args(argv)
    generated_at = args.generated_at or datetime.now(UTC).replace(
        microsecond=0
    ).isoformat().replace("+00:00", "Z")
    receipt = bind_research_model_artifact(
        registry_path=args.registry,
        model_id=args.model_id,
        artifact_path=args.artifact,
        backup_path=args.backup,
        generated_at=generated_at,
    )
    _write_json_atomic(args.receipt, receipt)
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
