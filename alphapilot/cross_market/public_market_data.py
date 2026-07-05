"""Public cross-market data smoke collector.

This module fetches public OHLCV research data from Yahoo Finance chart
endpoints. It stores only optional local raw cache files and committed aggregate
quality reports. It does not use broker credentials, read accounts, create
orders, or auto trade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time
from pathlib import Path
from statistics import mean, pstdev
from typing import Any
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import json
import math


YAHOO_CHART_BASE = "https://query1.finance.yahoo.com/v8/finance/chart"


@dataclass(frozen=True)
class CrossMarketSymbol:
    symbol: str
    display_name: str
    market: str
    asset_type: str
    currency: str
    data_source: str = "yahoo_finance_chart_public"


DEFAULT_CROSS_MARKET_SYMBOLS = [
    CrossMarketSymbol("600519.SS", "Kweichow Moutai", "cn_a_share", "stock", "CNY"),
    CrossMarketSymbol("000001.SZ", "Ping An Bank", "cn_a_share", "stock", "CNY"),
    CrossMarketSymbol("0700.HK", "Tencent", "hk_stock", "stock", "HKD"),
    CrossMarketSymbol("9988.HK", "Alibaba HK", "hk_stock", "stock", "HKD"),
    CrossMarketSymbol("SPY", "SPDR S&P 500 ETF", "us_etf", "etf", "USD"),
    CrossMarketSymbol("QQQ", "Invesco QQQ ETF", "us_etf", "etf", "USD"),
    CrossMarketSymbol("^HSI", "Hang Seng Index", "index", "index", "HKD"),
    CrossMarketSymbol("^GSPC", "S&P 500 Index", "index", "index", "USD"),
]


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def date_to_unix_seconds(value: date) -> int:
    return int(datetime.combine(value, time.min, tzinfo=UTC).timestamp())


def _round(value: float | None, digits: int = 6) -> float | None:
    if value is None or not math.isfinite(value):
        return None
    return round(float(value), digits)


def fetch_yahoo_chart(symbol: str, start_date: date, end_date: date, interval: str = "1d") -> dict[str, Any]:
    period1 = date_to_unix_seconds(start_date)
    period2 = date_to_unix_seconds(end_date)
    encoded = quote(symbol, safe="")
    url = (
        f"{YAHOO_CHART_BASE}/{encoded}"
        f"?period1={period1}&period2={period2}&interval={interval}&events=history"
    )
    request = Request(url, headers={"User-Agent": "AlphaPilotResearch/13.5.11"})
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (OSError, URLError, json.JSONDecodeError) as exc:
        return {"symbol": symbol, "error": str(exc), "url": url}
    return {"symbol": symbol, "url": url, "payload": payload}


def parse_chart_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    payload = raw.get("payload") or {}
    chart = payload.get("chart") or {}
    results = chart.get("result") or []
    if not results:
        return []
    result = results[0]
    timestamps = result.get("timestamp") or []
    quote_data = ((result.get("indicators") or {}).get("quote") or [{}])[0]
    rows: list[dict[str, Any]] = []
    for index, timestamp in enumerate(timestamps):
        row_date = datetime.fromtimestamp(timestamp, UTC).date().isoformat()
        row = {"date": row_date}
        for field in ["open", "high", "low", "close", "volume"]:
            values = quote_data.get(field) or []
            row[field] = values[index] if index < len(values) else None
        rows.append(row)
    return rows


def _daily_returns(rows: list[dict[str, Any]]) -> list[float]:
    returns: list[float] = []
    previous_close: float | None = None
    for row in rows:
        close = row.get("close")
        if close is None:
            continue
        close_float = float(close)
        if previous_close is not None and previous_close > 0:
            returns.append((close_float / previous_close) - 1)
        previous_close = close_float
    return returns


def _max_drawdown_pct(rows: list[dict[str, Any]]) -> float | None:
    peak: float | None = None
    max_drawdown = 0.0
    for row in rows:
        close = row.get("close")
        if close is None:
            continue
        value = float(close)
        if peak is None or value > peak:
            peak = value
        if peak and peak > 0:
            drawdown = (peak - value) / peak
            max_drawdown = max(max_drawdown, drawdown)
    return max_drawdown * 100


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {
            "rowCount": 0,
            "startDate": None,
            "endDate": None,
            "missingOhlcvRows": 0,
            "dataQualityScore": 0,
        }
    missing = 0
    for row in rows:
        if any(row.get(field) is None for field in ["open", "high", "low", "close", "volume"]):
            missing += 1
    returns = _daily_returns(rows)
    quality_score = 100
    if len(rows) < 200:
        quality_score -= 25
    if missing:
        quality_score -= min(40, missing)
    if not returns:
        quality_score -= 25
    quality_score = max(0, min(100, quality_score))
    return {
        "rowCount": len(rows),
        "startDate": rows[0]["date"],
        "endDate": rows[-1]["date"],
        "missingOhlcvRows": missing,
        "returnMeanDailyPct": _round(mean(returns) * 100 if returns else None),
        "returnVolDailyPct": _round(pstdev(returns) * 100 if len(returns) > 1 else None),
        "maxDrawdownPct": _round(_max_drawdown_pct(rows)),
        "dataQualityScore": quality_score,
    }


def collect_cross_market_smoke(
    *,
    symbols: list[CrossMarketSymbol] | None = None,
    start_date: date,
    end_date: date,
    interval: str = "1d",
    raw_cache_dir: Path | None = None,
) -> dict[str, Any]:
    symbols = symbols or DEFAULT_CROSS_MARKET_SYMBOLS
    generated_at = utc_now()
    results: list[dict[str, Any]] = []
    total_rows = 0
    success_count = 0
    failure_count = 0
    for item in symbols:
        raw = fetch_yahoo_chart(item.symbol, start_date, end_date, interval)
        rows = parse_chart_rows(raw)
        summary = summarize_rows(rows)
        error = raw.get("error")
        if rows and not error:
            success_count += 1
            total_rows += len(rows)
        else:
            failure_count += 1
        if raw_cache_dir and rows:
            raw_cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path = raw_cache_dir / f"{item.symbol.replace('/', '_').replace('^', 'INDEX_')}_{interval}.json"
            cache_path.write_text(json.dumps({"metadata": asdict(item), "rows": rows}, ensure_ascii=False), encoding="utf-8")
        results.append(
            {
                "metadata": asdict(item),
                "interval": interval,
                "status": "ok" if rows and not error else "failed",
                "error": error,
                "sourceUrl": raw.get("url"),
                "summary": summary,
                "rawDataCommittedToGit": False,
            }
        )
    return {
        "version": "V13.5.11",
        "reportId": "v13_5_11_cross_market_public_data_smoke_report",
        "generatedAt": generated_at,
        "status": "completed" if failure_count == 0 else "completed_with_warnings",
        "objective": (
            "Build a cross-market public data smoke sample for research only, "
            "covering crypto-adjacent equity/index references without execution authority."
        ),
        "dataSource": {
            "name": "Yahoo Finance public chart endpoint",
            "url": YAHOO_CHART_BASE,
            "requiresApiKey": False,
            "rawCacheCommittedToGit": False,
            "note": "Use as public research data smoke only; verify data source terms before production redistribution.",
        },
        "requestedRange": {
            "startDate": start_date.isoformat(),
            "endDate": end_date.isoformat(),
            "interval": interval,
        },
        "summary": {
            "symbolCount": len(symbols),
            "successCount": success_count,
            "failureCount": failure_count,
            "totalRows": total_rows,
            "markets": sorted({item.market for item in symbols}),
        },
        "symbols": results,
        "integrationBoundary": {
            "crossMarketResearchOnly": True,
            "usedForCryptoExecution": False,
            "normalizationRequiredBeforeModelUse": True,
            "requiresSeparateValidation": True,
        },
        "safetyBoundary": {
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "readsRealAccount": False,
            "readsRealPositions": False,
            "createsOrders": False,
            "autoTrading": False,
            "exchangeDryRunApproved": False,
            "liveTradingApproved": False,
        },
    }
