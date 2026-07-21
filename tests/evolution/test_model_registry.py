from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.models.model_registry import register_model_artifact
from alphapilot.evolution.models.trainer import TrainedModelArtifact
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import canonical_json, sha256_file, stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import ExperimentRecord


def model_artifact() -> TrainedModelArtifact:
    core = {
        "modelType": "logistic_regression",
        "featureNames": ["factor_a"],
        "parameters": {"weights": [1.0], "intercept": 0.0, "means": [0.0], "scales": [1.0]},
        "metrics": {"logLoss": 0.4, "brierScore": 0.12, "accuracy": 0.8},
        "trainingEvidence": {
            "factorRunIds": ["run_1"],
            "foldManifestHash": "walk_forward_test",
            "pointInTimeValidated": True,
        },
    }
    return TrainedModelArtifact(
        modelType=core["modelType"],
        featureNames=("factor_a",),
        parameters=core["parameters"],
        metrics=core["metrics"],
        trainingEvidence=core["trainingEvidence"],
        modelHash=stable_hash(core, prefix="model"),
    )


class ModelRegistryTests(unittest.TestCase):
    def test_model_is_registered_idempotently_as_shadow_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                payload = {"purpose": "unit_test"}
                repository.create_experiment(
                    ExperimentRecord(
                        experimentId="experiment_1",
                        experimentType="offline_classifier",
                        status="completed",
                        dataSnapshotId=None,
                        splitDefinition={"foldManifestHash": "walk_forward_test"},
                        costModel={},
                        parameters={},
                        codeCommit="unit_test",
                        payload=payload,
                        contentHash=stable_hash(payload),
                    )
                )
                first = register_model_artifact(
                    repository=repository,
                    experiment_id="experiment_1",
                    artifact=model_artifact(),
                )
                second = register_model_artifact(
                    repository=repository,
                    experiment_id="experiment_1",
                    artifact=model_artifact(),
                )
                model_count = repository.count("Models")
                with self.assertRaises(ValueError):
                    register_model_artifact(
                        repository=repository,
                        experiment_id="experiment_1",
                        artifact=model_artifact(),
                        status="demo_active",
                    )
            finally:
                connection.close()

        self.assertEqual(first, second)
        self.assertEqual(first.status, "shadow_candidate")
        self.assertEqual(model_count, 1)

    def test_missing_experiment_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                with self.assertRaises(ValueError):
                    register_model_artifact(
                        repository=RegistryRepository(connection),
                        experiment_id="missing",
                        artifact=model_artifact(),
                    )
            finally:
                connection.close()

    def test_model_binary_is_bound_without_mutating_legacy_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                payload = {"purpose": "unit_test"}
                repository.create_experiment(
                    ExperimentRecord(
                        experimentId="experiment_1",
                        experimentType="offline_classifier",
                        status="completed",
                        dataSnapshotId=None,
                        splitDefinition={"foldManifestHash": "walk_forward_test"},
                        costModel={},
                        parameters={},
                        codeCommit="unit_test",
                        payload=payload,
                        contentHash=stable_hash(payload),
                    )
                )
                artifact = model_artifact()
                legacy = register_model_artifact(
                    repository=repository,
                    experiment_id="experiment_1",
                    artifact=artifact,
                )
                artifact_path = root / "models" / f"{artifact.modelHash}.json"
                artifact_path.parent.mkdir(parents=True)
                artifact_path.write_text(canonical_json(artifact.to_dict()), encoding="utf-8")
                expected_artifact_sha256 = sha256_file(artifact_path)

                bound = register_model_artifact(
                    repository=repository,
                    experiment_id="experiment_1",
                    artifact=artifact,
                    artifact_path=artifact_path,
                )
                stored_legacy = repository.get_model(legacy.modelId)
                stored_bound = repository.get_model(bound.modelId)
            finally:
                connection.close()

        self.assertNotEqual(legacy.modelId, bound.modelId)
        self.assertIsNone(stored_legacy.artifactPath)
        self.assertIsNone(stored_legacy.artifactSha256)
        self.assertEqual(stored_bound.artifactPath, str(artifact_path.resolve()))
        self.assertEqual(stored_bound.artifactSha256, expected_artifact_sha256)
        self.assertEqual(stored_bound.payload["schemaVersion"], "offline_model_registry_v2")
        self.assertEqual(stored_bound.payload["lifecycleBoundary"], "shadow_only")
        self.assertFalse(stored_bound.payload["createsOrders"])

    def test_model_binary_payload_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            connection = connect_registry(root / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                payload = {"purpose": "unit_test"}
                repository.create_experiment(
                    ExperimentRecord(
                        experimentId="experiment_1",
                        experimentType="offline_classifier",
                        status="completed",
                        dataSnapshotId=None,
                        splitDefinition={"foldManifestHash": "walk_forward_test"},
                        costModel={},
                        parameters={},
                        codeCommit="unit_test",
                        payload=payload,
                        contentHash=stable_hash(payload),
                    )
                )
                artifact_path = root / "wrong.json"
                artifact_path.write_text('{"modelHash":"wrong"}', encoding="utf-8")
                with self.assertRaisesRegex(ValueError, "does not match"):
                    register_model_artifact(
                        repository=repository,
                        experiment_id="experiment_1",
                        artifact=model_artifact(),
                        artifact_path=artifact_path,
                    )
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
