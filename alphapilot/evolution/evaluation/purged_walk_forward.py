"""Deterministic expanding or rolling walk-forward fold manifests."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


@dataclass(frozen=True)
class WalkForwardFold:
    foldId: str
    trainStart: int
    trainEndExclusive: int
    purgeStart: int
    purgeEndExclusive: int
    embargoStart: int
    embargoEndExclusive: int
    testStart: int
    testEndExclusive: int

    @property
    def trainSize(self) -> int:
        return self.trainEndExclusive - self.trainStart

    @property
    def testSize(self) -> int:
        return self.testEndExclusive - self.testStart

    def to_dict(self) -> dict[str, Any]:
        return {
            "foldId": self.foldId,
            "trainStart": self.trainStart,
            "trainEndExclusive": self.trainEndExclusive,
            "trainSize": self.trainSize,
            "purgeStart": self.purgeStart,
            "purgeEndExclusive": self.purgeEndExclusive,
            "embargoStart": self.embargoStart,
            "embargoEndExclusive": self.embargoEndExclusive,
            "testStart": self.testStart,
            "testEndExclusive": self.testEndExclusive,
            "testSize": self.testSize,
        }


@dataclass(frozen=True)
class WalkForwardManifest:
    mode: str
    config: dict[str, Any]
    folds: tuple[WalkForwardFold, ...]
    manifestHash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "config": self.config,
            "folds": [fold.to_dict() for fold in self.folds],
            "manifestHash": self.manifestHash,
        }


def build_purged_walk_forward(
    *,
    sample_count: int,
    min_train_size: int,
    test_size: int,
    label_horizon: int,
    embargo_size: int,
    max_holding_period: int,
    step_size: int | None = None,
    mode: str = "expanding",
    train_window: int | None = None,
    min_folds: int = 3,
) -> WalkForwardManifest:
    if mode not in {"expanding", "rolling"}:
        raise ValueError("mode must be expanding or rolling")
    positive_values = {
        "sample_count": sample_count,
        "min_train_size": min_train_size,
        "test_size": test_size,
        "label_horizon": label_horizon,
        "max_holding_period": max_holding_period,
        "min_folds": min_folds,
    }
    for name, value in positive_values.items():
        if value <= 0:
            raise ValueError(f"{name} must be positive")
    if embargo_size < max_holding_period:
        raise ValueError("embargo_size must cover max_holding_period")
    if mode == "rolling" and (train_window is None or train_window < min_train_size):
        raise ValueError("rolling mode requires train_window >= min_train_size")
    step = step_size if step_size is not None else test_size
    if step <= 0:
        raise ValueError("step_size must be positive")

    gap = label_horizon + embargo_size
    test_start = min_train_size + gap
    folds: list[WalkForwardFold] = []
    while test_start + test_size <= sample_count:
        train_end = test_start - gap
        train_start = 0 if mode == "expanding" else max(0, train_end - int(train_window or 0))
        if train_end - train_start < min_train_size:
            test_start += step
            continue
        fold_number = len(folds) + 1
        folds.append(
            WalkForwardFold(
                foldId=f"fold_{fold_number:03d}",
                trainStart=train_start,
                trainEndExclusive=train_end,
                purgeStart=train_end,
                purgeEndExclusive=train_end + label_horizon,
                embargoStart=train_end + label_horizon,
                embargoEndExclusive=test_start,
                testStart=test_start,
                testEndExclusive=test_start + test_size,
            )
        )
        test_start += step

    if len(folds) < min_folds:
        raise ValueError(f"Only {len(folds)} complete folds are available; {min_folds} required")
    config = {
        "sampleCount": sample_count,
        "minTrainSize": min_train_size,
        "trainWindow": train_window,
        "testSize": test_size,
        "stepSize": step,
        "labelHorizon": label_horizon,
        "embargoSize": embargo_size,
        "maxHoldingPeriod": max_holding_period,
        "minFolds": min_folds,
    }
    core = {"mode": mode, "config": config, "folds": [fold.to_dict() for fold in folds]}
    return WalkForwardManifest(
        mode=mode,
        config=config,
        folds=tuple(folds),
        manifestHash=stable_hash(core, prefix="walk_forward"),
    )
