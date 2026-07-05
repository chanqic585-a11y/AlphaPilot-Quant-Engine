"""Market regime labeling for V13.4.27 research review.

The labeler reads local public OHLCV files only. It does not run backtests,
download data, call exchange APIs, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.factors.ohlcv_loader import discover_ohlcv_files, parse_timerange
from alphapilot.market_regime.market_regime_schema import (
    BtcSanityPoint,
    MarketBreadthSnapshot,
    MarketRegimeLabel,
    MarketRegimeReview,
)


def _read_ohlcv(path: Path) -> pd.DataFrame:
    suffixes = "".join(path.suffixes)
    if path.suffix == ".feather":
        return pd.read_feather(path)
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    if suffixes.endswith(".json.gz") or path.suffix == ".json":
        return pd.read_json(path)
    raise ValueError(f"unsupported_file_format:{path.name}")


def _prepare_frame(frame: pd.DataFrame, timerange: str | None = None) -> pd.DataFrame:
    output = frame.loc[:, ["date", "open", "high", "low", "close", "volume"]].copy()
    output["date"] = pd.to_datetime(output["date"], utc=True, errors="coerce")
    for column in ["open", "high", "low", "close", "volume"]:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    output = output.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date")
    output = output.drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)
    if timerange:
        start, end = parse_timerange(timerange)
        if start is not None:
            output = output[output["date"] >= start]
        if end is not None:
            output = output[output["date"] < end]
        output = output.reset_index(drop=True)
    return output


def _safe_pct(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value) * 100.0, 4)


def _safe_float(value: Any) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), 8)


def _iso(value: Any) -> str:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp.isoformat()


def _primary_label(labels: list[str]) -> str:
    for candidate in ["crash", "bear", "recovery", "bull", "high_volatility", "sideways"]:
        if candidate in labels:
            return candidate
    return "unknown"


def _label_btc_frame(frame: pd.DataFrame) -> list[MarketRegimeLabel]:
    if frame.empty:
        return []
    data = frame.copy()
    data["ema20"] = data["close"].ewm(span=20, adjust=False, min_periods=20).mean()
    data["ema50"] = data["close"].ewm(span=50, adjust=False, min_periods=50).mean()
    data["ema200"] = data["close"].ewm(span=200, adjust=False, min_periods=200).mean()
    returns = data["close"].pct_change()
    data["return3d"] = data["close"].pct_change(18)
    data["return7d"] = data["close"].pct_change(42)
    data["rollingVolatility"] = returns.rolling(42, min_periods=24).std()
    volatility_threshold = data["rollingVolatility"].quantile(0.80)

    labels: list[MarketRegimeLabel] = []
    for row in data.itertuples(index=False):
        row_labels: list[str] = []
        close = float(row.close)
        ema20 = getattr(row, "ema20")
        ema50 = getattr(row, "ema50")
        ema200 = getattr(row, "ema200")
        return3d = getattr(row, "return3d")
        return7d = getattr(row, "return7d")
        rolling_vol = getattr(row, "rollingVolatility")

        if pd.notna(ema20) and pd.notna(ema50) and pd.notna(ema200):
            if close > ema200 and ema20 > ema50:
                row_labels.append("bull")
            if close < ema200 and ema20 < ema50:
                row_labels.append("bear")
            if abs((ema20 / ema50) - 1.0) <= 0.01:
                row_labels.append("sideways")
        if pd.notna(rolling_vol) and pd.notna(volatility_threshold) and rolling_vol >= volatility_threshold:
            row_labels.append("high_volatility")
        if pd.notna(return3d) and return3d <= -0.10:
            row_labels.append("crash")
        if pd.notna(return7d) and return7d >= 0.10 and pd.notna(ema20) and close > ema20:
            row_labels.append("recovery")
        if not row_labels:
            row_labels.append("unknown")
        labels.append(
            MarketRegimeLabel(
                timestamp=_iso(row.date),
                close=round(close, 8),
                labels=sorted(set(row_labels)),
                primaryLabel=_primary_label(row_labels),
                ema20=_safe_float(ema20),
                ema50=_safe_float(ema50),
                ema200=_safe_float(ema200),
                return3dPct=_safe_pct(return3d),
                return7dPct=_safe_pct(return7d),
                rollingVolatilityPct=_safe_pct(rolling_vol),
            )
        )
    return labels


def _nearest_sanity_point(frame: pd.DataFrame, date_label: str) -> BtcSanityPoint:
    if frame.empty:
        return BtcSanityPoint(date_label, None, None, "BTC OHLCV frame is empty.")
    target = pd.Timestamp(date_label, tz="UTC")
    deltas = (frame["date"] - target).abs()
    nearest_index = deltas.idxmin()
    nearest = frame.loc[nearest_index]
    distance_days = float(deltas.loc[nearest_index] / pd.Timedelta(days=1))
    warning = None
    if distance_days > 31:
        warning = "No BTC candle within 31 days of requested checkpoint."
    close = float(nearest["close"])
    if close < 10000 or close > 300000:
        warning = "BTC close is outside broad sanity range; verify scale and instrument."
    return BtcSanityPoint(
        requestedDate=date_label,
        nearestTimestamp=_iso(nearest["date"]),
        close=round(close, 4),
        warning=warning,
    )


def _build_breadth_summary(data_path: str | Path, timerange: str) -> dict[str, Any]:
    discovered = discover_ohlcv_files(data_path, "1h")
    frames: list[pd.DataFrame] = []
    for pair, path in sorted(discovered.items()):
        try:
            frame = _prepare_frame(_read_ohlcv(path), timerange=timerange)
        except Exception:
            continue
        if frame.empty:
            continue
        frame = frame.loc[:, ["date", "close"]].copy()
        frame["pair"] = pair
        frame["return24h"] = frame["close"].pct_change(24)
        frame["ema50"] = frame["close"].ewm(span=50, adjust=False, min_periods=50).mean()
        frame["ema200"] = frame["close"].ewm(span=200, adjust=False, min_periods=200).mean()
        frames.append(frame)
    if not frames:
        return {
            "status": "unavailable",
            "source": "local_1h_ohlcv_breadth_proxy",
            "reason": "No readable 1h OHLCV files available.",
            "latestSnapshot": None,
            "snapshotCount": 0,
            "averagePositiveReturn24hPct": None,
            "averageAboveEma50Pct": None,
            "averageAboveEma200Pct": None,
        }
    panel = pd.concat(frames, ignore_index=True)
    snapshots: list[MarketBreadthSnapshot] = []
    for timestamp, group in panel.groupby("date", sort=True):
        valid_return = group["return24h"].dropna()
        valid_ema50 = group.dropna(subset=["ema50"])
        valid_ema200 = group.dropna(subset=["ema200"])
        snapshots.append(
            MarketBreadthSnapshot(
                timestamp=_iso(timestamp),
                pairCount=int(group["pair"].nunique()),
                positiveReturn24hPct=round(float((valid_return > 0).mean() * 100), 4) if not valid_return.empty else None,
                averageReturn24hPct=round(float(valid_return.mean() * 100), 4) if not valid_return.empty else None,
                medianReturn24hPct=round(float(valid_return.median() * 100), 4) if not valid_return.empty else None,
                aboveEma50Pct=round(float((valid_ema50["close"] > valid_ema50["ema50"]).mean() * 100), 4) if not valid_ema50.empty else None,
                aboveEma200Pct=round(float((valid_ema200["close"] > valid_ema200["ema200"]).mean() * 100), 4) if not valid_ema200.empty else None,
            )
        )
    latest = snapshots[-1].to_dict() if snapshots else None
    positive_values = [item.positiveReturn24hPct for item in snapshots if item.positiveReturn24hPct is not None]
    ema50_values = [item.aboveEma50Pct for item in snapshots if item.aboveEma50Pct is not None]
    ema200_values = [item.aboveEma200Pct for item in snapshots if item.aboveEma200Pct is not None]
    return {
        "status": "available",
        "source": "local_1h_ohlcv_breadth_proxy",
        "limitation": "Breadth is computed from locally available pairs, not from an exchange-wide historical universe snapshot.",
        "pairCount": int(panel["pair"].nunique()),
        "snapshotCount": len(snapshots),
        "latestSnapshot": latest,
        "averagePositiveReturn24hPct": round(float(pd.Series(positive_values).mean()), 4) if positive_values else None,
        "averageAboveEma50Pct": round(float(pd.Series(ema50_values).mean()), 4) if ema50_values else None,
        "averageAboveEma200Pct": round(float(pd.Series(ema200_values).mean()), 4) if ema200_values else None,
        "recentSnapshots": [item.to_dict() for item in snapshots[-20:]],
    }


def build_market_regime_review(
    data_path: str | Path = "user_data/data/okx/futures",
    timerange: str = "20260101-",
    btc_pair: str = "BTC/USDT:USDT",
) -> MarketRegimeReview:
    warnings: list[str] = []
    discovered_4h = discover_ohlcv_files(data_path, "4h")
    btc_path = discovered_4h.get(btc_pair)
    if btc_path is None:
        return MarketRegimeReview(
            status="blocked_no_btc_4h",
            timerange=timerange,
            btcPair=btc_pair,
            regimeDistribution={},
            dominantRegimes=[],
            btcSanityPoints=[],
            breadthSummary=_build_breadth_summary(data_path, timerange),
            labels=[],
            warnings=["Missing local BTC/USDT:USDT 4h futures OHLCV file."],
        )

    full_btc = _prepare_frame(_read_ohlcv(btc_path), timerange=None)
    btc = _prepare_frame(_read_ohlcv(btc_path), timerange=timerange)
    labels = _label_btc_frame(btc)
    distribution: Counter[str] = Counter()
    for label in labels:
        for item in label.labels:
            distribution[item] += 1
    sorted_distribution = dict(sorted(distribution.items(), key=lambda item: (-item[1], item[0])))
    dominant = [item for item, _ in list(sorted_distribution.items())[:3]]
    sanity_dates = ["2025-10-01", "2026-01-01", "2026-04-01", "2026-06-01", "2026-07-01"]
    sanity_points = [_nearest_sanity_point(full_btc, item) for item in sanity_dates]
    for point in sanity_points:
        if point.warning:
            warnings.append(f"BTC sanity warning for {point.requestedDate}: {point.warning}")
    if not labels:
        warnings.append("No BTC regime labels generated after timerange filtering.")

    return MarketRegimeReview(
        status="available" if labels else "empty",
        timerange=timerange,
        btcPair=btc_pair,
        regimeDistribution=sorted_distribution,
        dominantRegimes=dominant,
        btcSanityPoints=sanity_points,
        breadthSummary=_build_breadth_summary(data_path, timerange),
        labels=labels,
        warnings=warnings,
    )
