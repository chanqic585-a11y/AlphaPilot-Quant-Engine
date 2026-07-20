"""Run exact offline replays for the ten active 1h/1d Demo identities."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from alphapilot.factors.ohlcv_loader import _read_ohlcv_file, discover_ohlcv_files
from alphapilot.low_frequency.strategy_candidate_factory import _load_prepared_frames
from alphapilot.short_cycle.parameter_search import (
    _normalise_ohlcv,
    add_indicators,
    merge_btc_context,
)

from .adapters import ReplayResult, replay_low_frequency_candidate, replay_short_cycle_candidate
from .contracts import DemoReplayContract, load_replay_contracts


def load_original_candidates(
    low_frequency_report: str | Path,
    short_cycle_report: str | Path,
) -> dict[str, dict[str, Any]]:
    low_payload = json.loads(Path(low_frequency_report).read_text(encoding="utf-8"))
    short_payload = json.loads(Path(short_cycle_report).read_text(encoding="utf-8"))
    low_factory = low_payload.get("factory", low_payload)
    rows: dict[str, dict[str, Any]] = {}
    for row in low_factory.get("approvedCandidates", []):
        candidate_id = f"v13_7_20_{row['candidateId']}"
        rows[candidate_id] = dict(row)
    for row in short_payload.get("selectedCandidates", []):
        rows[str(row["candidateId"])] = dict(row)
    return rows


def _load_short_cycle_frames(
    data_path: Path,
    candidates: list[Mapping[str, Any]],
    *,
    timerange: str,
) -> tuple[dict[str, pd.DataFrame], list[str]]:
    pairs = {"BTC/USDT:USDT"}
    for candidate in candidates:
        pairs.update(str(pair) for pair in candidate["assetFilter"]["selectedPairs"])
    discovered = discover_ohlcv_files(data_path, "1h")
    frames: dict[str, pd.DataFrame] = {}
    warnings: list[str] = []
    for pair in sorted(pairs):
        path = discovered.get(pair)
        if path is None:
            warnings.append(f"missing_1h_pair:{pair}")
            continue
        frames[pair] = _normalise_ohlcv(_read_ohlcv_file(path), pair, timerange)
    missing = sorted(pairs.difference(frames))
    if missing:
        raise ValueError(f"short_cycle_required_data_missing:{','.join(missing)}")

    btc = add_indicators(frames["BTC/USDT:USDT"])
    prepared = {
        pair: merge_btc_context(add_indicators(frame), btc)
        for pair, frame in frames.items()
    }
    return prepared, warnings


def run_demo_release_replay(
    *,
    contracts_dir: str | Path,
    low_frequency_report: str | Path,
    short_cycle_report: str | Path,
    okx_data_path: str | Path,
    binance_vision_data_path: str | Path,
    expected_count: int = 10,
) -> tuple[
    tuple[DemoReplayContract, ...],
    dict[str, ReplayResult],
    dict[str, dict[str, Any]],
    list[str],
]:
    contracts = load_replay_contracts(contracts_dir, expected_count=expected_count)
    originals = load_original_candidates(low_frequency_report, short_cycle_report)
    missing_originals = sorted(
        row.strategy_candidate_id for row in contracts if row.strategy_candidate_id not in originals
    )
    if missing_originals:
        raise ValueError(f"source_candidate_missing:{','.join(missing_originals)}")

    low_contracts = [row for row in contracts if row.timeframe == "1d"]
    short_contracts = [row for row in contracts if row.timeframe == "1h"]
    if len(low_contracts) != 5 or len(short_contracts) != 5:
        raise ValueError(f"unexpected_timeframe_mix:1d={len(low_contracts)},1h={len(short_contracts)}")

    low_source_payload = json.loads(Path(low_frequency_report).read_text(encoding="utf-8"))
    low_factory = low_source_payload.get("factory", low_source_payload)
    _, low_frames, low_warnings = _load_prepared_frames(
        Path(okx_data_path), str(low_factory.get("timerange", "20200101-")), "1d"
    )
    if not low_frames:
        raise ValueError("low_frequency_prepared_frames_empty")

    short_payload = json.loads(Path(short_cycle_report).read_text(encoding="utf-8"))
    short_candidates = [originals[row.strategy_candidate_id] for row in short_contracts]
    short_frames, short_warnings = _load_short_cycle_frames(
        Path(binance_vision_data_path),
        short_candidates,
        timerange=str(short_payload.get("config", {}).get("timerange", "20200101-")),
    )

    results: dict[str, ReplayResult] = {}
    for contract in low_contracts:
        results[contract.strategy_candidate_id] = replay_low_frequency_candidate(
            contract.strategy_candidate_id, low_frames
        )
    for contract in short_contracts:
        results[contract.strategy_candidate_id] = replay_short_cycle_candidate(
            originals[contract.strategy_candidate_id],
            short_frames,
            fee_rate=float(short_payload.get("config", {}).get("feeRate", 0.0005)),
            slippage_rate=float(short_payload.get("config", {}).get("slippageRate", 0.0005)),
        )
    return contracts, results, originals, [*low_warnings, *short_warnings]
