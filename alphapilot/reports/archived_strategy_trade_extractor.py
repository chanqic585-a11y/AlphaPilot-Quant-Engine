"""Extract compact, auditable trade rows from Freqtrade result archives."""

from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path
from typing import Any


def read_freqtrade_strategy_result(
    archive_path: Path | str, strategy_name: str
) -> dict[str, Any]:
    path = Path(archive_path)
    with zipfile.ZipFile(path) as archive:
        candidates = [
            item
            for item in archive.infolist()
            if item.filename.endswith(".json") and "config" not in item.filename.lower()
        ]
        if not candidates:
            return {}
        payload = json.loads(archive.read(candidates[0]))
    strategies = payload.get("strategy") or {}
    result = strategies.get(strategy_name)
    return result if isinstance(result, dict) else {}


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _trade_r_values(trade: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    open_rate = _number(trade.get("open_rate"))
    stop_rate = _number(trade.get("initial_stop_loss_abs"))
    min_rate = _number(trade.get("min_rate"))
    max_rate = _number(trade.get("max_rate"))
    profit_ratio = _number(trade.get("profit_ratio"))
    leverage = _number(trade.get("leverage")) or 1.0
    if open_rate is None or stop_rate is None or open_rate == 0:
        return None, None, None
    risk_price = abs(open_rate - stop_rate)
    if risk_price == 0:
        return None, None, None
    risk_ratio = risk_price / open_rate * leverage
    net_r = _safe_ratio(profit_ratio, risk_ratio)
    if trade.get("is_short"):
        mfe = _safe_ratio(open_rate - min_rate, risk_price) if min_rate is not None else None
        mae = _safe_ratio(open_rate - max_rate, risk_price) if max_rate is not None else None
    else:
        mfe = _safe_ratio(max_rate - open_rate, risk_price) if max_rate is not None else None
        mae = _safe_ratio(min_rate - open_rate, risk_price) if min_rate is not None else None
    return net_r, mfe, mae


def _estimated_fee(trade: dict[str, Any]) -> float | None:
    stake = _number(trade.get("stake_amount"))
    fee_open = _number(trade.get("fee_open"))
    fee_close = _number(trade.get("fee_close"))
    if stake is None or fee_open is None or fee_close is None:
        return None
    return stake * (fee_open + fee_close)


def extract_freqtrade_trades(
    archive_path: Path | str, strategy_name: str, artifact_id: str
) -> list[dict[str, Any]]:
    """Return compact trade rows; derived R values are explicitly approximate."""

    strategy = read_freqtrade_strategy_result(archive_path, strategy_name)
    rows = []
    for index, trade in enumerate(strategy.get("trades") or []):
        if not isinstance(trade, dict):
            continue
        net_r, mfe_r, mae_r = _trade_r_values(trade)
        identity = f"{artifact_id}:{strategy_name}:{index}:{trade.get('pair')}:{trade.get('open_date')}"
        rows.append(
            {
                "tradeId": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                "artifactId": artifact_id,
                "strategyName": strategy_name,
                "pair": trade.get("pair"),
                "direction": "short" if trade.get("is_short") else "long",
                "openAt": trade.get("open_date"),
                "closeAt": trade.get("close_date"),
                "openRate": _number(trade.get("open_rate")),
                "closeRate": _number(trade.get("close_rate")),
                "minRate": _number(trade.get("min_rate")),
                "maxRate": _number(trade.get("max_rate")),
                "profitRatio": _number(trade.get("profit_ratio")),
                "profitAbs": _number(trade.get("profit_abs")),
                "durationMinutes": _number(trade.get("trade_duration")),
                "netRApprox": round(net_r, 8) if net_r is not None else None,
                "mfeRApprox": round(mfe_r, 8) if mfe_r is not None else None,
                "maeRApprox": round(mae_r, 8) if mae_r is not None else None,
                "initialStopRate": _number(trade.get("initial_stop_loss_abs")),
                "leverage": _number(trade.get("leverage")),
                "feeCostEstimate": _estimated_fee(trade),
                "fundingFees": _number(trade.get("funding_fees")),
                "slippageCost": None,
                "enterTag": trade.get("enter_tag"),
                "exitReason": trade.get("exit_reason"),
                "weekday": trade.get("open_date") or trade.get("weekday"),
                "marketRegime": None,
                "derivationNotes": [
                    "netRApprox uses Freqtrade net profit ratio divided by initial price-stop risk adjusted by leverage.",
                    "MFE/MAE use recorded min/max rates and do not reconstruct intrabar path.",
                ],
            }
        )
    return rows
