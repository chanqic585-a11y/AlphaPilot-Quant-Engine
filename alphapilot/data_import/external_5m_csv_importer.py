"""Import external 5m OHLCV CSV files into Freqtrade feather data.

The importer is research-only. It reads public/local OHLCV files and writes
local data files for backtesting. It does not request exchanges, use API keys,
or connect to private endpoints.
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd


DEFAULT_SOURCE_DIR = Path(r"E:\BaiduNetdiskDownload\5m")
DEFAULT_OUTPUT_DIR = Path("user_data/data/local5m/okx/futures")
DEFAULT_REPORT_PATH = Path("reports/external_5m_import_report.json")
FILENAME_RE = re.compile(r"^(?P<symbol>.+)_USDT_5m_from_\d+\.csv$", re.IGNORECASE)
TIMEFRAME_RULES = {
    "5m": "5min",
    "15m": "15min",
    "30m": "30min",
    "1h": "1h",
    "4h": "4h",
}


@dataclass
class ImportedTimeframe:
    timeframe: str
    rows: int
    outputPath: str
    start: str | None
    end: str | None


@dataclass
class ImportedPair:
    pair: str
    sourcePath: str
    status: str
    sourceRows: int = 0
    importedRows: int = 0
    skippedRows: int = 0
    timeframes: list[ImportedTimeframe] = field(default_factory=list)
    error: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_symbols(value: str | None) -> set[str] | None:
    if not value:
        return None
    symbols = {item.strip().upper() for item in value.split(",") if item.strip()}
    return symbols or None


def parse_timeframes(value: str) -> list[str]:
    requested = [item.strip() for item in value.split(",") if item.strip()]
    unknown = [item for item in requested if item not in TIMEFRAME_RULES]
    if unknown:
        raise ValueError(f"Unsupported timeframe(s): {', '.join(unknown)}")
    return requested


def pair_from_source(path: Path) -> tuple[str, str] | None:
    match = FILENAME_RE.match(path.name)
    if not match:
        return None
    symbol = match.group("symbol").upper()
    return symbol, f"{symbol}/USDT:USDT"


def freqtrade_filename(symbol: str, timeframe: str) -> str:
    return f"{symbol}_USDT_USDT-{timeframe}-futures.feather"


def discover_sources(source_dir: Path, symbols: set[str] | None, max_pairs: int | None) -> list[Path]:
    files: list[Path] = []
    for path in sorted(source_dir.glob("*_USDT_5m_from_*.csv")):
        parsed = pair_from_source(path)
        if not parsed:
            continue
        symbol, _ = parsed
        if symbols and symbol not in symbols:
            continue
        files.append(path)
        if max_pairs and len(files) >= max_pairs:
            break
    return files


def read_external_csv(path: Path) -> tuple[pd.DataFrame, int, int]:
    columns = {"timestamp", "open", "high", "low", "close", "vol", "confirm"}
    raw = pd.read_csv(path, usecols=lambda column: column in columns)
    source_rows = len(raw)
    if "confirm" in raw.columns:
        raw = raw[raw["confirm"].fillna(1).astype(int) == 1]
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime(raw["timestamp"], unit="ms", utc=True),
            "open": pd.to_numeric(raw["open"], errors="coerce"),
            "high": pd.to_numeric(raw["high"], errors="coerce"),
            "low": pd.to_numeric(raw["low"], errors="coerce"),
            "close": pd.to_numeric(raw["close"], errors="coerce"),
            "volume": pd.to_numeric(raw["vol"], errors="coerce"),
        }
    )
    frame = frame.dropna(subset=["date", "open", "high", "low", "close", "volume"])
    frame = frame.drop_duplicates(subset=["date"]).sort_values("date").reset_index(drop=True)
    skipped = source_rows - len(frame)
    return frame, source_rows, skipped


def resample_ohlcv(frame: pd.DataFrame, timeframe: str) -> pd.DataFrame:
    if timeframe == "5m":
        result = frame.copy()
    else:
        result = (
            frame.set_index("date")
            .resample(TIMEFRAME_RULES[timeframe], label="left", closed="left")
            .agg(
                {
                    "open": "first",
                    "high": "max",
                    "low": "min",
                    "close": "last",
                    "volume": "sum",
                }
            )
            .dropna(subset=["open", "high", "low", "close"])
            .reset_index()
        )
    result = result[["date", "open", "high", "low", "close", "volume"]].copy()
    result["date"] = pd.to_datetime(result["date"], utc=True).dt.floor("ms")
    return result.reset_index(drop=True)


def iso_or_none(value: object) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.Timestamp(value).isoformat()


def write_feather(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_feather(path)


def import_pair(path: Path, output_dir: Path, timeframes: Iterable[str], overwrite: bool) -> ImportedPair:
    parsed = pair_from_source(path)
    if not parsed:
        return ImportedPair(pair=path.stem, sourcePath=str(path), status="skipped", error="Unsupported filename")
    symbol, pair = parsed
    try:
        frame, source_rows, skipped = read_external_csv(path)
        if frame.empty:
            return ImportedPair(
                pair=pair,
                sourcePath=str(path),
                status="empty",
                sourceRows=source_rows,
                importedRows=0,
                skippedRows=skipped,
                error="No valid OHLCV rows after cleaning",
            )
        imported = ImportedPair(
            pair=pair,
            sourcePath=str(path),
            status="imported",
            sourceRows=source_rows,
            importedRows=len(frame),
            skippedRows=skipped,
        )
        for timeframe in timeframes:
            output_path = output_dir / freqtrade_filename(symbol, timeframe)
            if output_path.exists() and not overwrite:
                existing = pd.read_feather(output_path, columns=["date"])
                imported.timeframes.append(
                    ImportedTimeframe(
                        timeframe=timeframe,
                        rows=len(existing),
                        outputPath=str(output_path),
                        start=iso_or_none(existing["date"].min()) if not existing.empty else None,
                        end=iso_or_none(existing["date"].max()) if not existing.empty else None,
                    )
                )
                continue
            view = resample_ohlcv(frame, timeframe)
            write_feather(view, output_path)
            imported.timeframes.append(
                ImportedTimeframe(
                    timeframe=timeframe,
                    rows=len(view),
                    outputPath=str(output_path),
                    start=iso_or_none(view["date"].min()) if not view.empty else None,
                    end=iso_or_none(view["date"].max()) if not view.empty else None,
                )
            )
        return imported
    except Exception as exc:  # noqa: BLE001 - report per-pair import failures without aborting the whole run.
        return ImportedPair(pair=pair, sourcePath=str(path), status="failed", error=str(exc))


def build_report(imported: list[ImportedPair], source_dir: Path, output_dir: Path, timeframes: list[str]) -> dict[str, object]:
    return {
        "reportId": "external_5m_import_report",
        "source": "alphapilot_external_5m_csv_importer",
        "sourceDir": str(source_dir),
        "outputDir": str(output_dir),
        "timeframes": timeframes,
        "totalSources": len(imported),
        "importedCount": sum(1 for item in imported if item.status == "imported"),
        "failedCount": sum(1 for item in imported if item.status == "failed"),
        "emptyCount": sum(1 for item in imported if item.status == "empty"),
        "pairs": [asdict(item) for item in imported],
        "safetyBoundary": {
            "publicOrLocalOhlcvOnly": True,
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
    parser = argparse.ArgumentParser(description="Import external 5m OHLCV CSV data into Freqtrade feather files.")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR))
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR))
    parser.add_argument("--report-path", default=str(DEFAULT_REPORT_PATH))
    parser.add_argument("--timeframes", default="5m,15m,30m,1h,4h")
    parser.add_argument("--symbols", default="")
    parser.add_argument("--max-pairs", type=int, default=0)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)
    report_path = Path(args.report_path)
    timeframes = parse_timeframes(args.timeframes)
    symbols = parse_symbols(args.symbols)
    max_pairs = args.max_pairs if args.max_pairs and args.max_pairs > 0 else None
    if not source_dir.exists():
        raise SystemExit(f"Source directory not found: {source_dir}")
    sources = discover_sources(source_dir, symbols, max_pairs)
    imported = [import_pair(path, output_dir, timeframes, overwrite=args.overwrite) for path in sources]
    report = build_report(imported, source_dir, output_dir, timeframes)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("reportId", "totalSources", "importedCount", "failedCount", "emptyCount")}, ensure_ascii=False, indent=2))
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
