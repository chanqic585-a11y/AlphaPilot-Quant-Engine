"""Import local swap OHLCV XLSX files into Freqtrade feather data.

This importer is research-only. It reads local public-market datasets and writes
local backtest files. It does not request exchanges, use API keys, read accounts,
or create orders.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_SOURCE_DIR = Path(r"D:\BaiduNetdiskDownload\合约数据")
DEFAULT_OUTPUT_DIR = Path("user_data/data/local_contract_xlsx/okx/futures")
DEFAULT_REPORT_PATH = Path("reports/contract_swap_xlsx_import_report.json")
TIMEFRAME_DIRS = {
    "15m": "swap_candles_15m",
    "1h": "swap_candles_1H",
    "4h": "swap_candles_4H",
    "1d": "swap_candles_1D",
}


@dataclass
class ImportedSwapTimeframe:
    timeframe: str
    sourcePath: str | None
    status: str
    rows: int = 0
    outputPath: str | None = None
    start: str | None = None
    end: str | None = None
    error: str | None = None


@dataclass
class ImportedSwapPair:
    symbol: str
    pair: str
    status: str
    timeframes: list[ImportedSwapTimeframe] = field(default_factory=list)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_csv(value: str | None) -> list[str]:
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def normalize_symbol(symbol: str) -> str:
    value = symbol.strip().upper()
    if value.endswith("/USDT:USDT"):
        value = value.split("/", 1)[0]
    if value.endswith("_USDT_SWAP"):
        value = value[: -len("_USDT_SWAP")]
    return value


def parse_symbols(value: str | None) -> list[str]:
    symbols = [normalize_symbol(item) for item in parse_csv(value)]
    return [item for item in symbols if item]


def parse_timeframes(value: str) -> list[str]:
    requested = [item.strip() for item in value.split(",") if item.strip()]
    normalized = ["1d" if item.lower() == "1d" else item.lower() for item in requested]
    unknown = [item for item in normalized if item not in TIMEFRAME_DIRS]
    if unknown:
        raise ValueError(f"Unsupported timeframe(s): {', '.join(unknown)}")
    return normalized


def freqtrade_filename(symbol: str, timeframe: str) -> str:
    return f"{symbol}_USDT_USDT-{timeframe}-futures.feather"


def pair_name(symbol: str) -> str:
    return f"{symbol}/USDT:USDT"


def find_source_file(source_dir: Path, symbol: str, timeframe: str) -> Path | None:
    folder = source_dir / TIMEFRAME_DIRS[timeframe] / f"{symbol}_USDT_SWAP"
    preferred = folder / f"{symbol}_USDT_SWAP_{TIMEFRAME_DIRS[timeframe]}_ALL.xlsx"
    if preferred.exists():
        return preferred
    matches = sorted(folder.glob(f"{symbol}_USDT_SWAP_{TIMEFRAME_DIRS[timeframe]}_*.xlsx"))
    return matches[-1] if matches else None


def clean_ohlcv(path: Path) -> pd.DataFrame:
    raw = pd.read_excel(path)
    required = {"utc_time", "open", "high", "low", "close"}
    missing = required - set(raw.columns)
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
    if "confirmed" in raw.columns:
        raw = raw[raw["confirmed"].fillna(True).astype(bool)]
    volume_column = "volume_quote_currency" if "volume_quote_currency" in raw.columns else "volume_base_or_contracts"
    if volume_column not in raw.columns:
        raise ValueError("Missing volume column")
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["utc_time"], utc=True, errors="coerce"),
            "open": pd.to_numeric(raw["open"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
            "volume": pd.to_numeric(raw[volume_column], errors="coerce"),
        }
    )
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    frame = frame.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    frame["date"] = pd.to_datetime(frame["date"], utc=True).dt.floor("ms")
    return frame[["date", "open", "high", "low", "close", "volume"]]


def iso_or_none(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def import_timeframe(
    source_dir: Path,
    output_dir: Path,
    symbol: str,
    timeframe: str,
    overwrite: bool,
) -> ImportedSwapTimeframe:
    source_path = find_source_file(source_dir, symbol, timeframe)
    if source_path is None:
        return ImportedSwapTimeframe(timeframe=timeframe, sourcePath=None, status="missing")
    output_path = output_dir / freqtrade_filename(symbol, timeframe)
    if output_path.exists() and not overwrite:
        existing = pd.read_feather(output_path, columns=["date"])
        return ImportedSwapTimeframe(
            timeframe=timeframe,
            sourcePath=str(source_path),
            status="existing",
            rows=len(existing),
            outputPath=str(output_path),
            start=iso_or_none(existing["date"].min()) if not existing.empty else None,
            end=iso_or_none(existing["date"].max()) if not existing.empty else None,
        )
    try:
        frame = clean_ohlcv(source_path)
        if frame.empty:
            return ImportedSwapTimeframe(timeframe=timeframe, sourcePath=str(source_path), status="empty")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_feather(output_path)
        return ImportedSwapTimeframe(
            timeframe=timeframe,
            sourcePath=str(source_path),
            status="imported",
            rows=len(frame),
            outputPath=str(output_path),
            start=iso_or_none(frame["date"].min()),
            end=iso_or_none(frame["date"].max()),
        )
    except Exception as exc:  # noqa: BLE001 - report per-file import failure and keep the batch moving.
        return ImportedSwapTimeframe(
            timeframe=timeframe,
            sourcePath=str(source_path),
            status="failed",
            error=str(exc),
        )


def import_pair(source_dir: Path, output_dir: Path, symbol: str, timeframes: Iterable[str], overwrite: bool) -> ImportedSwapPair:
    results = [import_timeframe(source_dir, output_dir, symbol, timeframe, overwrite) for timeframe in timeframes]
    if any(item.status in {"imported", "existing"} for item in results):
        status = "imported"
    elif any(item.status == "failed" for item in results):
        status = "failed"
    else:
        status = "missing"
    return ImportedSwapPair(symbol=symbol, pair=pair_name(symbol), status=status, timeframes=results)


def build_report(imported: list[ImportedSwapPair], source_dir: Path, output_dir: Path, timeframes: list[str]) -> dict[str, object]:
    timeframe_rows = [
        timeframe
        for pair in imported
        for timeframe in pair.timeframes
    ]
    return {
        "reportId": "contract_swap_xlsx_import_report",
        "source": "alphapilot_contract_swap_xlsx_importer",
        "sourceDir": str(source_dir),
        "outputDir": str(output_dir),
        "timeframes": timeframes,
        "totalPairs": len(imported),
        "importedPairCount": sum(1 for item in imported if item.status == "imported"),
        "failedPairCount": sum(1 for item in imported if item.status == "failed"),
        "missingPairCount": sum(1 for item in imported if item.status == "missing"),
        "importedTimeframeCount": sum(1 for item in timeframe_rows if item.status in {"imported", "existing"}),
        "failedTimeframeCount": sum(1 for item in timeframe_rows if item.status == "failed"),
        "missingTimeframeCount": sum(1 for item in timeframe_rows if item.status == "missing"),
        "pairs": [asdict(item) for item in imported],
        "safetyBoundary": {
            "localPublicDatasetOnly": True,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyStored": False,
            "accountRead": False,
            "positionRead": False,
            "orderCreated": False,
            "autoTradingUsed": False,
        },
        "generatedAt": utc_now(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import local swap OHLCV XLSX files into Freqtrade feather files.")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--symbols", required=True)
    parser.add_argument("--timeframes", default="1h,4h")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    report_path = Path(args.report_path)
    symbols = parse_symbols(args.symbols)
    timeframes = parse_timeframes(args.timeframes)
    if not source_dir.exists():
        raise SystemExit(f"Source directory not found: {source_dir}")
    if not symbols:
        raise SystemExit("No symbols provided.")
    imported = [import_pair(source_dir, output_dir, symbol, timeframes, args.overwrite) for symbol in symbols]
    report = build_report(imported, source_dir, output_dir, timeframes)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("reportId", "totalPairs", "importedPairCount", "failedPairCount", "missingPairCount")}, ensure_ascii=False, indent=2))
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
