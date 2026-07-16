from __future__ import annotations

from alphapilot.derivatives_data.basis_builder import backward_asof_basis


def _row(timestamp: str, price: float, instrument: str) -> dict[str, object]:
    return {
        "timestampUtc": timestamp,
        "availableAt": timestamp,
        "baseAsset": "BTC",
        "instrumentId": instrument,
        "price": price,
        "exchange": "OKX",
    }


def test_basis_join_is_backward_only_and_never_uses_future_spot_price() -> None:
    spot = [
        _row("2026-01-01T00:00:00Z", 100.0, "BTC-USDT"),
        _row("2026-01-01T00:10:00Z", 200.0, "BTC-USDT"),
    ]
    perpetual = [_row("2026-01-01T00:05:00Z", 102.0, "BTC-USDT-SWAP")]

    result = backward_asof_basis(spot, perpetual, maximum_lag_seconds=600)

    assert len(result) == 1
    assert result[0]["spotPrice"] == 100.0
    assert result[0]["basisPct"] == 2.0
    assert result[0]["sourceTimeDifferenceSeconds"] == 300
    assert result[0]["stale"] is False


def test_basis_rejects_cross_exchange_core_join() -> None:
    spot = [_row("2026-01-01T00:00:00Z", 100.0, "BTC-USDT")]
    perpetual = [{**_row("2026-01-01T00:05:00Z", 102.0, "BTC-USDT-SWAP"), "exchange": "Binance"}]

    try:
        backward_asof_basis(spot, perpetual, maximum_lag_seconds=600)
    except ValueError as error:
        assert "same exchange" in str(error)
    else:
        raise AssertionError("cross-exchange basis join was accepted")
