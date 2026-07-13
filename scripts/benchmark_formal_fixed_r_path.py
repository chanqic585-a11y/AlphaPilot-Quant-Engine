"""Deterministic benchmark for the prepared fixed-R execution path."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import sys
from time import perf_counter

import numpy as np
import pandas as pd

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from alphapilot.evolution.evaluation.fixed_r_path import (
    FixedRPathConfig,
    evaluate_fixed_r_path,
    evaluate_prepared_fixed_r_path,
    prepare_fixed_r_execution_path,
)


def _frame(row_count: int) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(13_271_100)
    timestamps = np.arange(row_count, dtype=np.int64) * 300_000
    closes = 100.0 + np.cumsum(rng.normal(0.0, 0.08, row_count))
    opens = np.concatenate(([closes[0]], closes[:-1]))
    spread = np.abs(rng.normal(0.06, 0.02, row_count))
    execution = pd.DataFrame(
        {
            "timestamp_ms": timestamps,
            "open": opens,
            "high": np.maximum(opens, closes) + spread,
            "low": np.minimum(opens, closes) - spread,
            "close": closes,
        }
    )
    funding_indexes = np.arange(0, row_count, 96, dtype=np.int64)
    funding = pd.DataFrame(
        {
            "timestamp_ms": timestamps[funding_indexes],
            "funding_rate": rng.normal(0.00001, 0.00002, len(funding_indexes)),
        }
    )
    return execution, funding


def _digest(results: list[object]) -> str:
    payload = json.dumps(
        [asdict(result) for result in results],
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def run_benchmark(*, rows: int, signals: int, minimum_speedup: float) -> dict[str, object]:
    if rows < 10_000:
        raise ValueError("rows_must_be_at_least_10000")
    if signals < 10:
        raise ValueError("signals_must_be_at_least_10")
    execution, funding = _frame(rows)
    signal_indexes = np.linspace(100, rows - 500, signals, dtype=np.int64)
    signal_times = execution.iloc[signal_indexes]["timestamp_ms"].astype(int).tolist()
    config = FixedRPathConfig(
        stopLossPct=0.02,
        targetR=2.0,
        horizonBars=96,
        feeRate=0.0005,
        slippageRate=0.0002,
        latencyBars=1,
        slippageMultiplier=1.5,
    )

    started = perf_counter()
    compatibility_results = [
        evaluate_fixed_r_path(
            signalTimestampMs=timestamp,
            direction="long" if index % 2 == 0 else "short",
            executionFrame=execution,
            fundingFrame=funding,
            config=config,
        )
        for index, timestamp in enumerate(signal_times)
    ]
    compatibility_seconds = perf_counter() - started

    prepared = prepare_fixed_r_execution_path(execution, funding)
    started = perf_counter()
    prepared_results = [
        evaluate_prepared_fixed_r_path(
            signalTimestampMs=timestamp,
            direction="long" if index % 2 == 0 else "short",
            preparedPath=prepared,
            config=config,
        )
        for index, timestamp in enumerate(signal_times)
    ]
    prepared_seconds = perf_counter() - started

    compatibility_hash = _digest(compatibility_results)
    prepared_hash = _digest(prepared_results)
    parity = compatibility_hash == prepared_hash
    speedup = compatibility_seconds / max(prepared_seconds, 1e-9)
    result: dict[str, object] = {
        "schemaVersion": "formal_fixed_r_benchmark_v1",
        "rows": rows,
        "signals": signals,
        "parity": parity,
        "resultHash": prepared_hash,
        "compatibilitySeconds": round(compatibility_seconds, 4),
        "preparedSeconds": round(prepared_seconds, 4),
        "speedup": round(speedup, 2),
        "minimumSpeedup": minimum_speedup,
    }
    if not parity:
        raise RuntimeError(json.dumps({**result, "error": "result_parity_failed"}))
    if speedup < minimum_speedup:
        raise RuntimeError(json.dumps({**result, "error": "speedup_below_floor"}))
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=120_000)
    parser.add_argument("--signals", type=int, default=600)
    parser.add_argument("--minimum-speedup", type=float, default=10.0)
    args = parser.parse_args()
    print(
        json.dumps(
            run_benchmark(
                rows=args.rows,
                signals=args.signals,
                minimum_speedup=args.minimum_speedup,
            ),
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
