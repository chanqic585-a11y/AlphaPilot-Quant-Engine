"""Local OHLCV loader for V13.4.21 factor research.

The loader reads local public Freqtrade data files only. It does not download
data, call exchange APIs, read accounts, create orders, run backtests, or auto
trade.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.factors.factor_schema import FactorDataPanelConfig

SUPPORTED_SUFFIXES = (".feather", ".parquet", ".json", ".json.gz")
REQUIRED_COLUMNS = ("date", "open", "high", "low", "close", "volume")


@dataclass
class OhlcvLoadReport:
    loadedPairs: list[str] = field(default_factory=list)
    failedPairs: list[dict[str, str]] = field(default_factory=list)
    missingTimeframes: list[str] = field(default_factory=list)
    formatUsed: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "loadedPairs": self.loadedPairs,
            "failedPairs": self.failedPairs,
            "missingTimeframes": self.missingTimeframes,
            "formatUsed": self.formatUsed,
            "warnings": self.warnings,
        }


@dataclass
class OhlcvLoadResult:
    frames: dict[str, pd.DataFrame]
    report: OhlcvLoadReport


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def parse_timerange(timerange: str) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    start_raw, _, end_raw = timerange.partition("-")
    start = pd.Timestamp(datetime.strptime(start_raw, "%Y%m%d"), tz="UTC") if start_raw else None
    end = pd.Timestamp(datetime.strptime(end_raw, "%Y%m%d"), tz="UTC") if end_raw else None
    return start, end


def normalize_pair_from_filename(path: Path, timeframe: str) -> str | None:
    stem = path.name
    marker = f"-{timeframe}-"
    if marker not in stem:
        return None
    pair_part = stem.split(marker, 1)[0]
    parts = pair_part.split("_")
    if len(parts) < 3:
        return None
    base = parts[0]
    quote = parts[1]
    settle = parts[2]
    return f"{base}/{quote}:{settle}"


def pair_to_freqtrade_stem(pair: str) -> str:
    return pair.replace("/", "_").replace(":", "_")


def discover_ohlcv_files(data_path: str | Path, timeframe: str) -> dict[str, Path]:
    root = Path(data_path)
    discovered: dict[str, Path] = {}
    if not root.exists():
        return discovered
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if not any(path.name.endswith(suffix) for suffix in SUPPORTED_SUFFIXES):
            continue
        if f"-{timeframe}-" not in path.name:
            continue
        if not path.name.endswith(f"{timeframe}-futures.feather") and "-futures" not in path.name:
            continue
        pair = normalize_pair_from_filename(path, timeframe)
        if pair and pair not in discovered:
            discovered[pair] = path
    return discovered


def _candidate_files_for_pair(data_path: str | Path, pair: str, timeframe: str) -> list[Path]:
    root = Path(data_path)
    stem = pair_to_freqtrade_stem(pair)
    return [
        root / f"{stem}-{timeframe}-futures.feather",
        root / f"{stem}-{timeframe}-futures.parquet",
        root / f"{stem}-{timeframe}-futures.json",
        root / f"{stem}-{timeframe}-futures.json.gz",
    ]


def _read_ohlcv_file(path: Path) -> pd.DataFrame:
    suffixes = "".join(path.suffixes)
    if path.suffix == ".feather":
        return pd.read_feather(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if suffixes.endswith(".json.gz") or path.suffix == ".json":
        return pd.read_json(path)
    raise ValueError(f"Unsupported OHLCV file format: {path.as_posix()}")


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number


def _normalize_frame(frame: pd.DataFrame, pair: str, timerange: str) -> pd.DataFrame:
    missing = sorted(set(REQUIRED_COLUMNS).difference(frame.columns))
    if missing:
        raise ValueError(f"missing_columns: {','.join(missing)}")

    output = frame.loc[:, list(REQUIRED_COLUMNS)].copy()
    output["date"] = pd.to_datetime(output["date"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        output[column] = pd.to_numeric(output[column], errors="coerce")
    output = output.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    output = output.sort_values("date").drop_duplicates(subset=["date"], keep="last")

    start, end = parse_timerange(timerange)
    if start is not None:
        output = output[output["date"] >= start]
    if end is not None:
        output = output[output["date"] < end]
    output["pair"] = pair
    if output.empty:
        raise ValueError("empty_after_timerange_filter")
    return output.reset_index(drop=True)


def load_local_ohlcv(config: FactorDataPanelConfig) -> OhlcvLoadResult:
    report = OhlcvLoadReport()
    discovered = discover_ohlcv_files(config.dataPath, config.timeframe)
    requested_pairs = config.pairs or sorted(discovered.keys())
    frames: dict[str, pd.DataFrame] = {}

    if not requested_pairs:
        report.warnings.append(f"No local OHLCV files discovered under {config.dataPath} for timeframe {config.timeframe}.")
        return OhlcvLoadResult(frames=frames, report=report)

    for pair in requested_pairs:
        path = discovered.get(pair)
        if path is None:
            path = next((candidate for candidate in _candidate_files_for_pair(config.dataPath, pair, config.timeframe) if candidate.exists()), None)
        if path is None:
            report.failedPairs.append({"pair": pair, "reason": f"missing_{config.timeframe}_futures_file"})
            report.missingTimeframes.append(f"{pair}:{config.timeframe}")
            continue
        try:
            raw = _read_ohlcv_file(path)
            frame = _normalize_frame(raw, pair, config.timerange)
        except ImportError as exc:
            report.failedPairs.append({"pair": pair, "reason": f"missing_dependency: {exc}"})
            continue
        except Exception as exc:  # noqa: BLE001 - failures are written to the load report.
            report.failedPairs.append({"pair": pair, "reason": str(exc)})
            continue
        frames[pair] = frame
        report.loadedPairs.append(pair)
        report.formatUsed[pair] = "".join(path.suffixes).lstrip(".")

    if report.failedPairs:
        report.warnings.append("Some pairs could not be loaded. Failed pairs remain excluded; no data was fabricated.")
    if not frames:
        report.warnings.append("No readable OHLCV frames loaded. Factor panel generation is blocked.")
    return OhlcvLoadResult(frames=frames, report=report)
