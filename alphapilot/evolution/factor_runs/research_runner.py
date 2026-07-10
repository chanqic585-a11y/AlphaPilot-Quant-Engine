"""V13.17 purged walk-forward research runner over registered FactorRuns."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from statistics import fmean
from typing import Any, Callable

import pandas as pd

from alphapilot.evolution.evaluation.cost_stress import evaluate_cost_stress
from alphapilot.evolution.evaluation.multiple_testing import benjamini_hochberg
from alphapilot.evolution.evaluation.purged_walk_forward import (
    WalkForwardManifest,
    build_purged_walk_forward,
)
from alphapilot.evolution.evaluation.robustness import evaluate_group_stability
from alphapilot.evolution.models.model_registry import register_model_artifact
from alphapilot.evolution.models.trainer import (
    TrainedModelArtifact,
    TrainingDataset,
    predict_probabilities,
    train_logistic_baseline,
    train_tree_boosting_challenger,
)
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import ExperimentRecord
from alphapilot.evolution.strategies.candidate_builder import (
    StrategyCandidateDraft,
    build_strategy_candidate,
)

from .labels import DirectionalLabelConfig
from .materializer import MaterializedFactorMatrix


MODEL_TRAINERS: dict[str, Callable[..., TrainedModelArtifact]] = {
    "logistic_regression": train_logistic_baseline,
    "gradient_boosted_stumps": train_tree_boosting_challenger,
}


@dataclass(frozen=True)
class ResearchEvaluationConfig:
    lockedTestFraction: float = 0.20
    minimumTrainFraction: float = 0.45
    testFraction: float = 0.12
    probabilityThreshold: float = 0.55
    minimumOosTrades: int = 30
    minimumLockedTrades: int = 10
    minimumProfitFactor: float = 1.10
    minimumLockedProfitFactor: float = 1.05
    minimumPositiveGroupFraction: float = 0.67

    def validate(self) -> None:
        if not 0.1 <= self.lockedTestFraction <= 0.4:
            raise ValueError("lockedTestFraction must be between 0.1 and 0.4")
        if not 0.3 <= self.minimumTrainFraction < 0.8:
            raise ValueError("minimumTrainFraction must be between 0.3 and 0.8")
        if not 0.05 <= self.testFraction <= 0.25:
            raise ValueError("testFraction must be between 0.05 and 0.25")
        if not 0.5 <= self.probabilityThreshold < 1:
            raise ValueError("probabilityThreshold must be in [0.5, 1)")


@dataclass
class _DirectionEvaluation:
    direction: str
    payload: dict[str, Any]
    selectedArtifact: TrainedModelArtifact
    pValue: float


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _training_view_manifest(
    *,
    sample_count: int,
    source_manifest_hash: str,
    view_id: str,
) -> WalkForwardManifest:
    config = {
        "sampleCount": sample_count,
        "sourceWalkForwardManifestHash": source_manifest_hash,
        "trainingViewId": view_id,
    }
    return WalkForwardManifest(
        mode="training_view",
        config=config,
        folds=(),
        manifestHash=stable_hash(config, prefix="walk_forward"),
    )


def _train(
    model_type: str,
    frame: pd.DataFrame,
    *,
    feature_columns: tuple[str, ...],
    label_column: str,
    factor_run_ids: tuple[str, ...],
    source_manifest_hash: str,
    view_id: str,
    repository: RegistryRepository,
) -> TrainedModelArtifact:
    manifest = _training_view_manifest(
        sample_count=len(frame),
        source_manifest_hash=source_manifest_hash,
        view_id=view_id,
    )
    dataset = TrainingDataset(
        featureNames=feature_columns,
        features=frame[list(feature_columns)].to_numpy(dtype="float64").tolist(),
        labels=frame[label_column].astype("int64").tolist(),
        factorRunIds=factor_run_ids,
        foldManifest=manifest,
    )
    if model_type == "logistic_regression":
        return train_logistic_baseline(
            dataset,
            repository=repository,
            epochs=250,
            learning_rate=0.08,
            l2_penalty=0.002,
        )
    if model_type == "gradient_boosted_stumps":
        return train_tree_boosting_challenger(
            dataset,
            repository=repository,
            estimator_count=12,
            learning_rate=0.18,
        )
    raise ValueError(f"Unsupported model type: {model_type}")


def _classification_metrics(probabilities: list[float], labels: list[int]) -> dict[str, float]:
    if not probabilities or len(probabilities) != len(labels):
        raise ValueError("Aligned classification values are required")
    clipped = [min(max(value, 1e-12), 1 - 1e-12) for value in probabilities]
    return {
        "sampleCount": float(len(labels)),
        "positiveRate": fmean(labels),
        "accuracy": sum(int(value >= 0.5) == label for value, label in zip(probabilities, labels, strict=True))
        / len(labels),
        "brierScore": fmean(
            (value - label) ** 2 for value, label in zip(probabilities, labels, strict=True)
        ),
        "logLoss": -fmean(
            label * math.log(value) + (1 - label) * math.log(1 - value)
            for value, label in zip(clipped, labels, strict=True)
        ),
    }


def _profit_factor(values: list[float]) -> float | None:
    gains = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    return gains / losses if losses > 0 else None


def _maximum_drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def _strategy_metrics(
    frame: pd.DataFrame,
    probabilities: list[float],
    *,
    direction: str,
    threshold: float,
    fee_rate: float,
    slippage_rate: float,
) -> dict[str, Any]:
    if len(frame) != len(probabilities):
        raise ValueError("Strategy probabilities must align with rows")
    selected = frame.copy()
    selected["probability"] = probabilities
    selected = selected[selected["probability"] >= threshold].copy()
    net_column = f"label_{direction}_net_r"
    gross_return_column = f"label_{direction}_gross_return"
    delayed_return_column = f"label_{direction}_delayed_gross_return"
    target_column = f"label_{direction}_target_hit"
    net_values = selected[net_column].astype("float64").tolist()
    profit_factor = _profit_factor(net_values)
    trade_count = len(selected)
    rows = [
        {
            "instrument": str(row.instrument_id),
            "month": pd.Timestamp(row.date).strftime("%Y-%m"),
            "netR": float(getattr(row, net_column)),
        }
        for row in selected.itertuples(index=False)
    ]
    stability: dict[str, Any] = {}
    if rows:
        for name, result in evaluate_group_stability(
            rows,
            dimensions=["instrument", "month"],
            metric="netR",
            minimum_positive_fraction=0.67,
            minimum_groups=2,
        ).items():
            stability[name] = asdict(result)
    if trade_count:
        cost_stress = asdict(
            evaluate_cost_stress(
                gross_returns=selected[gross_return_column].astype("float64").tolist(),
                delayed_returns=selected[delayed_return_column].astype("float64").tolist(),
                base_fee_rate=fee_rate,
                base_slippage_rate=slippage_rate,
            )
        )
    else:
        cost_stress = {
            "allRequiredScenariosEvaluated": False,
            "blockedReason": "no_trades_at_fixed_threshold",
        }
    return {
        "probabilityThreshold": threshold,
        "tradeCount": trade_count,
        "winCount": int(selected[target_column].sum()) if trade_count else 0,
        "winRate": float(selected[target_column].mean()) if trade_count else None,
        "totalNetR": sum(net_values),
        "averageNetR": fmean(net_values) if net_values else None,
        "profitFactor": profit_factor,
        "maximumDrawdownR": _maximum_drawdown(net_values),
        "sameBarAmbiguousCount": int(
            selected[f"label_{direction}_same_bar_ambiguous"].sum()
        )
        if trade_count
        else 0,
        "stability": stability,
        "costStress": cost_stress,
    }


def _binomial_tail(successes: int, trials: int, null_probability: float = 1 / 3) -> float:
    if trials <= 0:
        return 1.0
    return min(
        1.0,
        sum(
            math.comb(trials, count)
            * (null_probability**count)
            * ((1 - null_probability) ** (trials - count))
            for count in range(successes, trials + 1)
        ),
    )


def _evaluate_direction(
    panel: pd.DataFrame,
    *,
    direction: str,
    feature_columns: tuple[str, ...],
    factor_run_ids: tuple[str, ...],
    walk_forward: WalkForwardManifest,
    development_times: list[int],
    locked_times: list[int],
    repository: RegistryRepository,
    config: ResearchEvaluationConfig,
    label_config: DirectionalLabelConfig,
) -> _DirectionEvaluation:
    label_column = f"label_{direction}_target_hit"
    model_results: dict[str, Any] = {}
    model_predictions: dict[str, tuple[pd.DataFrame, list[float]]] = {}
    for model_type in MODEL_TRAINERS:
        prediction_frames: list[pd.DataFrame] = []
        probabilities: list[float] = []
        fold_rows: list[dict[str, Any]] = []
        for fold in walk_forward.folds:
            train_times = set(development_times[fold.trainStart : fold.trainEndExclusive])
            test_times = set(development_times[fold.testStart : fold.testEndExclusive])
            train = panel[panel["timestamp_ms"].isin(train_times)]
            test = panel[panel["timestamp_ms"].isin(test_times)]
            artifact = _train(
                model_type,
                train,
                feature_columns=feature_columns,
                label_column=label_column,
                factor_run_ids=factor_run_ids,
                source_manifest_hash=walk_forward.manifestHash,
                view_id=f"{direction}:{model_type}:{fold.foldId}",
                repository=repository,
            )
            fold_probabilities = predict_probabilities(
                artifact,
                test[list(feature_columns)].to_numpy(dtype="float64").tolist(),
            )
            prediction_frames.append(test)
            probabilities.extend(fold_probabilities)
            fold_rows.append(
                {
                    "foldId": fold.foldId,
                    "trainRows": len(train),
                    "testRows": len(test),
                    "classification": _classification_metrics(
                        fold_probabilities, test[label_column].astype("int64").tolist()
                    ),
                }
            )
        oos_frame = pd.concat(prediction_frames, ignore_index=True)
        classification = _classification_metrics(
            probabilities,
            oos_frame[label_column].astype("int64").tolist(),
        )
        strategy = _strategy_metrics(
            oos_frame,
            probabilities,
            direction=direction,
            threshold=config.probabilityThreshold,
            fee_rate=label_config.feeRate,
            slippage_rate=label_config.slippageRate,
        )
        model_results[model_type] = {
            "classification": classification,
            "strategy": strategy,
            "folds": fold_rows,
        }
        model_predictions[model_type] = (oos_frame, probabilities)

    selected_model = min(
        model_results,
        key=lambda name: (model_results[name]["classification"]["brierScore"], name),
    )
    development = panel[panel["timestamp_ms"].isin(set(development_times))]
    selected_artifact = _train(
        selected_model,
        development,
        feature_columns=feature_columns,
        label_column=label_column,
        factor_run_ids=factor_run_ids,
        source_manifest_hash=walk_forward.manifestHash,
        view_id=f"{direction}:{selected_model}:development_locked_parameters",
        repository=repository,
    )
    locked = panel[panel["timestamp_ms"].isin(set(locked_times))]
    locked_probabilities = predict_probabilities(
        selected_artifact,
        locked[list(feature_columns)].to_numpy(dtype="float64").tolist(),
    )
    locked_classification = _classification_metrics(
        locked_probabilities,
        locked[label_column].astype("int64").tolist(),
    )
    locked_strategy = _strategy_metrics(
        locked,
        locked_probabilities,
        direction=direction,
        threshold=config.probabilityThreshold,
        fee_rate=label_config.feeRate,
        slippage_rate=label_config.slippageRate,
    )
    selected_oos = model_results[selected_model]["strategy"]
    p_value = _binomial_tail(selected_oos["winCount"], selected_oos["tradeCount"])
    payload = {
        "direction": direction,
        "selectedModelType": selected_model,
        "selectionRule": "lowest_development_oos_brier_score_then_model_name",
        "parameterSearchPerformed": False,
        "modelResults": model_results,
        "lockedTest": {
            "accessedAfterModelSelection": True,
            "rowCount": len(locked),
            "classification": locked_classification,
            "strategy": locked_strategy,
        },
        "winRateNullPValue": p_value,
    }
    return _DirectionEvaluation(direction, payload, selected_artifact, p_value)


def _passes_performance_gate(
    evaluation: _DirectionEvaluation,
    *,
    config: ResearchEvaluationConfig,
    fdr_significant: bool,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    selected = evaluation.payload["modelResults"][evaluation.payload["selectedModelType"]][
        "strategy"
    ]
    locked = evaluation.payload["lockedTest"]["strategy"]
    if selected["tradeCount"] < config.minimumOosTrades:
        reasons.append("insufficient_oos_trades")
    if selected["averageNetR"] is None or selected["averageNetR"] <= 0:
        reasons.append("non_positive_oos_expectancy")
    if selected["profitFactor"] is None or selected["profitFactor"] < config.minimumProfitFactor:
        reasons.append("oos_profit_factor_below_threshold")
    cost = selected["costStress"]
    if not cost.get("allRequiredScenariosEvaluated") or not cost.get("cost2xPositive"):
        reasons.append("cost_stress_failed")
    for dimension in ("instrument", "month"):
        result = selected["stability"].get(dimension)
        if not result or result["positiveFraction"] < config.minimumPositiveGroupFraction:
            reasons.append(f"{dimension}_stability_failed")
    if locked["tradeCount"] < config.minimumLockedTrades:
        reasons.append("insufficient_locked_trades")
    if locked["averageNetR"] is None or locked["averageNetR"] <= 0:
        reasons.append("non_positive_locked_expectancy")
    if locked["profitFactor"] is None or locked["profitFactor"] < config.minimumLockedProfitFactor:
        reasons.append("locked_profit_factor_below_threshold")
    if not fdr_significant:
        reasons.append("multiple_testing_not_significant")
    return not reasons, reasons


def run_factor_research(
    *,
    matrix: MaterializedFactorMatrix,
    repository: RegistryRepository,
    label_config: DirectionalLabelConfig | None = None,
    evaluation_config: ResearchEvaluationConfig | None = None,
    code_commit: str | None = None,
) -> dict[str, Any]:
    labels = label_config or DirectionalLabelConfig()
    settings = evaluation_config or ResearchEvaluationConfig()
    labels.validate()
    settings.validate()
    panel = pd.read_parquet(matrix.path)
    unique_times = sorted(int(value) for value in panel["timestamp_ms"].unique())
    if len(unique_times) < 200:
        raise ValueError("At least 200 complete timestamps are required for V13.17 research")
    locked_count = max(40, int(len(unique_times) * settings.lockedTestFraction))
    development_times = unique_times[:-locked_count]
    locked_times = unique_times[-locked_count:]
    minimum_train = max(80, int(len(development_times) * settings.minimumTrainFraction))
    test_size = max(30, int(len(development_times) * settings.testFraction))
    walk_forward = build_purged_walk_forward(
        sample_count=len(development_times),
        min_train_size=minimum_train,
        test_size=test_size,
        label_horizon=labels.maxHoldingBars,
        embargo_size=labels.maxHoldingBars,
        max_holding_period=labels.maxHoldingBars,
        step_size=test_size,
        min_folds=3,
    )
    evaluations = [
        _evaluate_direction(
            panel,
            direction=direction,
            feature_columns=matrix.featureColumns,
            factor_run_ids=matrix.factorRunIds,
            walk_forward=walk_forward,
            development_times=development_times,
            locked_times=locked_times,
            repository=repository,
            config=settings,
            label_config=labels,
        )
        for direction in ("long", "short")
    ]
    fdr = benjamini_hochberg(
        {evaluation.direction: evaluation.pValue for evaluation in evaluations}, q=0.10
    )
    significant = {item.itemId: item.significant for item in fdr.decisions}
    snapshot = repository.get_data_snapshot(matrix.dataSnapshotId)
    if snapshot is None:
        raise ValueError(f"DataSnapshot is not registered: {matrix.dataSnapshotId}")
    expression_ids = [
        str(repository.get_factor_definition(identifier).definition["expressionId"])
        for identifier in matrix.factorDefinitionIds
    ]
    experiment_rows: list[dict[str, Any]] = []
    model_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for evaluation in evaluations:
        performance_passed, performance_reasons = _passes_performance_gate(
            evaluation,
            config=settings,
            fdr_significant=significant[evaluation.direction],
        )
        formal_gate_passed = performance_passed and matrix.formalPromotionEligible
        blockers = list(performance_reasons)
        if not matrix.formalPromotionEligible:
            blockers.append("data_snapshot_provenance_not_formal")
        payload = {
            "schemaVersion": "v13_17_directional_research_experiment_v1",
            "dataSnapshotId": matrix.dataSnapshotId,
            "factorRunIds": list(matrix.factorRunIds),
            "factorMatrixSha256": matrix.sha256,
            "walkForwardManifest": walk_forward.to_dict(),
            "evaluation": evaluation.payload,
            "fdr": asdict(fdr),
            "performanceGatePassed": performance_passed,
            "formalGatePassed": formal_gate_passed,
            "blockers": blockers,
            "rewardRiskRatio": labels.takeProfitR / labels.stopLossR,
            "researchOnly": True,
            "createsOrders": False,
        }
        experiment_id = stable_hash(
            {
                "dataSnapshotId": matrix.dataSnapshotId,
                "direction": evaluation.direction,
                "factorMatrixSha256": matrix.sha256,
                "walkForwardManifestHash": walk_forward.manifestHash,
                "selectedModelHash": evaluation.selectedArtifact.modelHash,
            },
            prefix="experiment",
        )
        experiment = repository.create_experiment(
            ExperimentRecord(
                experimentId=experiment_id,
                experimentType="purged_walk_forward_directional_2r",
                status="research_validated" if formal_gate_passed else "completed",
                dataSnapshotId=matrix.dataSnapshotId,
                splitDefinition={
                    "walkForward": walk_forward.to_dict(),
                    "lockedTestTimestampCount": len(locked_times),
                    "lockedTestStartMs": locked_times[0],
                    "lockedTestEndMs": locked_times[-1],
                    "lockedTestAccessPolicy": "access_after_fixed_model_selection",
                },
                costModel={
                    "feeRate": labels.feeRate,
                    "slippageRate": labels.slippageRate,
                    "stressMultipliers": [1, 2, 3],
                    "oneBarDelay": True,
                },
                parameters={
                    "direction": evaluation.direction,
                    "probabilityThreshold": settings.probabilityThreshold,
                    "stopLossR": labels.stopLossR,
                    "takeProfitR": labels.takeProfitR,
                    "maxHoldingBars": labels.maxHoldingBars,
                },
                codeCommit=code_commit,
                payload=payload,
                contentHash=stable_hash(payload),
            )
        )
        model = register_model_artifact(
            repository=repository,
            experiment_id=experiment.experimentId,
            artifact=evaluation.selectedArtifact,
            status="shadow_candidate",
        )
        experiment_rows.append(
            {
                "experimentId": experiment.experimentId,
                "direction": evaluation.direction,
                "status": experiment.status,
                "performanceGatePassed": performance_passed,
                "formalGatePassed": formal_gate_passed,
                "blockers": blockers,
                "evaluation": evaluation.payload,
            }
        )
        model_rows.append(
            {
                "modelId": model.modelId,
                "experimentId": experiment.experimentId,
                "algorithm": model.algorithm,
                "status": model.status,
                "modelHash": evaluation.selectedArtifact.modelHash,
            }
        )
        if formal_gate_passed:
            candidate = build_strategy_candidate(
                StrategyCandidateDraft(
                    name=f"V13.17 {evaluation.direction.title()} 2R Research Candidate",
                    familyKey=f"v13_17_directional_2r_{evaluation.direction}",
                    direction=evaluation.direction,
                    marketDefinition={
                        "exchange": snapshot.exchange,
                        "marketType": snapshot.marketType,
                        "timeframe": matrix.timeframe,
                        "universePolicy": "registered_snapshot_universe",
                    },
                    entryRules=expression_ids,
                    exitRules={
                        "stopLossR": labels.stopLossR,
                        "takeProfitR": labels.takeProfitR,
                        "maxHoldingBars": labels.maxHoldingBars,
                    },
                    riskRules={
                        "riskPerTradePct": 0.25,
                        "maxLeverage": 1,
                        "maxConcurrentPositions": 3,
                    },
                    evidence={
                        "dataSnapshotId": matrix.dataSnapshotId,
                        "factorRunIds": list(matrix.factorRunIds),
                        "experimentIds": [experiment.experimentId],
                        "walkForwardManifestHash": walk_forward.manifestHash,
                        "formalGateStatus": "passed",
                    },
                ),
                repository=repository,
            )
            candidate_rows.append(
                {
                    "strategyCandidateId": candidate.strategyCandidateId,
                    "name": candidate.name,
                    "status": candidate.status,
                }
            )
    return {
        "reportId": "v13_17_factor_run_backtest_report",
        "version": "V13.17.0",
        "status": (
            "completed_with_provenance_blocker"
            if not matrix.formalPromotionEligible
            else "completed"
        ),
        "generatedAt": _utc_now(),
        "dataSnapshotId": matrix.dataSnapshotId,
        "matrix": matrix.to_dict(),
        "labelConfig": asdict(labels),
        "evaluationConfig": asdict(settings),
        "walkForwardManifest": walk_forward.to_dict(),
        "lockedTest": {
            "timestampCount": len(locked_times),
            "start": pd.Timestamp(locked_times[0], unit="ms", tz="UTC").isoformat(),
            "end": pd.Timestamp(locked_times[-1], unit="ms", tz="UTC").isoformat(),
            "accessedAfterModelSelection": True,
        },
        "multipleTesting": asdict(fdr),
        "experiments": experiment_rows,
        "models": model_rows,
        "strategyCandidates": candidate_rows,
        "formalPromotionEligible": bool(candidate_rows),
        "blockers": (
            []
            if matrix.formalPromotionEligible
            else ["local_base_source_provenance_not_verified"]
        ),
        "safetyBoundary": {
            "researchOnly": True,
            "apiKeyUsed": False,
            "accountRead": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "orderCreated": False,
            "demoReleaseCreated": False,
            "liveTradingEnabled": False,
        },
    }
