"""Candidate-neutral canonical event contract used by formal validation."""

from __future__ import annotations

from typing import Any, Mapping


def _signal_id(candidate_id: str, symbol: str, timestamp: str) -> str:
    return f"{candidate_id}::formal::{symbol}::{timestamp}"


def canonicalize_formal_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Map an internal replay event to the strict formal parity contract."""

    legs: list[dict[str, Any]] = []
    for leg_index, raw_leg in enumerate(event.get("legs") or event.get("exitLegs") or []):
        leg = dict(raw_leg)
        legs.append(
            {
                "legIndex": int(leg.get("legIndex", leg_index)),
                "legFraction": float(leg.get("legFraction", leg.get("fraction"))),
                "exitReason": str(leg.get("exitReason", leg.get("reason"))),
                "triggerTimestamp": str(leg["triggerTimestamp"]),
                "executionTimestamp": str(leg["executionTimestamp"]),
                "price": float(leg["price"]),
                "grossR": float(leg["grossR"]),
                "feesR": float(leg["feesR"]),
                "slippageR": float(leg["slippageR"]),
                "spreadProxyR": float(leg["spreadProxyR"]),
                "fundingR": float(leg.get("fundingR") or 0.0),
                "netR": float(leg["netR"]),
                "isGapFill": bool(leg["isGapFill"]),
                "ambiguousPath": bool(leg["ambiguousPath"]),
            }
        )
    candidate_id = str(event["candidateId"])
    signal_timestamp = str(event["signalTimestamp"])
    symbol = str(event["symbol"])
    initial_stop = event.get("initialStop", event.get("initialStopPrice"))
    return {
        "candidateId": candidate_id,
        "signalId": str(
            event.get("signalId")
            or _signal_id(candidate_id, symbol, signal_timestamp)
        ),
        "symbol": symbol,
        "direction": str(event.get("direction") or event.get("side")),
        "signalTimestamp": signal_timestamp,
        "entryTimestamp": str(event["entryTimestamp"]),
        "entryPrice": float(event["entryPrice"]),
        "initialStop": float(initial_stop),
        "exitPolicyHash": str(event["exitPolicyHash"]),
        "exitLegCount": len(legs),
        "exitLegs": legs,
    }
