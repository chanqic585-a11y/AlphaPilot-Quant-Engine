"""Strict separation of real liquidation events from diagnostic proxies."""

from __future__ import annotations

from typing import Any


REAL_FIELDS = {
    "timestampUtc",
    "instrumentId",
    "side",
    "notional",
    "quantity",
    "price",
    "source",
    "availableAt",
}


def classify_liquidation_evidence(record: dict[str, Any]) -> str:
    if "liquidationNotional" in record and not REAL_FIELDS <= record.keys():
        raise ValueError("liquidationNotional cannot name proxy liquidation evidence")
    if REAL_FIELDS <= record.keys() and all(record.get(field) is not None for field in REAL_FIELDS):
        return (
            "independently_validated_liquidation"
            if record.get("independentlyValidated")
            else "real_liquidation"
        )
    proxy_fields = {
        "liquidationProxyScore",
        "oiDrop",
        "volumeAnomaly",
        "atrExpansion",
        "wick",
        "priceReclaim",
    }
    if proxy_fields & record.keys():
        if "liquidationProxyScore" not in record:
            return "unavailable"
        return "proxy_liquidation"
    return "unavailable"
