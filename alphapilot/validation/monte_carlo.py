from __future__ import annotations

import math
from typing import Any, Iterable

import numpy as np


def _quantiles(values: np.ndarray) -> dict[str, float]:
    return {
        "p10": float(np.quantile(values, 0.10)),
        "median": float(np.quantile(values, 0.50)),
        "p90": float(np.quantile(values, 0.90)),
        "p95": float(np.quantile(values, 0.95)),
    }


def run_monte_carlo(
    net_r_values: Iterable[float],
    *,
    risk_per_trade_pct: float,
    draws: int,
    seed: int,
    research_stop_pct: float | None = None,
    include_sample_rows: bool = False,
) -> dict[str, Any]:
    values = np.asarray([float(value) for value in net_r_values], dtype=float)
    if values.size == 0:
        result = {
            "draws": draws,
            "seed": seed,
            "status": "unavailable_no_trades",
        }
        if include_sample_rows:
            result["sampleRows"] = []
        return result
    rng = np.random.default_rng(seed)
    block_length = max(2, min(values.size, int(math.sqrt(values.size))))
    block_count = math.ceil(values.size / block_length)
    ending = np.empty(draws, dtype=float)
    maximum_drawdowns = np.empty(draws, dtype=float)
    maximum_loss_runs = np.empty(draws, dtype=int)
    ruined = np.empty(draws, dtype=bool)
    chunk_size = min(250, draws)
    offset = 0
    while offset < draws:
        count = min(chunk_size, draws - offset)
        starts = rng.integers(0, values.size, size=(count, block_count))
        additions = np.arange(block_length)
        indices = (starts[:, :, None] + additions) % values.size
        samples = values[indices.reshape(count, -1)[:, : values.size]]
        equity = np.ones(count, dtype=float)
        peak = np.ones(count, dtype=float)
        max_dd = np.zeros(count, dtype=float)
        current_loss = np.zeros(count, dtype=int)
        max_loss = np.zeros(count, dtype=int)
        active = np.ones(count, dtype=bool)
        for column in range(values.size):
            returns = samples[:, column]
            factors = 1 + returns * risk_per_trade_pct / 100
            equity[active] *= factors[active]
            peak = np.maximum(peak, equity)
            drawdown = np.where(peak > 0, (peak - equity) / peak * 100, 100.0)
            max_dd = np.maximum(max_dd, drawdown)
            current_loss = np.where((returns < 0) & active, current_loss + 1, 0)
            max_loss = np.maximum(max_loss, current_loss)
            active &= equity > 0
            if research_stop_pct is not None:
                active &= drawdown < research_stop_pct
        target = slice(offset, offset + count)
        ending[target] = equity * 100
        maximum_drawdowns[target] = max_dd
        maximum_loss_runs[target] = max_loss
        ruined[target] = equity <= 0
        offset += count
    result = {
        "draws": draws,
        "seed": seed,
        "blockMethod": "circular_block_bootstrap",
        "blockLengthTrades": block_length,
        "pathModel": "fixed_ratio_sequence_with_optional_research_stop",
        "overlapConstraintLimitation": (
            "resampled sequence cannot preserve original concurrent-position timing"
        ),
        "endingEquity": _quantiles(ending),
        "maximumDrawdownPct": _quantiles(maximum_drawdowns),
        "maximumConsecutiveLossesP95": float(
            np.quantile(maximum_loss_runs, 0.95)
        ),
        "probabilityDrawdownAtLeast10Pct": float(
            (maximum_drawdowns >= 10).mean()
        ),
        "probabilityDrawdownAtLeast15Pct": float(
            (maximum_drawdowns >= 15).mean()
        ),
        "probabilityDrawdownAtLeast20Pct": float(
            (maximum_drawdowns >= 20).mean()
        ),
        "probabilityRuin": float(ruined.mean()),
    }
    if include_sample_rows:
        result["sampleRows"] = [
            {
                "drawIndex": index,
                "endingEquity": float(ending[index]),
                "maximumDrawdownPct": float(maximum_drawdowns[index]),
                "maximumConsecutiveLosses": int(maximum_loss_runs[index]),
                "ruined": bool(ruined[index]),
            }
            for index in range(draws)
        ]
    return result
