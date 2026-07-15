"""Synthetic evaluator controls. These records are never eligible factors."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .factor_evaluation import evaluate_factor_trial


def _passes(result: dict[str, object]) -> bool:
    return bool(
        result["baseCostSpread"] > 0
        and result["stress1_5xSpread"] > 0
        and result["positiveFoldCount"] >= 4
        and result["pValue"] <= 0.05
    )


def run_evaluator_controls(*, seed: int) -> dict[str, object]:
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2021-01-01", periods=500, freq="D", tz="UTC")
    columns = [f"asset_{index}" for index in range(12)]
    latent = pd.DataFrame(rng.normal(size=(500, 12)), index=dates, columns=columns)
    forward = latent * 0.015 + pd.DataFrame(rng.normal(scale=0.003, size=(500, 12)), index=dates, columns=columns)
    positive = evaluate_factor_trial(
        trial_id="synthetic_positive_control",
        factor=latent,
        forward_returns=forward,
        direction=1,
        base_cost_bps=5,
        folds=5,
        embargo_rows=2,
    )
    negatives: list[dict[str, object]] = []
    for control_id in ("random", "time_shuffled", "random_direction"):
        if control_id == "random":
            factor = pd.DataFrame(rng.normal(size=latent.shape), index=dates, columns=columns)
        elif control_id == "time_shuffled":
            factor = latent.iloc[rng.permutation(len(latent))].set_axis(dates)
        else:
            signs = pd.Series(rng.choice([-1, 1], size=len(latent)), index=dates)
            factor = latent.mul(signs, axis=0)
        result = evaluate_factor_trial(
            trial_id=f"synthetic_negative_{control_id}",
            factor=factor,
            forward_returns=forward,
            direction=1,
            base_cost_bps=5,
            folds=5,
            embargo_rows=2,
        )
        negatives.append({"controlId": control_id, "passed": _passes(result), "metrics": result})
    return {
        "schemaVersion": "factor_evaluator_controls_v1",
        "positiveControl": {"passed": _passes(positive), "metrics": positive},
        "negativeControls": negatives,
        "controlsEligibleForShortlist": False,
    }
