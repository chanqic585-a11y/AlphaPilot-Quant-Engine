from __future__ import annotations

import pytest

from alphapilot.derivatives_data.liquidation_evidence import classify_liquidation_evidence


def test_real_and_proxy_liquidation_evidence_remain_separate() -> None:
    real = classify_liquidation_evidence(
        {
            "timestampUtc": "2026-01-01T00:00:00Z",
            "instrumentId": "BTC-USDT-SWAP",
            "side": "sell",
            "notional": 1000,
            "quantity": 0.01,
            "price": 100_000,
            "source": "official_public_liquidation_feed",
            "availableAt": "2026-01-01T00:00:01Z",
        }
    )
    proxy = classify_liquidation_evidence(
        {"liquidationProxyScore": 0.8, "oiDrop": 0.1, "atrExpansion": 1.5}
    )

    assert real == "real_liquidation"
    assert proxy == "proxy_liquidation"


def test_proxy_cannot_use_real_liquidation_notional_name() -> None:
    with pytest.raises(ValueError, match="liquidationNotional"):
        classify_liquidation_evidence({"liquidationNotional": 123, "oiDrop": 0.1})
