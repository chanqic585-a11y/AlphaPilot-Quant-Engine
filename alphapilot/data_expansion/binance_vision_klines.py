"""Download Binance Vision public USDT futures klines.

This module downloads public historical kline zip files from Binance Vision and
converts them to local Freqtrade-style feather files. It does not use API keys,
private endpoints, account data, position data, orders, dry-run, or live
trading.
"""

from __future__ import annotations

import io
import json
import time
import urllib.error
import urllib.request
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd


BINANCE_VISION_BASE = "https://data.binance.vision/data/futures/um/monthly/klines"
KLINE_COLUMNS = [
    "open_time",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
]


@dataclass(frozen=True)
class BinanceVisionDownloadConfig:
    pairs: tuple[str, ...]
    timeframes: tuple[str, ...]
    startMonth: str = "2020-01"
    endMonth: str = "2026-07"
    outputPath: Path = Path("user_data/data/binance_vision/futures")
    cachePath: Path = Path("user_data/data/binance_vision/raw_zip_cache")
    workers: int = 6
    force: bool = False
    timeoutSeconds: int = 30


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def pair_to_binance_symbol(pair: str) -> str:
    return pair.split(":", 1)[0].replace("/", "")


def pair_to_freqtrade_stem(pair: str) -> str:
    return pair.replace("/", "_").replace(":", "_")


def iter_months(start_month: str, end_month: str) -> list[str]:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    return [period.strftime("%Y-%m") for period in pd.period_range(start, end, freq="M")]


def _monthly_url(symbol: str, timeframe: str, month: str) -> str:
    return f"{BINANCE_VISION_BASE}/{symbol}/{timeframe}/{symbol}-{timeframe}-{month}.zip"


def _cache_file(cache_path: Path, symbol: str, timeframe: str, month: str) -> Path:
    return cache_path / symbol / timeframe / f"{symbol}-{timeframe}-{month}.zip"


