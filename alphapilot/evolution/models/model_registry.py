"""Persist immutable offline model artifacts as shadow candidates only."""

from __future__ import annotations

from alphapilot.evolution.registry.hashing import stable_hash
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
) -> ModelRecord:
    if status not in ALLOWED_MODEL_STATUSES:
        raise ValueError("Models may be registered only in draft or shadow lifecycle states")
    experiment = repository.get_experiment(experiment_id)
    if experiment is None:
        raise ValueError(f"Experiment is not registered: {experiment_id}")
    if experiment.status not in {"completed", "research_validated"}:
        raise ValueError(f"Experiment is not complete: {experiment_id}")
    payload = {
        "schemaVersion": "offline_model_registry_v1",
        "artifact": artifact.to_dict(),
        "artifactModelHash": artifact.modelHash,
        "experimentId": experiment_id,
        "lifecycleBoundary": "shadow_only",
        "autoReplacesDemo": False,
        "createsOrders": False,
    }
    model_id = stable_hash(
        {"experimentId": experiment_id, "artifactModelHash": artifact.modelHash},
        prefix="model_record",
    )
    return repository.create_model(
        ModelRecord(
            modelId=model_id,
            experimentId=experiment_id,
            algorithm=artifact.modelType,
            status=status,
            artifactPath=None,
            artifactSha256=None,
            payload=payload,
            contentHash=stable_hash(payload),
        )
    )
