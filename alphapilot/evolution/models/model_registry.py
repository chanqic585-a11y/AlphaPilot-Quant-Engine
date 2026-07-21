"""Persist immutable offline model artifacts as shadow candidates only."""

from __future__ import annotations

import json
from pathlib import Path

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import ModelRecord

from .trainer import TrainedModelArtifact


ALLOWED_MODEL_STATUSES = {"draft", "shadow_candidate", "shadow_approved", "archived"}


def register_model_artifact(
    *,
    repository: RegistryRepository,
    experiment_id: str,
    artifact: TrainedModelArtifact,
    status: str = "shadow_candidate",
    artifact_path: Path | str | None = None,
) -> ModelRecord:
    if status not in ALLOWED_MODEL_STATUSES:
        raise ValueError("Models may be registered only in draft or shadow lifecycle states")
    experiment = repository.get_experiment(experiment_id)
    if experiment is None:
        raise ValueError(f"Experiment is not registered: {experiment_id}")
    if experiment.status not in {"completed", "research_validated"}:
        raise ValueError(f"Experiment is not complete: {experiment_id}")
    resolved_artifact_path: Path | None = None
    artifact_sha256: str | None = None
    if artifact_path is not None:
        resolved_artifact_path = Path(artifact_path).expanduser().resolve()
        if not resolved_artifact_path.is_file():
            raise ValueError(f"Model artifact file does not exist: {resolved_artifact_path}")
        try:
            stored_artifact = json.loads(resolved_artifact_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ValueError("Model artifact file is not valid UTF-8 JSON") from error
        if stored_artifact != artifact.to_dict():
            raise ValueError("Model artifact file does not match the registered artifact")
        artifact_sha256 = sha256_file(resolved_artifact_path)

    payload = {
        "schemaVersion": "offline_model_registry_v2" if artifact_sha256 else "offline_model_registry_v1",
        "artifact": artifact.to_dict(),
        "artifactModelHash": artifact.modelHash,
        "experimentId": experiment_id,
        "lifecycleBoundary": "shadow_only",
        "autoReplacesDemo": False,
        "createsOrders": False,
    }
    model_identity = {"experimentId": experiment_id, "artifactModelHash": artifact.modelHash}
    if artifact_sha256:
        payload["artifactSha256"] = artifact_sha256
        model_identity["artifactSha256"] = artifact_sha256
    model_id = stable_hash(model_identity, prefix="model_record")
    return repository.create_model(
        ModelRecord(
            modelId=model_id,
            experimentId=experiment_id,
            algorithm=artifact.modelType,
            status=status,
            artifactPath=str(resolved_artifact_path) if resolved_artifact_path is not None else None,
            artifactSha256=artifact_sha256,
            payload=payload,
            contentHash=stable_hash(payload),
        )
    )
