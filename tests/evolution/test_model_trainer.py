from __future__ import annotations

import math
import tempfile
import unittest
from pathlib import Path

from alphapilot.evolution.evaluation.purged_walk_forward import build_purged_walk_forward
from alphapilot.evolution.models.trainer import (
    TrainingDataset,
    predict_probabilities,
    train_logistic_baseline,
    train_tree_boosting_challenger,
)
from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import (
    DataSnapshotRecord,
    FactorDefinitionRecord,
    FactorRunRecord,
)


def register_factor_run(repository: RegistryRepository) -> str:
    snapshot = DataSnapshotRecord(
        dataSnapshotId="snapshot_model_test",
        source="unit_test",
        exchange="okx",
        marketType="swap",
        timeframe="1h",
        startTime=None,
        endTime=None,
        pointInTimeCutoff="2026-01-01T00:00:00+00:00",
        manifest={"files": []},
        contentHash=stable_hash({"snapshot": "model_test"}),
    )
    factor = FactorDefinitionRecord(
        factorDefinitionId="factor_model_test",
        name="Model test factor",
        version="v1",
        expression="close",
        definition={"researchOnly": True},
        contentHash=stable_hash({"factor": "model_test"}),
    )
    repository.create_data_snapshot(snapshot)
    repository.create_factor_definition(factor)
    payload = {"rowCount": 60, "pointInTimeValidated": True}
    run = FactorRunRecord(
        factorRunId="factor_run_model_test",
        factorDefinitionId=factor.factorDefinitionId,
        dataSnapshotId=snapshot.dataSnapshotId,
        codeCommit="unit_test",
        configHash=stable_hash({"config": "model_test"}),
        resultPath=None,
        resultSha256=None,
        status="completed",
        payload=payload,
        contentHash=stable_hash(payload),
    )
    repository.create_factor_run(run)
    return run.factorRunId


def training_dataset(factor_run_id: str) -> TrainingDataset:
    features = []
    labels = []
    for index in range(60):
        x1 = (index - 30) / 10
        x2 = math.sin(index / 5)
        features.append([x1, x2])
        labels.append(1 if x1 + 0.3 * x2 > 0 else 0)
    manifest = build_purged_walk_forward(
        sample_count=60,
        min_train_size=20,
        test_size=10,
        label_horizon=2,
        embargo_size=2,
        max_holding_period=2,
        min_folds=3,
    )
    return TrainingDataset(
        featureNames=("factor_a", "factor_b"),
        features=features,
        labels=labels,
        factorRunIds=(factor_run_id,),
        foldManifest=manifest,
    )


class ModelTrainerTests(unittest.TestCase):
    def test_logistic_and_tree_challenger_are_deterministic_and_registered_input_only(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                factor_run_id = register_factor_run(repository)
                dataset = training_dataset(factor_run_id)
                logistic = train_logistic_baseline(dataset, repository=repository)
                logistic_repeat = train_logistic_baseline(dataset, repository=repository)
                challenger = train_tree_boosting_challenger(
                    dataset,
                    repository=repository,
                    estimator_count=8,
                )
            finally:
                connection.close()

        self.assertEqual(logistic.modelHash, logistic_repeat.modelHash)
        self.assertEqual(logistic.modelType, "logistic_regression")
        self.assertEqual(challenger.modelType, "gradient_boosted_stumps")
        self.assertGreaterEqual(logistic.metrics["accuracy"], 0.75)
        self.assertGreaterEqual(challenger.metrics["accuracy"], 0.75)
        probabilities = predict_probabilities(challenger, dataset.features)
        self.assertEqual(len(probabilities), 60)
        self.assertTrue(all(0 <= value <= 1 for value in probabilities))
        self.assertEqual(logistic.trainingEvidence["factorRunIds"], [factor_run_id])
        self.assertEqual(
            logistic.trainingEvidence["foldManifestHash"],
            dataset.foldManifest.manifestHash,
        )

    def test_unregistered_factor_run_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            connection = connect_registry(Path(directory) / "registry.sqlite")
            try:
                repository = RegistryRepository(connection)
                dataset = training_dataset("missing_run")
                with self.assertRaises(ValueError):
                    train_logistic_baseline(dataset, repository=repository)
            finally:
                connection.close()


if __name__ == "__main__":
    unittest.main()
