"""Snapshot-bound fixed-2R formal strategy backtest adapter."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.derivatives.feature_panel import (
    build_derivatives_feature_panel_from_frames,
)
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.evolution.registry.types import DataSnapshotRecord
from alphapilot.evolution.workflow.backtest import BacktestAdapterResult
from alphapilot.evolution.workflow.types import (
    EvaluationBindingRecord,
    StrategyVersionRecord,
)
from alphapilot.reports.generate_v13_5_23_alpha191_crypto_subset_replay_report import (
    build_alpha191_observer_signals,
)

from .fixed_r_path import (
    FixedRPathConfig,
    PreparedFixedRExecutionPath,
    evaluate_prepared_fixed_r_path,
    prepare_fixed_r_execution_path,
)
from .short_cycle_signals import build_short_cycle_formal_signals


_TIMEFRAME_MINUTES = {"5m": 5, "15m": 15, "1h": 60, "4h": 240, "1d": 1440}


def _inside(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _load_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"formal_manifest_missing:{path.name}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"formal_manifest_invalid:{path.name}")
    return value


def _load_manifests(
    directory: Path,
    binding: EvaluationBindingRecord,
) -> dict[str, dict[str, Any]]:
    payloads = {
        "walk_forward": _load_json(directory / "walk-forward.json"),
        "holdout": _load_json(directory / "holdout.json"),
        "locked": _load_json(directory / "locked-oos.json"),
        "regime": _load_json(directory / "regime.json"),
        "cost": _load_json(directory / "cost.json"),
    }
    expected = {
        "walk_forward": binding.walkForwardManifestHash,
        "holdout": binding.holdoutManifestHash,
        "locked": binding.lockedOosManifestHash,
        "regime": str(binding.evidence.get("regimeManifestHash") or ""),
        "cost": str(binding.evidence.get("costManifestHash") or ""),
    }
    for key, payload in payloads.items():
        if not expected[key] or payload.get("manifestHash") != expected[key]:
            raise ValueError(f"manifest_hash_mismatch:{key.replace('_', '-')}")
    return payloads


def _snapshot_frames(
    snapshot: DataSnapshotRecord,
    canonical_root: Path,
) -> tuple[
    dict[str, dict[str, pd.DataFrame]],
    dict[str, pd.DataFrame],
    list[dict[str, str]],
]:
    ohlcv: dict[str, dict[str, pd.DataFrame]] = {}
    funding: dict[str, pd.DataFrame] = {}
    hashes: list[dict[str, str]] = []
    for item in snapshot.manifest.get("files", []):
        relative = str(item.get("path") or "")
        path = (canonical_root / relative).resolve()
        if not _inside(path, canonical_root) or not path.is_file():
            raise ValueError(f"snapshot_file_invalid:{relative}")
        actual_hash = sha256_file(path)
        if actual_hash != item.get("sha256"):
            raise ValueError(f"snapshot_file_hash_mismatch:{relative}")
        hashes.append({"path": relative, "sha256": actual_hash})
        frame = pd.read_parquet(path)
        if frame.empty:
            continue
        if "ohlcv" in path.parts:
            instrument = str(frame["instrument_id"].iloc[0])
            timeframe = str(frame["timeframe"].iloc[0])
            ohlcv.setdefault(timeframe, {})[instrument] = frame
        elif "funding" in path.parts and "instrument_id" in frame.columns:
            instrument = str(frame["instrument_id"].iloc[0])
            funding[instrument] = frame
    return ohlcv, funding, hashes


def _pair_to_instrument(pair: str) -> str:
    if pair.endswith("/USDT:USDT"):
        return f"{pair.removesuffix('/USDT:USDT')}-USDT-SWAP"
    return pair.replace("/", "-")


def _regime_lookup(signal_frames: dict[str, pd.DataFrame]) -> pd.Series:
    btc = signal_frames.get("BTC-USDT-SWAP")
    if btc is None or btc.empty:
        return pd.Series(dtype="object")
    ordered = btc.sort_values("timestamp_ms")
    close = pd.to_numeric(ordered["close"], errors="coerce")
    returns = close.pct_change()
    ema = close.ewm(span=200, adjust=False).mean()
    volatility = returns.rolling(20, min_periods=5).std()
    labels = pd.Series("range", index=ordered.index, dtype="object")
    labels.loc[close > ema * 1.025] = "bull"
    labels.loc[close < ema * 0.975] = "bear"
    labels.loc[returns.rolling(3).sum() <= -0.08] = "crash"
    high_vol = volatility.quantile(0.75)
    labels.loc[(volatility >= high_vol) & (labels == "range")] = (
        "volatility_expansion"
    )
    return pd.Series(
        labels.to_numpy(),
        index=pd.to_numeric(ordered["timestamp_ms"]).astype("int64"),
    )


def _regime_at(lookup: pd.Series, timestamp: int) -> str:
    if lookup.empty:
        return "unknown"
    position = int(lookup.index.searchsorted(timestamp, side="right")) - 1
    return str(lookup.iloc[position]) if position >= 0 else "unknown"


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    net = [float(row["netR"]) for row in rows]
    gross = [float(row["grossR"]) for row in rows]
    positives = sum(value for value in net if value > 0)
    negatives = abs(sum(value for value in net if value < 0))
    profit_factor = positives / negatives if negatives > 0 else (999.0 if positives else 0.0)
    cumulative = 0.0
    peak = 0.0
    maximum_drawdown = 0.0
    for value in net:
        cumulative += value
        peak = max(peak, cumulative)
        maximum_drawdown = max(maximum_drawdown, peak - cumulative)
    return {
        "tradeCount": len(rows),
        "profitFactor": round(profit_factor, 8),
        "averageNetR": round(sum(net) / len(net), 8) if net else 0.0,
        "averageGrossR": round(sum(gross) / len(gross), 8) if gross else 0.0,
        "maximumDrawdownR": round(maximum_drawdown, 8),
        "winRate": round(sum(value > 0 for value in net) / len(net), 8)
        if net
        else 0.0,
        "ambiguousPathCount": sum(bool(row["ambiguousPath"]) for row in rows),
        "partialTargetCount": sum(
            float(row.get("partialExitFraction") or 0) > 0 for row in rows
        ),
    }


def _stress_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    values = [float(row["netR"]) for row in rows]
    return {
        "tradeCount": len(values),
        "averageNetR": round(sum(values) / len(values), 8) if values else 0.0,
    }


def _group_metrics(
    rows: list[dict[str, Any]], key: str, required: tuple[str, ...] = ()
) -> dict[str, dict[str, Any]]:
    values = {str(row[key]) for row in rows}
    values.update(required)
    return {
        value: _summary([row for row in rows if str(row[key]) == value])
        for value in sorted(values)
    }


def _split_for_signal(
    *,
    instrument: str,
    timestamp: int,
    signal_index: int,
    manifests: dict[str, dict[str, Any]],
) -> tuple[str, int | None]:
    if instrument in set(manifests["holdout"].get("holdoutSymbols") or []):
        return "holdout", None
    if timestamp >= int(manifests["locked"].get("lockedStartTimestampMs") or 0):
        return "locked_oos", None
    for fold in manifests["walk_forward"].get("folds") or []:
        if int(fold["testStart"]) <= signal_index < int(
            fold["testEndExclusive"]
        ):
            return "walk_forward", int(fold.get("fold") or 0)
    return "development", None


def _execution_horizon(
    *,
    signal_timeframe: str,
    execution_timeframe: str,
    signal_bars: int,
) -> int:
    signal_minutes = _TIMEFRAME_MINUTES.get(signal_timeframe)
    execution_minutes = _TIMEFRAME_MINUTES.get(execution_timeframe)
    if signal_minutes is None or execution_minutes is None or signal_bars < 1:
        raise ValueError("short_cycle_execution_horizon_invalid")
    total_minutes = signal_minutes * signal_bars
    if total_minutes % execution_minutes:
        raise ValueError("short_cycle_execution_horizon_not_aligned")
    return total_minutes // execution_minutes


def run_formal_strategy_backtest(
    strategy_version: StrategyVersionRecord,
    evaluation_binding: EvaluationBindingRecord,
    snapshot: DataSnapshotRecord,
    manifest_root: Path | str,
) -> BacktestAdapterResult:
    """Evaluate one immutable strategy/binding/snapshot combination."""

    if evaluation_binding.dataSnapshotId != snapshot.dataSnapshotId:
        raise ValueError("evaluation_binding_snapshot_mismatch")
    metadata = snapshot.manifest.get("metadata") or {}
    if not metadata.get("formalResearchEligible") or not metadata.get(
        "pointInTimeValidated"
    ):
        raise ValueError("formal_snapshot_not_eligible")
    directory = (
        Path(manifest_root).resolve()
        / evaluation_binding.strategyDataContractId
        / snapshot.dataSnapshotId
    )
    manifests = _load_manifests(directory, evaluation_binding)
    canonical_root_value = evaluation_binding.evidence.get("canonicalRoot")
    canonical_root = (
        Path(str(canonical_root_value)).resolve()
        if canonical_root_value
        else (Path(manifest_root).resolve().parent / "canonical").resolve()
    )
    ohlcv, funding, source_hashes = _snapshot_frames(snapshot, canonical_root)
    signal_timeframe = str(
        evaluation_binding.evidence.get("signalTimeframe")
        or strategy_version.definition.get("timeframe")
        or ""
    )
    execution_timeframe = str(
        evaluation_binding.evidence.get("executionTimeframe") or ""
    )
    if not execution_timeframe:
        execution_timeframe = next(
            (
                value
                for value in ("5m", "15m", "1h", signal_timeframe)
                if value in ohlcv
            ),
            "",
        )
    signal_frames = ohlcv.get(signal_timeframe) or {}
    execution_frames = ohlcv.get(execution_timeframe) or {}
    if not signal_frames or not execution_frames:
        raise ValueError(
            f"formal_snapshot_timeframe_missing:{signal_timeframe}:{execution_timeframe}"
        )
    signal_engine = str(
        strategy_version.definition.get("signalEngine") or "alpha191_observer_v1"
    )
    overlay_id = ""
    if signal_engine == "alpha191_observer_v1":
        panel = build_derivatives_feature_panel_from_frames(
            signal_frames,
            timeframe=signal_timeframe,
            funding_frames=funding,
        ).rows
        overlay_id = str(strategy_version.parameters.get("overlayId") or "")
        signals = build_alpha191_observer_signals(panel, overlay_id=overlay_id)
        stop_loss_pct = float(strategy_version.parameters.get("stopLossPct") or 0)
        horizon_bars = int(strategy_version.parameters.get("horizonBars") or 0)
    elif signal_engine == "short_cycle_v1":
        signals = build_short_cycle_formal_signals(
            signal_frames,
            signal_timeframe=signal_timeframe,
            family=str(strategy_version.definition.get("signalFamily") or ""),
            expected_direction=str(
                strategy_version.definition.get("direction") or ""
            ),
            parameters=strategy_version.parameters,
        )
        stop_loss_pct = 0.0
        horizon_bars = _execution_horizon(
            signal_timeframe=signal_timeframe,
            execution_timeframe=execution_timeframe,
            signal_bars=int(strategy_version.parameters.get("max_hold") or 0),
        )
    else:
        raise ValueError(f"formal_signal_engine_not_supported:{signal_engine}")
    target_r = float(strategy_version.definition.get("targetR") or 0)
    exit_policy = str(
        strategy_version.definition.get("exitPolicy")
        or "fixed_target_full_exit_v1"
    )
    if exit_policy not in {
        "fixed_target_full_exit_v1",
        "two_r_half_atr_runner_v1",
    }:
        raise ValueError(f"formal_exit_policy_not_supported:{exit_policy}")
    cost = manifests["cost"]
    if target_r < 2 or float(cost.get("targetR") or 0) < 2:
        raise ValueError("formal_target_r_below_2")
    fee_rate = float(cost.get("feeRate", evaluation_binding.costModel.get("feeRate", 0)))
    slippage_rate = float(
        cost.get("slippageRate", evaluation_binding.costModel.get("slippageRate", 0))
    )
    latency_values = [int(value) for value in cost.get("latencyBars") or [0]]
    stress_values = [float(value) for value in cost.get("stressMultipliers") or [1.0]]
    baseline_latency = min(latency_values)
    baseline_stress = min(stress_values)
    regime_lookup = _regime_lookup(signal_frames)
    trades: list[dict[str, Any]] = []
    stress_rows: list[dict[str, Any]] = []
    stress_missing_count = 0
    short_cycle_last_exit: dict[str, int] = {}
    prepared_execution_paths: dict[str, PreparedFixedRExecutionPath] = {}
    signal_timestamp_indexes: dict[str, pd.Index] = {}
    for _, signal in signals.iterrows():
        instrument = _pair_to_instrument(str(signal["pair"]))
        execution = execution_frames.get(instrument)
        signal_source = signal_frames.get(instrument)
        if execution is None or signal_source is None:
            continue
        timestamp = int(signal["signalTimestampMs"])
        prepared_path = prepared_execution_paths.get(instrument)
        if prepared_path is None:
            prepared_path = prepare_fixed_r_execution_path(
                execution,
                funding.get(instrument),
            )
            prepared_execution_paths[instrument] = prepared_path
        if signal_engine == "short_cycle_v1":
            signal_index = int(signal["signalIndex"])
            if timestamp <= short_cycle_last_exit.get(instrument, -1):
                continue
            row_stop_loss_pct = float(signal["stopLossPct"])
        else:
            timestamp_index = signal_timestamp_indexes.get(instrument)
            if timestamp_index is None:
                timestamp_index = pd.Index(
                    pd.to_numeric(
                        signal_source.sort_values("timestamp_ms")["timestamp_ms"]
                    ).astype("int64")
                )
                signal_timestamp_indexes[instrument] = timestamp_index
            signal_index = int(timestamp_index.searchsorted(timestamp))
            row_stop_loss_pct = stop_loss_pct
        split, fold = _split_for_signal(
            instrument=instrument,
            timestamp=timestamp,
            signal_index=signal_index,
            manifests=manifests,
        )
        base_config = FixedRPathConfig(
            stopLossPct=row_stop_loss_pct,
            targetR=target_r,
            horizonBars=horizon_bars,
            feeRate=fee_rate,
            slippageRate=slippage_rate,
            latencyBars=baseline_latency,
            slippageMultiplier=baseline_stress,
            exitPolicy=exit_policy,
        )
        try:
            outcome = evaluate_prepared_fixed_r_path(
                signalTimestampMs=timestamp,
                direction=str(signal["direction"]),
                preparedPath=prepared_path,
                config=base_config,
            )
        except ValueError as exc:
            if str(exc) == "fixed_r_entry_bar_missing":
                continue
            raise
        row = {
            **asdict(outcome),
            "instrumentId": instrument,
            "signalTimestampMs": timestamp,
            "setupName": str(signal.get("setupName") or ""),
            "overlayId": overlay_id,
            "split": split,
            "fold": fold,
            "regime": _regime_at(regime_lookup, timestamp),
        }
        trades.append(row)
        if signal_engine == "short_cycle_v1":
            short_cycle_last_exit[instrument] = int(outcome.exitTimestampMs)
        try:
            stressed = evaluate_prepared_fixed_r_path(
                signalTimestampMs=timestamp,
                direction=str(signal["direction"]),
                preparedPath=prepared_path,
                config=FixedRPathConfig(
                    stopLossPct=row_stop_loss_pct,
                    targetR=target_r,
                    horizonBars=horizon_bars,
                    feeRate=fee_rate,
                    slippageRate=slippage_rate,
                    latencyBars=max(latency_values),
                    slippageMultiplier=max(stress_values),
                    exitPolicy=exit_policy,
                ),
            )
        except ValueError as exc:
            if str(exc) != "fixed_r_entry_bar_missing":
                raise
            stress_missing_count += 1
        else:
            stress_rows.append({"netR": stressed.netR, "split": split})

    overall = _summary(trades)
    by_split = _group_metrics(
        trades,
        "split",
        required=("development", "walk_forward", "holdout", "locked_oos"),
    )
    stress_by_split = {
        split: _stress_summary(
            [row for row in stress_rows if str(row["split"]) == split]
        )
        for split in ("development", "walk_forward", "holdout", "locked_oos")
    }
    stress_net = [float(row["netR"]) for row in stress_rows]
    metrics = {
        **overall,
        "holdoutTradeCount": by_split["holdout"]["tradeCount"],
        "lockedTradeCount": by_split["locked_oos"]["tradeCount"],
        "bySplit": by_split,
        "bySymbol": _group_metrics(trades, "instrumentId"),
        "byRegime": _group_metrics(trades, "regime"),
        "costStress": {
            "tradeCount": len(stress_net),
            "missingPathCount": stress_missing_count,
            "averageNetR": round(sum(stress_net) / len(stress_net), 8)
            if stress_net
            else 0.0,
            "bySplit": stress_by_split,
            "latencyBars": max(latency_values),
            "slippageMultiplier": max(stress_values),
        },
    }
    checks = {
        "snapshotBound": bool(source_hashes),
        "manifestBound": True,
        "targetRFixed": target_r >= 2,
        "lockedOos": metrics["lockedTradeCount"] > 0,
        "holdout": metrics["holdoutTradeCount"] > 0,
        "costStress": bool(stress_net)
        and stress_missing_count == 0
        and metrics["costStress"]["averageNetR"] > 0,
        "stability": all(
            by_split[name]["tradeCount"] > 0
            for name in ("development", "walk_forward", "holdout", "locked_oos")
        ),
    }
    evidence = {
        "strategyVersionId": strategy_version.strategyVersionId,
        "strategyContentHash": strategy_version.contentHash,
        "evaluationBindingId": evaluation_binding.evaluationBindingId,
        "dataSnapshotId": snapshot.dataSnapshotId,
        "dataSnapshotContentHash": snapshot.contentHash,
        "walkForwardManifestHash": evaluation_binding.walkForwardManifestHash,
        "holdoutManifestHash": evaluation_binding.holdoutManifestHash,
        "lockedOosManifestHash": evaluation_binding.lockedOosManifestHash,
        "regimeManifestHash": str(
            evaluation_binding.evidence["regimeManifestHash"]
        ),
        "costManifestHash": str(evaluation_binding.evidence["costManifestHash"]),
        "sourceFileHashes": source_hashes,
        "signalTimeframe": signal_timeframe,
        "executionTimeframe": execution_timeframe,
        "exitPolicy": exit_policy,
        "plannedTargetR": target_r,
        "formalResearchOnly": True,
        "orderCreation": False,
    }
    report_core = {
        "schemaVersion": (
            "formal_fixed_2r_half_atr_runner_backtest_v1"
            if exit_policy == "two_r_half_atr_runner_v1"
            else "formal_fixed_2r_backtest_v1"
        ),
        "metrics": metrics,
        "checks": checks,
        "evidence": evidence,
        "trades": trades,
    }
    report = {
        **report_core,
        "resultHash": stable_hash(report_core, prefix="formal_backtest"),
    }
    report_path = directory / "formal-backtest-result.json"
    write_json_atomic(report_path, report)
    result_evidence = {
        **evidence,
        "reportPath": str(report_path),
        "reportSha256": sha256_file(report_path),
        "resultHash": report["resultHash"],
    }
    return BacktestAdapterResult(
        metrics=metrics,
        checks=checks,
        evidence=result_evidence,
    )