def _download_bytes(url: str, timeout: int) -> bytes | None:
    request = urllib.request.Request(url, headers={"User-Agent": "AlphaPilotResearchDownloader/13.7.40"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            return response.read()
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise
    except urllib.error.URLError:
        return None


def _read_zip_frame(payload: bytes) -> pd.DataFrame:
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        names = [name for name in archive.namelist() if name.endswith(".csv")]
        if not names:
            return pd.DataFrame(columns=KLINE_COLUMNS)
        with archive.open(names[0]) as handle:
            frame = pd.read_csv(handle, header=None)
    if frame.empty:
        return pd.DataFrame(columns=KLINE_COLUMNS)
    if str(frame.iloc[0, 0]).lower() in {"open_time", "open time"}:
        frame = frame.iloc[1:].reset_index(drop=True)
    frame = frame.iloc[:, : len(KLINE_COLUMNS)]
    frame.columns = KLINE_COLUMNS[: len(frame.columns)]
    return frame


def _normalise_frame(raw: pd.DataFrame, pair: str) -> pd.DataFrame:
    if raw.empty:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume", "pair"])
    frame = raw.copy()
    frame["date"] = pd.to_datetime(pd.to_numeric(frame["open_time"], errors="coerce"), unit="ms", utc=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    frame = frame.loc[:, ["date", "open", "high", "low", "close", "volume"]]
    frame = frame.sort_values("date").drop_duplicates(subset=["date"], keep="last")
    frame["pair"] = pair
    return frame


def _fetch_month(
    *,
    pair: str,
    symbol: str,
    timeframe: str,
    month: str,
    cache_path: Path,
    timeout: int,
    force: bool,
) -> dict[str, Any]:
    url = _monthly_url(symbol, timeframe, month)
    cache_file = _cache_file(cache_path, symbol, timeframe, month)
    payload: bytes | None = None
    source = "downloaded"
    if cache_file.exists() and not force:
        payload = cache_file.read_bytes()
        source = "cache"
    else:
        payload = _download_bytes(url, timeout)
        if payload:
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(payload)
    if not payload:
        return {
            "pair": pair,
            "symbol": symbol,
            "timeframe": timeframe,
            "month": month,
            "status": "missing",
            "url": url,
            "rowCount": 0,
        }
    try:
        frame = _normalise_frame(_read_zip_frame(payload), pair)
    except Exception as exc:  # pragma: no cover - report defensive path
        return {
            "pair": pair,
            "symbol": symbol,
            "timeframe": timeframe,
            "month": month,
            "status": "failed_parse",
            "url": url,
            "error": str(exc),
            "rowCount": 0,
        }
    return {
        "pair": pair,
        "symbol": symbol,
        "timeframe": timeframe,
        "month": month,
        "status": "loaded",
        "source": source,
        "url": url,
        "rowCount": int(len(frame)),
        "frame": frame,
    }


def download_binance_vision_klines(config: BinanceVisionDownloadConfig) -> dict[str, Any]:
    months = iter_months(config.startMonth, config.endMonth)
    tasks: list[dict[str, str]] = []
    for pair in config.pairs:
        symbol = pair_to_binance_symbol(pair)
        for timeframe in config.timeframes:
            for month in months:
                tasks.append({"pair": pair, "symbol": symbol, "timeframe": timeframe, "month": month})

    monthly_results: list[dict[str, Any]] = []
    frames_by_key: dict[tuple[str, str], list[pd.DataFrame]] = {}
    started = time.time()
    with ThreadPoolExecutor(max_workers=max(1, config.workers)) as executor:
        futures = [
            executor.submit(
                _fetch_month,
                pair=task["pair"],
                symbol=task["symbol"],
                timeframe=task["timeframe"],
                month=task["month"],
                cache_path=config.cachePath,
                timeout=config.timeoutSeconds,
                force=config.force,
            )
            for task in tasks
        ]
        for future in as_completed(futures):
            result = future.result()
            frame = result.pop("frame", None)
            monthly_results.append(result)
            if frame is not None and not frame.empty:
                frames_by_key.setdefault((result["pair"], result["timeframe"]), []).append(frame)

    output_rows: list[dict[str, Any]] = []
    config.outputPath.mkdir(parents=True, exist_ok=True)
    for (pair, timeframe), frames in sorted(frames_by_key.items()):
        merged = pd.concat(frames, ignore_index=True)
        merged = merged.sort_values("date").drop_duplicates(subset=["date"], keep="last")
        merged = merged.loc[:, ["date", "open", "high", "low", "close", "volume"]]
        output_file = config.outputPath / f"{pair_to_freqtrade_stem(pair)}-{timeframe}-futures.feather"
        merged.reset_index(drop=True).to_feather(output_file)
        output_rows.append(
            {
                "pair": pair,
                "timeframe": timeframe,
                "outputFile": output_file.as_posix(),
                "rowCount": int(len(merged)),
                "start": merged["date"].min().isoformat() if not merged.empty else None,
                "end": merged["date"].max().isoformat() if not merged.empty else None,
            }
        )

    status_counts: dict[str, int] = {}
    for result in monthly_results:
        status_counts[result["status"]] = status_counts.get(result["status"], 0) + 1

    return {
        "version": "V13.7.40",
        "source": "binance_vision_public_monthly_klines_v13_7_40",
        "generatedAt": utc_now(),
        "status": "completed",
        "config": {
            "pairs": list(config.pairs),
            "timeframes": list(config.timeframes),
            "startMonth": config.startMonth,
            "endMonth": config.endMonth,
            "outputPath": config.outputPath.as_posix(),
            "cachePath": config.cachePath.as_posix(),
            "workers": config.workers,
            "force": config.force,
        },
        "taskCount": len(tasks),
        "statusCounts": status_counts,
        "outputCount": len(output_rows),
        "outputs": output_rows,
        "missingSamples": [row for row in monthly_results if row["status"] != "loaded"][:200],
        "elapsedSeconds": round(time.time() - started, 3),
        "safetyBoundary": {
            "publicDataOnly": True,
            "apiKeyStorage": False,
            "tradeApiEnabled": False,
            "withdrawApiEnabled": False,
            "realAccountReads": False,
            "realPositionReads": False,
            "orderCreation": False,
            "exchangeDryRun": False,
            "liveTrading": False,
            "autoTrading": False,
        },
    }


def save_download_report(report: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
