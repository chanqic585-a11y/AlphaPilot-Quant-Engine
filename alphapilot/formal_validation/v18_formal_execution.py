"""Pure V18 formal evidence, capital replay, and parity primitives."""

from __future__ import annotations

import math
from collections import Counter, defaultdict
from statistics import median
from typing import Any, Mapping, Sequence

import numpy as np
import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash

from .correlation_cluster_policy import build_correlation_clusters_v1
from .portfolio_beta_policy import estimate_portfolio_betas_v1
from .portfolio_event_engine import process_portfolio_timestamp_v2


def _utc_timestamp(value: object) -> pd.Timestamp:
    timestamp = pd.Timestamp(value)
    if timestamp.tzinfo is None:
        timestamp = timestamp.tz_localize("UTC")
    else:
        timestamp = timestamp.tz_convert("UTC")
    return timestamp


def _utc_iso(value: object) -> str:
    return _utc_timestamp(value).isoformat().replace("+00:00", "Z")


def _ordered(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    result["date"] = pd.to_datetime(result["date"], utc=True, errors="coerce")
    for column in ("open", "high", "low", "close", "volume"):
        result[column] = pd.to_numeric(result[column], errors="coerce")
    return (
        result.dropna(subset=["date", "open", "high", "low", "close", "volume"])
        .sort_values("date")
        .drop_duplicates("date", keep="last")
        .reset_index(drop=True)
    )


def build_daily_market_evidence(
    frames: Mapping[str, pd.DataFrame],
) -> tuple[
    dict[str, list[dict[str, Any]]],
    dict[str, list[dict[str, Any]]],
    dict[str, Any],
]:
    """Aggregate registered OKX volCcyQuote bars into causal UTC-day evidence."""

    daily_liquidity: dict[str, list[dict[str, Any]]] = {}
    return_panel: dict[str, list[dict[str, Any]]] = {}
    invalid_symbols: list[str] = []
    for symbol, raw in sorted(frames.items()):
        frame = _ordered(raw)
        if frame.empty or (frame["volume"] <= 0.0).any():
            invalid_symbols.append(str(symbol))
            daily_liquidity[str(symbol)] = []
            return_panel[str(symbol)] = []
            continue
        working = frame.set_index("date")
        daily = pd.DataFrame(
            {
                "quoteVolume": working["volume"].resample("1D").sum(min_count=1),
                "close": working["close"].resample("1D").last(),
            }
        ).dropna()
        daily = daily[daily["quoteVolume"] > 0.0]
        daily_liquidity[str(symbol)] = [
            {
                "timestamp": _utc_iso(index),
                "quoteVolume": float(row["quoteVolume"]),
                "close": float(row["close"]),
                "source": "registered_okx_vol_ccy_quote",
            }
            for index, row in daily.iterrows()
        ]
        returns = np.log(daily["close"] / daily["close"].shift(1)).dropna()
        return_panel[str(symbol)] = [
            {"timestamp": _utc_iso(index), "return": float(value)}
            for index, value in returns.items()
        ]
    audit = {
        "schemaVersion": "s01_v18_capacity_data_semantics_audit_v1",
        "status": "passed" if not invalid_symbols else "failed",
        "provider": "OKX public candles",
        "sourceField": "volume",
        "registeredMeaning": "okx_vol_ccy_quote",
        "aggregation": "sum_by_completed_utc_day",
        "estimatedQuoteVolume": False,
        "instrumentMetadataRequired": False,
        "instrumentCount": len(frames),
        "invalidSymbols": invalid_symbols,
        "lookaheadReadCount": 0,
    }
    return daily_liquidity, return_panel, audit


def _rolling_z(values: pd.Series, window: int) -> pd.Series:
    mean = values.rolling(window, min_periods=window).mean()
    standard = values.rolling(window, min_periods=window).std(ddof=0)
    return (values - mean) / standard.replace(0.0, np.nan)


def _market_close(frames: Mapping[str, pd.DataFrame]) -> pd.Series:
    panel = pd.concat(
        {
            symbol: _ordered(frame).set_index("date")["close"]
            for symbol, frame in frames.items()
            if not frame.empty
        },
        axis=1,
    ).sort_index()
    return panel.median(axis=1, skipna=True)


def _prior_liquidity_median(
    rows: Sequence[Mapping[str, Any]], entry_timestamp: object
) -> float | None:
    entry_day = _utc_timestamp(entry_timestamp).date()
    values = [
        float(row["quoteVolume"])
        for row in rows
        if _utc_timestamp(row["timestamp"]).date() < entry_day
        and math.isfinite(float(row["quoteVolume"]))
        and float(row["quoteVolume"]) > 0.0
    ][-30:]
    return float(median(values)) if len(values) >= 24 else None


def build_signal_feature_evidence(
    events: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
    candidate: Mapping[str, Any],
    *,
    include_source_bar_hashes: bool = False,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Rebuild exactly the frozen S01 ranking fields at each signal timestamp."""

    feature = dict(candidate.get("featureDefinition") or {})
    residual_window = int(feature["residualWindow"])
    recovery_bars = int(feature["recoveryBars"])
    ordered = {symbol: _ordered(frame) for symbol, frame in frames.items()}
    market_close = _market_close(ordered)
    daily_liquidity, _, semantics = build_daily_market_evidence(ordered)
    by_symbol: dict[str, pd.DataFrame] = {}
    for symbol, frame in ordered.items():
        market = market_close.reindex(pd.DatetimeIndex(frame["date"])).ffill().reset_index(
            drop=True
        )
        residual = frame["close"].pct_change() - market.pct_change()
        residual_z = _rolling_z(residual, residual_window)
        by_symbol[symbol] = pd.DataFrame(
            {"date": frame["date"], "residualZ": residual_z}
        )

    enriched: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for raw in events:
        row = dict(raw)
        symbol = str(row.get("symbol") or row.get("instrumentId") or "")
        evidence = by_symbol.get(symbol)
        extreme: float | None = None
        recovery: float | None = None
        liquidity = _prior_liquidity_median(
            daily_liquidity.get(symbol, []), row.get("entryTimestamp")
        )
        if evidence is not None:
            target = _utc_timestamp(row.get("signalTimestamp"))
            matches = evidence.index[evidence["date"] == target]
            if len(matches) == 1:
                position = int(matches[0])
                extreme_position = position - recovery_bars
                if extreme_position >= 0:
                    extreme_value = evidence.iloc[extreme_position]["residualZ"]
                    signal_value = evidence.iloc[position]["residualZ"]
                    if pd.notna(extreme_value) and pd.notna(signal_value):
                        extreme = float(extreme_value)
                        recovery = float(signal_value - extreme_value)
        values = {
            "eventExtremeResidualZ": extreme,
            "recoverySizeZ": recovery,
            "liquidity30d": liquidity,
        }
        source_bar_hashes: list[str] = []
        if include_source_bar_hashes:
            target = _utc_timestamp(row.get("signalTimestamp"))
            lookback = max(residual_window + recovery_bars + 2, 2)
            instrument_frame = ordered.get(symbol, pd.DataFrame())
            instrument_rows = (
                instrument_frame[instrument_frame["date"] <= target]
                .tail(lookback)[["date", "close", "volume"]]
                .to_dict("records")
                if not instrument_frame.empty
                else []
            )
            market_rows = [
                {
                    "instrumentId": instrument_id,
                    "rows": frame[frame["date"] <= target]
                    .tail(lookback)[["date", "close"]]
                    .to_dict("records"),
                }
                for instrument_id, frame in sorted(ordered.items())
            ]
            liquidity_rows = [
                item
                for item in daily_liquidity.get(symbol, [])
                if _utc_timestamp(item["timestamp"]) <= target
            ][-30:]
            source_bar_hashes = [
                "sha256:" + stable_hash(instrument_rows),
                "sha256:" + stable_hash(market_rows),
                "sha256:" + stable_hash(liquidity_rows),
            ]
        for field, value in values.items():
            if value is None or not math.isfinite(float(value)):
                missing.append(
                    {"signalId": str(row.get("signalId") or ""), "field": field}
                )
        enriched.append(
            {
                **row,
                **values,
                "instrumentId": symbol,
                "sourceTimestamp": _utc_iso(row.get("signalTimestamp")),
                "availableAt": _utc_iso(row.get("signalTimestamp")),
                "dailyLiquidity": daily_liquidity.get(symbol, []),
                "sourceBarHashes": source_bar_hashes,
                "lookaheadReadCount": 0,
            }
        )
    audit = {
        "schemaVersion": "s01_v18_signal_ranking_evidence_v1",
        "eventCount": len(events),
        "missingRankingFieldCount": len(missing),
        "missing": missing,
        "residualWindow": residual_window,
        "recoveryBars": recovery_bars,
        "liquidityLookbackCompletedUtcDays": 30,
        "liquidityMinimumCompletedUtcDays": 24,
        "capacityDataSemanticsStatus": semantics["status"],
        "lookaheadReadCount": 0,
    }
    return enriched, audit


def attach_point_in_time_context(
    events: Sequence[Mapping[str, Any]],
    return_panel: Mapping[str, Sequence[Mapping[str, Any]]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Attach frozen correlation clusters and BTC betas using prior UTC days only."""

    enriched: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    context_cache: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
    for raw in events:
        row = dict(raw)
        symbol = str(row.get("instrumentId") or row.get("symbol") or "")
        as_of = _utc_iso(row.get("entryTimestamp"))
        cache_key = _utc_timestamp(as_of).date().isoformat()
        if cache_key not in context_cache:
            context_cache[cache_key] = (
                build_correlation_clusters_v1(
                    return_panel,
                    as_of_timestamp=as_of,
                ),
                estimate_portfolio_betas_v1(
                    return_panel,
                    as_of_timestamp=as_of,
                ),
            )
        clusters, betas = context_cache[cache_key]
        cluster = clusters["assignments"].get(symbol)
        beta = betas["betas"].get(symbol)
        if cluster is None:
            missing.append({"signalId": str(row.get("signalId") or ""), "field": "correlationCluster"})
        if beta is None:
            missing.append({"signalId": str(row.get("signalId") or ""), "field": "beta"})
        enriched.append(
            {
                **row,
                "correlationCluster": cluster,
                "beta": float(beta) if beta is not None else None,
                "pointInTimeContextAsOf": as_of,
                "lookaheadReadCount": 0,
            }
        )
    return enriched, {
        "schemaVersion": "s01_v18_point_in_time_context_audit_v1",
        "eventCount": len(events),
        "evaluatedUtcDayCount": len(context_cache),
        "missingContextFieldCount": len(missing),
        "missing": missing,
        "strictlyPriorUtcDaysOnly": True,
        "lookaheadReadCount": 0,
    }


def _mark_price(frame: pd.DataFrame, timestamp: pd.Timestamp) -> float | None:
    matches = frame.index[frame["date"] == timestamp]
    return float(frame.iloc[int(matches[0])]["open"]) if len(matches) == 1 else None


def _decision(row: Mapping[str, Any], *, accepted: bool) -> dict[str, Any]:
    actual = row.get("actualNotional")
    return {
        "signalId": str(row.get("signalId") or ""),
        "instrumentId": str(row.get("instrumentId") or row.get("symbol") or ""),
        "accepted": accepted,
        "reason": None if accepted else str(row.get("reason") or "unknown"),
        "actualNotional": float(actual) if actual is not None else None,
        "riskAmount": (
            float(row["riskAmount"]) if row.get("riskAmount") is not None else None
        ),
    }


def replay_v18_capital_policy(
    events: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
    *,
    policy: Mapping[str, Any],
    capture_pit_context: bool = False,
) -> dict[str, Any]:
    """Replay one frozen event stream through the canonical V18 portfolio engine."""

    ordered = {symbol: _ordered(frame) for symbol, frame in frames.items()}
    by_entry: dict[pd.Timestamp, list[dict[str, Any]]] = defaultdict(list)
    by_exit: dict[pd.Timestamp, list[dict[str, Any]]] = defaultdict(list)
    event_by_signal: dict[str, dict[str, Any]] = {}
    for raw in events:
        event = dict(raw)
        signal_id = str(event["signalId"])
        event_by_signal[signal_id] = event
        by_entry[_utc_timestamp(event["entryTimestamp"])].append(event)
        for leg in event.get("exitLegs", []):
            by_exit[_utc_timestamp(leg["executionTimestamp"])].append(
                {**dict(leg), "signalId": signal_id, "instrumentId": event["instrumentId"]}
            )

    timeline = sorted(
        {
            *(_utc_timestamp(value) for frame in ordered.values() for value in frame["date"]),
            *by_entry.keys(),
            *by_exit.keys(),
        }
    )
    equity = float(policy["initial_capital"])
    positions: list[dict[str, Any]] = []
    accepted_entries: dict[str, dict[str, Any]] = {}
    decisions: list[dict[str, Any]] = []
    closed_legs: list[dict[str, Any]] = []
    ignored_exit_legs: list[dict[str, Any]] = []
    equity_curve: list[dict[str, Any]] = [
        {"timestamp": None, "equity": equity, "positionCount": 0}
    ]
    trade_pnl: dict[str, dict[str, float]] = defaultdict(
        lambda: {"grossPnl": 0.0, "netPnl": 0.0}
    )
    maximum_position_count = 0
    maximum_open_risk = 0.0
    maximum_cluster_risk = 0.0
    maximum_projected_beta = 0.0
    pit_contexts: list[dict[str, Any]] = []

    for timestamp in timeline:
        exit_rows: list[dict[str, Any]] = []
        exit_fraction_by_signal: dict[str, float] = defaultdict(float)
        for leg in by_exit.get(timestamp, []):
            signal_id = str(leg["signalId"])
            position = next(
                (row for row in positions if str(row.get("signalId")) == signal_id),
                None,
            )
            if position is None:
                if signal_id not in accepted_entries:
                    ignored_exit_legs.append(
                        {
                            "signalId": signal_id,
                            "executionTimestamp": _utc_iso(timestamp),
                            "reason": "entry_not_accepted",
                        }
                    )
                    continue
                raise ValueError(f"Exit leg has no accepted open position: {signal_id}")
            initial_risk = float(position["initialRiskAmount"])
            net_pnl = initial_risk * float(leg["netR"])
            gross_pnl = initial_risk * float(leg.get("grossR") or leg["netR"])
            exit_rows.append(
                {
                    **leg,
                    "netPnl": net_pnl,
                    "grossPnl": gross_pnl,
                }
            )
            exit_fraction_by_signal[signal_id] += float(leg["legFraction"])
            trade_pnl[signal_id]["netPnl"] += net_pnl
            trade_pnl[signal_id]["grossPnl"] += gross_pnl

        marks: list[dict[str, Any]] = []
        for position in positions:
            signal_id = str(position.get("signalId"))
            remaining_before = float(position.get("remainingFraction", 1.0))
            remaining_after = remaining_before - exit_fraction_by_signal.get(signal_id, 0.0)
            if remaining_after <= 1e-12:
                continue
            symbol = str(position["instrumentId"])
            price = _mark_price(ordered[symbol], timestamp)
            if price is None:
                continue
            scale = remaining_after / remaining_before
            quantity = float(position["quantity"]) * scale
            direction_sign = 1.0 if str(position["direction"]) == "long" else -1.0
            unrealized = direction_sign * (price - float(position["entryPrice"])) * quantity
            marks.append(
                {
                    "instrumentId": symbol,
                    "markNotional": abs(price * quantity),
                    "unrealizedPnl": unrealized,
                }
            )

        entries = []
        for raw in by_entry.get(timestamp, []):
            entries.append(
                {
                    **raw,
                    "entryTimestamp": _utc_iso(timestamp),
                    "entryPrice": float(raw["entryPrice"]),
                    "stopPrice": float(raw.get("stopPrice") or raw["initialStop"]),
                }
            )
        if capture_pit_context and entries:
            preview = process_portfolio_timestamp_v2(
                timestamp=_utc_iso(timestamp),
                current_equity=equity,
                open_positions=positions,
                exits=exit_rows,
                funding=[],
                marks=marks,
                entry_signals=[],
                policy=policy,
            )
            preview_equity = float(preview["currentEquity"])
            preview_positions = sorted(
                (dict(row) for row in preview["openPositions"]),
                key=lambda row: (
                    str(row.get("instrumentId") or ""),
                    str(row.get("signalId") or ""),
                ),
            )
            open_risk_amount = sum(
                float(row.get("riskAmount") or 0.0) for row in preview_positions
            )
            cluster_risk_amount: dict[str, float] = defaultdict(float)
            portfolio_beta = 0.0
            for position in preview_positions:
                cluster_risk_amount[str(position.get("correlationCluster") or "")] += (
                    float(position.get("riskAmount") or 0.0)
                )
                direction_sign = (
                    1.0 if str(position.get("direction") or "") == "long" else -1.0
                )
                portfolio_beta += (
                    direction_sign
                    * float(position.get("markNotional") or 0.0)
                    / preview_equity
                    * float(position.get("beta") or 0.0)
                )
            for entry in entries:
                direction = str(entry.get("direction") or "")
                same_direction_risk = sum(
                    float(row.get("riskAmount") or 0.0)
                    for row in preview_positions
                    if str(row.get("direction") or "") == direction
                )
                symbol = str(entry.get("instrumentId") or entry.get("symbol") or "")
                pit_contexts.append(
                    {
                        "signalId": str(entry.get("signalId") or ""),
                        "contextTimestamp": _utc_iso(timestamp),
                        "currentEquity": preview_equity,
                        "openPositions": preview_positions,
                        "openRiskR": open_risk_amount / preview_equity,
                        "sameDirectionRiskR": same_direction_risk / preview_equity,
                        "clusterRiskByCluster": {
                            key: value / preview_equity
                            for key, value in sorted(cluster_risk_amount.items())
                        },
                        "portfolioBeta": portfolio_beta,
                        "concurrentPositionCount": len(preview_positions),
                        "symbolAlreadyOpen": any(
                            str(row.get("instrumentId") or "") == symbol
                            for row in preview_positions
                        ),
                        "clusterMembership": entry.get("correlationCluster"),
                        "assetBeta": entry.get("beta"),
                        "capacityInputs": {
                            "currentEquity": preview_equity,
                            "entryPrice": entry.get("entryPrice"),
                            "stopPrice": entry.get("stopPrice"),
                            "dailyLiquidity": entry.get("dailyLiquidity"),
                            "instrumentMeta": entry.get("instrumentMeta") or {},
                        },
                    }
                )
        result = process_portfolio_timestamp_v2(
            timestamp=_utc_iso(timestamp),
            current_equity=equity,
            open_positions=positions,
            exits=exit_rows,
            funding=[],
            marks=marks,
            entry_signals=entries,
            policy=policy,
        )
        equity = float(result["currentEquity"])
        positions = [dict(row) for row in result["openPositions"]]
        for accepted in result["acceptedEntries"]:
            signal_id = str(accepted["signalId"])
            canonical = next(
                row for row in positions if str(row.get("signalId")) == signal_id
            )
            canonical.update(
                {
                    "remainingFraction": 1.0,
                    "initialRiskAmount": float(accepted["riskAmount"]),
                    "initialQuantity": float(accepted["quantity"]),
                    "entryPrice": float(accepted["entryPrice"]),
                    "unrealizedPnl": 0.0,
                }
            )
            accepted_entries[signal_id] = dict(canonical)
            decisions.append(_decision(canonical, accepted=True))
            maximum_projected_beta = max(
                maximum_projected_beta,
                abs(float(accepted["projectedPortfolioBeta"])),
            )
        decisions.extend(
            _decision(row, accepted=False) for row in result["rejectedEntries"]
        )
        closed_legs.extend(dict(row) for row in result["closedPositions"])
        maximum_position_count = max(maximum_position_count, len(positions))
        open_risk = sum(float(row["riskAmount"]) for row in positions)
        maximum_open_risk = max(maximum_open_risk, open_risk)
        cluster_totals: dict[str, float] = defaultdict(float)
        for position in positions:
            cluster_totals[str(position["correlationCluster"])] += float(
                position["riskAmount"]
            )
        maximum_cluster_risk = max(
            maximum_cluster_risk, max(cluster_totals.values(), default=0.0)
        )
        if entries or exit_rows or marks:
            equity_curve.append(
                {
                    "timestamp": _utc_iso(timestamp),
                    "equity": equity,
                    "positionCount": len(positions),
                    "openRisk": open_risk,
                }
            )

    trades: list[dict[str, Any]] = []
    for signal_id, accepted in sorted(accepted_entries.items()):
        source = event_by_signal[signal_id]
        pnl = trade_pnl[signal_id]
        trades.append(
            {
                **accepted,
                "foldId": source.get("foldId"),
                "exitTimestamp": source["exitLegs"][-1]["executionTimestamp"],
                "realizedGrossR": sum(
                    float(leg.get("grossR") or 0.0) for leg in source["exitLegs"]
                ),
                "realizedNetR": sum(float(leg["netR"]) for leg in source["exitLegs"]),
                **pnl,
            }
        )
    rejection_counts = Counter(
        str(row["reason"]) for row in decisions if not bool(row["accepted"])
    )
    replay = {
        "schemaVersion": "s01_v18_formal_capital_replay_v1",
        "initialEquity": float(policy["initial_capital"]),
        "finalEquity": equity,
        "rawSignalCount": len(events),
        "acceptedSignalCount": len(accepted_entries),
        "rejectedSignalCount": len(events) - len(accepted_entries),
        "decisions": decisions,
        "trades": trades,
        "closedLegs": closed_legs,
        "ignoredExitLegs": ignored_exit_legs,
        "openPositions": positions,
        "equityCurve": equity_curve,
        "rejectionBreakdown": dict(sorted(rejection_counts.items())),
        "maximumConcurrentPositions": maximum_position_count,
        "maximumOpenRiskAmount": maximum_open_risk,
        "maximumClusterRiskAmount": maximum_cluster_risk,
        "maximumAbsoluteProjectedBeta": maximum_projected_beta,
        "lookaheadReadCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    if capture_pit_context:
        replay["pitContexts"] = pit_contexts
    return replay


def _maximum_drawdown_percent(equity_curve: Sequence[Mapping[str, Any]]) -> float:
    peak: float | None = None
    maximum = 0.0
    for row in equity_curve:
        value = float(row["equity"])
        peak = value if peak is None else max(peak, value)
        if peak > 0.0:
            maximum = max(maximum, (peak - value) / peak * 100.0)
    return maximum


def summarize_capital_replay(replay: Mapping[str, Any]) -> dict[str, Any]:
    """Summarize one V18 capital replay without changing accepted identities."""

    trades = [dict(row) for row in replay.get("trades", [])]
    pnls = [float(row.get("netPnl") or 0.0) for row in trades]
    net_rs = [float(row.get("realizedNetR") or 0.0) for row in trades]
    positive = sum(value for value in pnls if value > 0.0)
    negative = abs(sum(value for value in pnls if value < 0.0))
    by_symbol: dict[str, float] = defaultdict(float)
    by_month: dict[str, float] = defaultdict(float)
    for row in trades:
        contribution = max(0.0, float(row.get("netPnl") or 0.0))
        by_symbol[str(row.get("instrumentId") or row.get("symbol") or "")] += contribution
        month = _utc_timestamp(row["exitTimestamp"]).strftime("%Y-%m")
        by_month[month] += contribution
    denominator = positive if positive > 0.0 else 1.0
    initial = float(replay.get("initialEquity") or 0.0)
    final = float(replay.get("finalEquity") or initial)
    return {
        "schemaVersion": "s01_v18_formal_portfolio_metrics_v1",
        "tradeCount": len(trades),
        "winCount": sum(value > 0.0 for value in pnls),
        "lossCount": sum(value < 0.0 for value in pnls),
        "profitFactor": positive / negative if negative > 0.0 else None,
        "profitFactorStatus": "defined" if negative > 0.0 else "undefined_no_losses",
        "averageNetR": sum(net_rs) / len(net_rs) if net_rs else 0.0,
        "totalNetR": sum(net_rs),
        "netPnl": final - initial,
        "netReturnPercent": ((final / initial) - 1.0) * 100.0 if initial else 0.0,
        "maximumDrawdownPercent": _maximum_drawdown_percent(
            replay.get("equityCurve", [])
        ),
        "maximumSingleSymbolPositiveContribution": max(
            by_symbol.values(), default=0.0
        )
        / denominator,
        "maximumSingleMonthPositiveContribution": max(
            by_month.values(), default=0.0
        )
        / denominator,
        "positiveContributionBySymbol": dict(sorted(by_symbol.items())),
        "positiveContributionByMonth": dict(sorted(by_month.items())),
    }


def _event_cost_r(event: Mapping[str, Any]) -> tuple[float, float]:
    gross = 0.0
    net = 0.0
    explicit_cost = 0.0
    has_explicit_cost = False
    for leg in event.get("exitLegs", []):
        gross += float(leg.get("grossR") or 0.0)
        net += float(leg.get("netR") or 0.0)
        for field in ("feesR", "slippageR", "spreadProxyR"):
            if leg.get(field) is not None:
                explicit_cost += float(leg.get(field) or 0.0)
                has_explicit_cost = True
    return gross, explicit_cost if has_explicit_cost else max(0.0, gross - net)


def build_locked_cost_stress(
    base_replay: Mapping[str, Any],
    events: Sequence[Mapping[str, Any]],
    cost_model: Mapping[str, Any],
) -> dict[str, Any]:
    """Reprice only the base-accepted trades while freezing identity and size."""

    source = {str(row["signalId"]): dict(row) for row in events}
    base_trades = [dict(row) for row in base_replay.get("trades", [])]
    accepted_ids = [str(row["signalId"]) for row in base_trades]
    scenarios: list[dict[str, Any]] = []
    for scenario in cost_model.get("scenarios", []):
        multiplier = float(scenario["multiplier"])
        trades: list[dict[str, Any]] = []
        for base in base_trades:
            event = source[str(base["signalId"])]
            gross_r, base_cost_r = _event_cost_r(event)
            net_r = gross_r - base_cost_r * multiplier
            risk = float(base["riskAmount"])
            trades.append(
                {
                    **base,
                    "realizedGrossR": gross_r,
                    "realizedNetR": net_r,
                    "grossPnl": risk * gross_r,
                    "netPnl": risk * net_r,
                    "baseNonFundingCostR": base_cost_r,
                    "scenarioCostR": base_cost_r * multiplier,
                }
            )
        equity = float(base_replay["initialEquity"])
        curve: list[dict[str, Any]] = [
            {"timestamp": None, "equity": equity, "positionCount": 0}
        ]
        for row in sorted(
            trades,
            key=lambda value: (
                _utc_timestamp(value["exitTimestamp"]),
                str(value["signalId"]),
            ),
        ):
            equity += float(row["netPnl"])
            curve.append(
                {
                    "timestamp": _utc_iso(row["exitTimestamp"]),
                    "equity": equity,
                    "positionCount": 0,
                }
            )
        scenario_replay = {
            "initialEquity": float(base_replay["initialEquity"]),
            "finalEquity": equity,
            "trades": trades,
            "equityCurve": curve,
        }
        scenarios.append(
            {
                "scenarioId": str(scenario["scenarioId"]),
                "multiplier": multiplier,
                "acceptedSignalIds": list(accepted_ids),
                "metrics": summarize_capital_replay(scenario_replay),
                "trades": trades,
            }
        )
    return {
        "schemaVersion": "s01_v18_locked_cost_stress_v1",
        "selectionFrozenFrom": "base",
        "baseAcceptedSignalIds": accepted_ids,
        "selectionIdentityStable": all(
            row["acceptedSignalIds"] == accepted_ids for row in scenarios
        ),
        "scenarios": scenarios,
    }


def compare_capital_replays(
    reference: Mapping[str, Any], implementation: Mapping[str, Any]
) -> dict[str, Any]:
    """Compare exact capital decisions and accepted research notionals."""

    reference_rows = {
        str(row["signalId"]): dict(row) for row in reference.get("decisions", [])
    }
    implementation_rows = {
        str(row["signalId"]): dict(row)
        for row in implementation.get("decisions", [])
    }
    identities = sorted(set(reference_rows) | set(implementation_rows))
    acceptance_matches = 0
    size_matches = 0
    accepted_denominator = 0
    mismatches: list[dict[str, Any]] = []
    for signal_id in identities:
        left = reference_rows.get(signal_id)
        right = implementation_rows.get(signal_id)
        acceptance_match = bool(
            left is not None
            and right is not None
            and left.get("accepted") == right.get("accepted")
            and left.get("reason") == right.get("reason")
        )
        if acceptance_match:
            acceptance_matches += 1
        if left and right and left.get("accepted") and right.get("accepted"):
            accepted_denominator += 1
            left_notional = float(left["actualNotional"])
            right_notional = float(right["actualNotional"])
            if math.isclose(left_notional, right_notional, rel_tol=1e-9, abs_tol=1e-9):
                size_matches += 1
            else:
                mismatches.append(
                    {"signalId": signal_id, "reason": "position_size_mismatch"}
                )
        if not acceptance_match:
            mismatches.append(
                {"signalId": signal_id, "reason": "capital_acceptance_mismatch"}
            )
    acceptance_pct = (
        acceptance_matches / len(identities) * 100.0 if identities else 100.0
    )
    size_pct = (
        size_matches / accepted_denominator * 100.0
        if accepted_denominator
        else 100.0
    )
    blockers: list[str] = []
    if acceptance_pct != 100.0:
        blockers.append("capital_acceptance_mismatch")
    if size_pct != 100.0:
        blockers.append("position_size_mismatch")
    return {
        "schemaVersion": "s01_v18_capital_policy_parity_v1",
        "status": "passed" if not blockers else "failed",
        "passed": not blockers,
        "referenceDecisionCount": len(reference_rows),
        "implementationDecisionCount": len(implementation_rows),
        "capitalAcceptanceParityPct": acceptance_pct,
        "positionSizeParityPct": size_pct,
        "blockers": blockers,
        "mismatches": mismatches,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
