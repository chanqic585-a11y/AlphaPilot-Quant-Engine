"""Same-exchange backward as-of Spot/Perpetual basis construction."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _parse(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("basis timestamps must include a timezone")
    return parsed.astimezone(timezone.utc)


def backward_asof_basis(
    spot_rows: list[dict[str, Any]],
    perpetual_rows: list[dict[str, Any]],
    maximum_lag_seconds: int,
) -> list[dict[str, Any]]:
    if maximum_lag_seconds <= 0:
        raise ValueError("maximum_lag_seconds must be positive")
    spots_by_asset: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in spot_rows:
        key = (str(row["exchange"]), str(row["baseAsset"]))
        spots_by_asset.setdefault(key, []).append(dict(row))
    for rows in spots_by_asset.values():
        rows.sort(key=lambda row: _parse(str(row["timestampUtc"])))

    results: list[dict[str, Any]] = []
    for perpetual in perpetual_rows:
        key = (str(perpetual["exchange"]), str(perpetual["baseAsset"]))
        candidates = spots_by_asset.get(key, [])
        if not candidates and any(
            str(row.get("baseAsset")) == key[1] for row in spot_rows
        ):
            raise ValueError("formal basis requires Spot and Perpetual data from the same exchange")
        perpetual_time = _parse(str(perpetual["timestampUtc"]))
        backward = [
            row for row in candidates if _parse(str(row["timestampUtc"])) <= perpetual_time
        ]
        if not backward:
            continue
        spot = backward[-1]
        spot_time = _parse(str(spot["timestampUtc"]))
        lag = int((perpetual_time - spot_time).total_seconds())
        spot_price = float(spot["price"])
        perpetual_price = float(perpetual["price"])
        if spot_price <= 0:
            raise ValueError("spotPrice must be positive")
        basis_pct = (perpetual_price / spot_price - 1.0) * 100.0
        available_at = max(
            _parse(str(spot.get("availableAt") or spot["timestampUtc"])),
            _parse(str(perpetual.get("availableAt") or perpetual["timestampUtc"])),
        )
        results.append(
            {
                "timestampUtc": str(perpetual["timestampUtc"]),
                "baseAsset": key[1],
                "spotInstrumentId": spot["instrumentId"],
                "perpetualInstrumentId": perpetual["instrumentId"],
                "spotPrice": spot_price,
                "perpetualPrice": perpetual_price,
                "basisPct": round(basis_pct, 12),
                "annualizedBasisProxy": round(basis_pct * 365.0, 12),
                "sourceTimeDifferenceSeconds": lag,
                "availableAt": available_at.isoformat().replace("+00:00", "Z"),
                "stale": lag > maximum_lag_seconds,
                "joinDirection": "backward_asof",
                "exchange": key[0],
            }
        )
    return results
