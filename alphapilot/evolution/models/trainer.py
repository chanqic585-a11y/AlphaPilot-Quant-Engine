"""Deterministic offline classifiers tied to registered research evidence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import fmean
from typing import Any, Sequence

from alphapilot.evolution.evaluation.purged_walk_forward import WalkForwardManifest
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository


@dataclass(frozen=True)
class TrainingDataset:
    featureNames: tuple[str, ...]
    features: Sequence[Sequence[float]]
    labels: Sequence[int]
    factorRunIds: tuple[str, ...]
    foldManifest: WalkForwardManifest


@dataclass(frozen=True)
class TrainedModelArtifact:
    modelType: str
    featureNames: tuple[str, ...]
    parameters: dict[str, Any]
    metrics: dict[str, float]
    trainingEvidence: dict[str, Any]
    modelHash: str
    researchOnly: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "modelType": self.modelType,
            "featureNames": list(self.featureNames),
            "parameters": self.parameters,
            "metrics": self.metrics,
            "trainingEvidence": self.trainingEvidence,
            "modelHash": self.modelHash,
            "researchOnly": self.researchOnly,
        }


def _sigmoid(value: float) -> float:
    if value >= 0:
        return 1 / (1 + math.exp(-value))
    exponent = math.exp(value)
    return exponent / (1 + exponent)


def _validate_dataset(dataset: TrainingDataset, repository: RegistryRepository) -> list[list[float]]:
    rows = [list(map(float, row)) for row in dataset.features]
    labels = list(dataset.labels)
    if not rows or len(rows) != len(labels):
        raise ValueError("Aligned non-empty features and labels are required")
    if len(dataset.featureNames) == 0 or any(len(row) != len(dataset.featureNames) for row in rows):
        raise ValueError("Feature rows must match featureNames")
    if len(rows) != int(dataset.foldManifest.config.get("sampleCount") or 0):
        raise ValueError("Training rows must match the registered fold manifest sample count")
    if not all(math.isfinite(value) for row in rows for value in row):
        raise ValueError("Training features must be finite")
    if set(labels) - {0, 1} or len(set(labels)) < 2:
        raise ValueError("Training labels must contain both binary classes")
    if not dataset.factorRunIds:
        raise ValueError("At least one registered FactorRun is required")
    for run_id in dataset.factorRunIds:
        run = repository.get_factor_run(run_id)
        if run is None:
            raise ValueError(f"Unregistered FactorRun: {run_id}")
        if run.status not in {"completed", "research_validated"}:
            raise ValueError(f"FactorRun is not complete: {run_id}")
        if not bool(run.payload.get("pointInTimeValidated")):
            raise ValueError(f"FactorRun lacks point-in-time validation: {run_id}")
    if not dataset.foldManifest.manifestHash.startswith("walk_forward_"):
        raise ValueError("A registered purged walk-forward manifest is required")
    return rows


def _training_evidence(dataset: TrainingDataset, rows: list[list[float]]) -> dict[str, Any]:
    return {
        "factorRunIds": sorted(dataset.factorRunIds),
        "foldManifestHash": dataset.foldManifest.manifestHash,
        "foldCount": len(dataset.foldManifest.folds),
        "sampleCount": len(rows),
        "datasetHash": stable_hash(
            {
                "featureNames": list(dataset.featureNames),
                "features": rows,
                "labels": list(dataset.labels),
                "factorRunIds": sorted(dataset.factorRunIds),
                "foldManifestHash": dataset.foldManifest.manifestHash,
            },
            prefix="training_dataset",
        ),
        "pointInTimeValidated": True,
        "purgedWalkForward": True,
    }


def _classification_metrics(probabilities: list[float], labels: list[int]) -> dict[str, float]:
    clipped = [min(max(value, 1e-12), 1 - 1e-12) for value in probabilities]
    return {
        "logLoss": -fmean(
            label * math.log(probability) + (1 - label) * math.log(1 - probability)
            for probability, label in zip(clipped, labels, strict=True)
        ),
        "brierScore": fmean(
            (probability - label) ** 2
            for probability, label in zip(probabilities, labels, strict=True)
        ),
        "accuracy": sum(
            int(probability >= 0.5) == label
            for probability, label in zip(probabilities, labels, strict=True)
        )
        / len(labels),
        "positiveRate": fmean(labels),
    }


def _artifact(
    *,
    model_type: str,
    feature_names: tuple[str, ...],
    parameters: dict[str, Any],
    metrics: dict[str, float],
    evidence: dict[str, Any],
) -> TrainedModelArtifact:
    core = {
        "modelType": model_type,
        "featureNames": list(feature_names),
        "parameters": parameters,
        "metrics": metrics,
        "trainingEvidence": evidence,
        "researchOnly": True,
    }
    return TrainedModelArtifact(
        modelType=model_type,
        featureNames=feature_names,
        parameters=parameters,
        metrics=metrics,
        trainingEvidence=evidence,
        modelHash=stable_hash(core, prefix="model"),
    )


def train_logistic_baseline(
    dataset: TrainingDataset,
    *,
    repository: RegistryRepository,
    epochs: int = 500,
    learning_rate: float = 0.1,
    l2_penalty: float = 0.001,
) -> TrainedModelArtifact:
    rows = _validate_dataset(dataset, repository)
    labels = list(dataset.labels)
    feature_count = len(dataset.featureNames)
    means = [fmean(row[index] for row in rows) for index in range(feature_count)]
    scales = []
    for index, mean in enumerate(means):
        variance = fmean((row[index] - mean) ** 2 for row in rows)
        scales.append(math.sqrt(variance) if variance > 1e-12 else 1.0)
    standardized = [
        [(row[index] - means[index]) / scales[index] for index in range(feature_count)]
        for row in rows
    ]
    weights = [0.0] * feature_count
    intercept = math.log((sum(labels) + 0.5) / (len(labels) - sum(labels) + 0.5))
    for _ in range(epochs):
        probabilities = [
            _sigmoid(intercept + sum(weight * value for weight, value in zip(weights, row, strict=True)))
            for row in standardized
        ]
        errors = [probability - label for probability, label in zip(probabilities, labels, strict=True)]
        intercept -= learning_rate * fmean(errors)
        for index in range(feature_count):
            gradient = fmean(error * row[index] for error, row in zip(errors, standardized, strict=True))
            gradient += l2_penalty * weights[index]
            weights[index] -= learning_rate * gradient
    parameters = {
        "weights": weights,
        "intercept": intercept,
        "means": means,
        "scales": scales,
        "epochs": epochs,
        "learningRate": learning_rate,
        "l2Penalty": l2_penalty,
    }
    evidence = _training_evidence(dataset, rows)
    draft = _artifact(
        model_type="logistic_regression",
        feature_names=dataset.featureNames,
        parameters=parameters,
        metrics={},
        evidence=evidence,
    )
    probabilities = predict_probabilities(draft, rows)
    return _artifact(
        model_type=draft.modelType,
        feature_names=draft.featureNames,
        parameters=parameters,
        metrics=_classification_metrics(probabilities, labels),
        evidence=evidence,
    )


def _candidate_thresholds(values: list[float], maximum: int = 16) -> list[float]:
    unique = sorted(set(values))
    if len(unique) < 2:
        return []
    midpoints = [(left + right) / 2 for left, right in zip(unique, unique[1:])]
    if len(midpoints) <= maximum:
        return midpoints
    indexes = sorted({round(index * (len(midpoints) - 1) / (maximum - 1)) for index in range(maximum)})
    return [midpoints[index] for index in indexes]


def train_tree_boosting_challenger(
    dataset: TrainingDataset,
    *,
    repository: RegistryRepository,
    estimator_count: int = 20,
    learning_rate: float = 0.2,
) -> TrainedModelArtifact:
    rows = _validate_dataset(dataset, repository)
    labels = list(dataset.labels)
    if estimator_count <= 0 or learning_rate <= 0:
        raise ValueError("Tree boosting parameters must be positive")
    positive_rate = min(max(fmean(labels), 1e-6), 1 - 1e-6)
    base_logit = math.log(positive_rate / (1 - positive_rate))
    logits = [base_logit] * len(rows)
    stumps: list[dict[str, float | int]] = []
    for _ in range(estimator_count):
        probabilities = [_sigmoid(value) for value in logits]
        residuals = [label - probability for label, probability in zip(labels, probabilities, strict=True)]
        best = None
        for feature_index in range(len(dataset.featureNames)):
            values = [row[feature_index] for row in rows]
            for threshold in _candidate_thresholds(values):
                left_indexes = [index for index, value in enumerate(values) if value <= threshold]
                right_indexes = [index for index, value in enumerate(values) if value > threshold]
                if not left_indexes or not right_indexes:
                    continue
                left_index_set = set(left_indexes)
                left_value = fmean(residuals[index] for index in left_indexes)
                right_value = fmean(residuals[index] for index in right_indexes)
                loss = sum(
                    (residuals[index] - (left_value if index in left_index_set else right_value)) ** 2
                    for index in range(len(rows))
                )
                candidate = (loss, feature_index, threshold, left_value, right_value)
                if best is None or candidate < best:
                    best = candidate
        if best is None:
            break
        _, feature_index, threshold, left_value, right_value = best
        stump = {
            "featureIndex": feature_index,
            "threshold": threshold,
            "leftValue": left_value,
            "rightValue": right_value,
        }
        stumps.append(stump)
        for index, row in enumerate(rows):
            leaf = left_value if row[feature_index] <= threshold else right_value
            logits[index] += learning_rate * leaf
    parameters = {
        "baseLogit": base_logit,
        "learningRate": learning_rate,
        "estimatorCount": len(stumps),
        "stumps": stumps,
    }
    evidence = _training_evidence(dataset, rows)
    draft = _artifact(
        model_type="gradient_boosted_stumps",
        feature_names=dataset.featureNames,
        parameters=parameters,
        metrics={},
        evidence=evidence,
    )
    probabilities = predict_probabilities(draft, rows)
    return _artifact(
        model_type=draft.modelType,
        feature_names=draft.featureNames,
        parameters=parameters,
        metrics=_classification_metrics(probabilities, labels),
        evidence=evidence,
    )


def predict_probabilities(
    artifact: TrainedModelArtifact,
    features: Sequence[Sequence[float]],
) -> list[float]:
    rows = [list(map(float, row)) for row in features]
    if any(len(row) != len(artifact.featureNames) for row in rows):
        raise ValueError("Prediction rows must match model feature count")
    if artifact.modelType == "logistic_regression":
        weights = artifact.parameters["weights"]
        means = artifact.parameters["means"]
        scales = artifact.parameters["scales"]
        intercept = artifact.parameters["intercept"]
        return [
            _sigmoid(
                intercept
                + sum(
                    weights[index] * ((row[index] - means[index]) / scales[index])
                    for index in range(len(row))
                )
            )
            for row in rows
        ]
    if artifact.modelType == "gradient_boosted_stumps":
        learning_rate = artifact.parameters["learningRate"]
        probabilities: list[float] = []
        for row in rows:
            score = artifact.parameters["baseLogit"]
            for stump in artifact.parameters["stumps"]:
                feature_index = int(stump["featureIndex"])
                leaf = (
                    stump["leftValue"]
                    if row[feature_index] <= stump["threshold"]
                    else stump["rightValue"]
                )
                score += learning_rate * leaf
            probabilities.append(_sigmoid(score))
        return probabilities
    raise ValueError(f"Unsupported model type: {artifact.modelType}")
