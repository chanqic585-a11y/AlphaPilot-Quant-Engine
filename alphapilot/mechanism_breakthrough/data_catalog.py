"""Read-only discovery of reusable local OHLCV snapshots."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


@dataclass(frozen=True)
class LocalOhlcvAsset:
    instrument_id: str
    timeframe: str
    path: Path
    byte_size: int

    def to_dict(self) -> dict[str, object]:
        row = asdict(self)
        row["path"] = str(self.path)
        return row


@dataclass(frozen=True)
class LocalOhlcvCatalog:
    root: Path
    assets: tuple[LocalOhlcvAsset, ...]
    network_calls: int = 0

    def by_timeframe(self, timeframe: str) -> tuple[LocalOhlcvAsset, ...]:
        return tuple(row for row in self.assets if row.timeframe == timeframe)


def discover_local_ohlcv(
    root: str | Path,
    *,
    timeframes: Iterable[str] = ("1h", "4h"),
) -> LocalOhlcvCatalog:
    """Select one fullest immutable local file per instrument/timeframe."""

    resolved = Path(root).resolve()
    allowed = set(timeframes)
    selected: dict[tuple[str, str], LocalOhlcvAsset] = {}
    for path in resolved.rglob("*.parquet"):
        try:
            timeframe = path.parent.name
            instrument_id = path.parent.parent.name
        except IndexError:
            continue
        if timeframe not in allowed or not instrument_id.endswith("-USDT-SWAP"):
            continue
        asset = LocalOhlcvAsset(
            instrument_id=instrument_id,
            timeframe=timeframe,
            path=path.resolve(),
            byte_size=path.stat().st_size,
        )
        key = (instrument_id, timeframe)
        current = selected.get(key)
        if current is None or (asset.byte_size, asset.path.name) > (
            current.byte_size,
            current.path.name,
        ):
            selected[key] = asset
    return LocalOhlcvCatalog(
        root=resolved,
        assets=tuple(selected[key] for key in sorted(selected)),
        network_calls=0,
    )


def _normalize_frame(frame: pd.DataFrame) -> pd.DataFrame:
    normalized = frame.copy()
    if "date" not in normalized and "timestamp_ms" in normalized:
        normalized["date"] = pd.to_datetime(normalized["timestamp_ms"], unit="ms", utc=True)
    normalized["date"] = pd.to_datetime(normalized["date"], utc=True)
    required = {"date", "open", "high", "low", "close", "volume"}
    missing = sorted(required - set(normalized))
    if missing:
        raise ValueError(f"local_ohlcv_columns_missing:{','.join(missing)}")
    for name in ("open", "high", "low", "close", "volume"):
        normalized[name] = pd.to_numeric(normalized[name], errors="coerce")
    return (
        normalized.dropna(subset=list(required))
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def load_development_frame(
    path: str | Path,
    *,
    development_fraction: float = 0.8,
) -> tuple[pd.DataFrame, dict[str, object]]:
    if not 0.5 <= development_fraction < 1.0:
        raise ValueError("development_fraction_out_of_bounds")
    frame = _normalize_frame(pd.read_parquet(Path(path)))
    split = max(1, int(len(frame) * development_fraction))
    development = frame.iloc[:split].copy()
    return development, {
        "path": str(Path(path).resolve()),
        "totalRowCount": int(len(frame)),
        "developmentRowCount": int(len(development)),
        "reservedLockedOosRowCount": int(len(frame) - len(development)),
        "lockedOosReadCount": 0,
        "economicResultReadScope": "development_only",
    }

