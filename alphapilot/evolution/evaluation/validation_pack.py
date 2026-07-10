"""Build deterministic, leakage-resistant formal validation manifests."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.evaluation.purged_walk_forward import (
    build_purged_walk_forward,
)
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.types import DataSnapshotRecord
from alphapilot.evolution.workflow.types import StrategyDataContractRecord


@dataclass(frozen=True)
class FormalValidationPack:
    strategyDataContractId: str
    dataSnapshotId: str
    walkForwardManifestHash: str
    holdoutManifestHash: str
    lockedOosManifestHash: str
    regimeManifestHash: str
    costManifestHash: str
    holdoutSymbols: tuple[str, ...]
    trainingSymbols: tuple[str, ...]
    walkForwardFoldCount: int
    lockedStartIndex: int
    manifestPaths: tuple[str, ...]


def _snapshot_frames(
    snapshot: DataSnapshotRecord,
    *,
    canonical_root: Path,
    signal_timeframe: str,
) -> dict[str, pd.DataFrame]:
    frames: dict[str, pd.DataFrame] = {}
    for row in snapshot.manifest.get("files", []):
        path = canonical_root / str(row["path"])
        if "ohlcv" not in path.parts:
            continue
        frame = pd.read_parquet(path)
        if frame.empty or "timeframe" not in frame.columns:
            continue
        if str(frame["timeframe"].iloc[0]) != signal_timeframe:
            continue
        instrument = str(frame["instrument_id"].iloc[0])
        frames[instrument] = frame.sort_values("timestamp_ms").reset_index(drop=True)
    return frames


def _regime_manifest(
    frames: dict[str, pd.DataFrame], requested: list[str]
) -> dict[str, Any]:
    btc = frames.get("BTC-USDT-SWAP")
    if btc is None or btc.empty:
        raise ValueError("btc_regime_series_missing")
    close = pd.to_numeric(btc["close"], errors="coerce")
    returns = close.pct_change()
    ema = close.ewm(span=200, adjust=False).mean()
    volatility = returns.rolling(20, min_periods=5).std()
    high_vol = volatility.quantile(0.75)
    labels = pd.Series("range", index=btc.index, dtype="object")
    labels.loc[close > ema * 1.025] = "bull"
    labels.loc[close < ema * 0.975] = "bear"
    labels.loc[returns.rolling(3).sum() <= -0.08] = "crash"
    labels.loc[(volatility >= high_vol) & (labels == "range")] = "volatility_expansion"
    counts = {str(key): int(value) for key, value in labels.value_counts().items()}
    observed = sorted(counts)
    return {
        "schemaVersion": "regime_manifest_v1",
        "instrumentId": "BTC-USDT-SWAP",
        "method": "ema200_return3_volatility20_v1",
        "requestedRegimes": requested,
        "observedRegimes": observed,
        "missingRegimes": sorted(set(requested) - set(observed)),
        "counts": counts,
    }


def build_formal_validation_pack(
    contract: StrategyDataContractRecord,
    snapshot: DataSnapshotRecord,
    *,
    canonical_root: Path | str,
    manifest_root: Path | str,
) -> FormalValidationPack:
    canonical = Path(canonical_root).resolve()
    output_root = (
        Path(manifest_root).resolve()
        / contract.strategyDataContractId
        / snapshot.dataSnapshotId
    )
    frames = _snapshot_frames(
        snapshot,
        canonical_root=canonical,
        signal_timeframe=str(contract.contract["signalTimeframe"]),
    )
    symbols = sorted(frames)
    if len(symbols) < 2:
        raise ValueError("validation_pack_requires_two_symbols")
    holdout_count = max(1, math.ceil(len(symbols) * 0.2))
    holdout_symbols = tuple(symbols[-holdout_count:])
    training_symbols = tuple(symbols[:-holdout_count])
    timestamps = sorted(
        {
            int(value)
            for symbol in training_symbols
            for value in frames[symbol]["timestamp_ms"].tolist()
        }
    )
    if len(timestamps) < 240:
        raise ValueError(f"validation_pack_samples_insufficient:{len(timestamps)}")
    locked_count = max(30, int(len(timestamps) * 0.15))
    locked_start = len(timestamps) - locked_count
    development_count = locked_start
    max_holding = int(contract.contract.get("maxHoldingBars", 24))
    label_horizon = int(contract.contract.get("labelHorizonBars", max_holding))
    test_size = max(20, int(development_count * 0.10))
    min_train = max(80, int(development_count * 0.45))
    walk_forward = build_purged_walk_forward(
        sample_count=development_count,
        min_train_size=min_train,
        test_size=test_size,
        label_horizon=label_horizon,
        embargo_size=max_holding,
        max_holding_period=max_holding,
        min_folds=3,
    ).to_dict()
    holdout = {
        "schemaVersion": "unseen_symbol_holdout_v1",
        "strategyDataContractId": contract.strategyDataContractId,
        "trainingSymbols": list(training_symbols),
        "holdoutSymbols": list(holdout_symbols),
        "selection": "sorted_symbols_final_20_percent",
    }
    holdout_hash = stable_hash(holdout, prefix="holdout")
    locked = {
        "schemaVersion": "locked_oos_manifest_v1",
        "strategyDataContractId": contract.strategyDataContractId,
        "dataSnapshotId": snapshot.dataSnapshotId,
        "lockedStartIndex": locked_start,
        "lockedEndExclusive": len(timestamps),
        "lockedStartTimestampMs": timestamps[locked_start],
        "lockedEndTimestampMs": timestamps[-1],
        "evaluationPolicy": "evaluate_once_per_strategy_and_gate_profile",
    }
    locked_hash = stable_hash(locked, prefix="locked_oos")
    requested_regimes = list(
        (contract.contract.get("validationPolicy") or {}).get(
            "regimeCoverage", []
        )
    )
    regime = _regime_manifest(frames, requested_regimes)
    regime_hash = stable_hash(regime, prefix="regime")
    cost = {
        "schemaVersion": "formal_cost_manifest_v1",
        "strategyDataContractId": contract.strategyDataContractId,
        **dict(contract.contract.get("costPolicy") or {}),
        "targetR": float(contract.contract["targetR"]),
        "sameBarAmbiguity": (contract.contract.get("validationPolicy") or {}).get(
            "sameBarAmbiguity"
        ),
    }
    cost_hash = stable_hash(cost, prefix="cost")
    manifests = {
        "walk-forward.json": walk_forward,
        "holdout.json": {**holdout, "manifestHash": holdout_hash},
        "locked-oos.json": {**locked, "manifestHash": locked_hash},
        "regime.json": {**regime, "manifestHash": regime_hash},
        "cost.json": {**cost, "manifestHash": cost_hash},
    }
    output_root.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for name, payload in manifests.items():
        path = output_root / name
        write_json_atomic(path, payload)
        paths.append(str(path))
    return FormalValidationPack(
        strategyDataContractId=contract.strategyDataContractId,
        dataSnapshotId=snapshot.dataSnapshotId,
        walkForwardManifestHash=str(walk_forward["manifestHash"]),
        holdoutManifestHash=holdout_hash,
        lockedOosManifestHash=locked_hash,
        regimeManifestHash=regime_hash,
        costManifestHash=cost_hash,
        holdoutSymbols=holdout_symbols,
        trainingSymbols=training_symbols,
        walkForwardFoldCount=len(walk_forward["folds"]),
        lockedStartIndex=locked_start,
        manifestPaths=tuple(sorted(paths)),
    )
