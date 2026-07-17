from __future__ import annotations
from datetime import datetime, timedelta, timezone

from alphapilot.formal_validation.correlation_cluster_policy import (
    SHARED_UNKNOWN_CLUSTER,
    build_correlation_clusters_v1,
)


def _returns(scale: float, *, count: int = 80, invert: bool = False) -> list[dict[str, object]]:
    start = datetime(2025, 10, 1, tzinfo=timezone.utc)
    rows: list[dict[str, object]] = []
    for offset in range(count):
        value = ((offset % 9) - 4) * 0.002 * scale
        rows.append(
            {
                "timestamp": (start + timedelta(days=offset)).isoformat(),
                "return": -value if invert else value,
            }
        )
    return rows


def test_positive_correlation_uses_deterministic_connected_components() -> None:
    result = build_correlation_clusters_v1(
        {
            "BTC-USDT-SWAP": _returns(1.0),
            "ETH-USDT-SWAP": _returns(1.2),
            "SOL-USDT-SWAP": _returns(0.8, invert=True),
            "NEW-USDT-SWAP": _returns(1.0, count=20),
        },
        as_of_timestamp="2026-01-01T00:00:00Z",
    )

    assignments = result["assignments"]
    assert assignments["BTC-USDT-SWAP"] == assignments["ETH-USDT-SWAP"]
    assert assignments["SOL-USDT-SWAP"] != assignments["BTC-USDT-SWAP"]
    assert assignments["NEW-USDT-SWAP"] == SHARED_UNKNOWN_CLUSTER
    assert result["lookaheadReadCount"] == 0
    assert result["frozenUntil"] == "2026-01-01T00:00:00Z"


def test_cluster_assignment_is_independent_of_input_order() -> None:
    first = build_correlation_clusters_v1(
        {"BTC": _returns(1.0), "ETH": _returns(1.1)},
        as_of_timestamp="2026-01-01T00:00:00Z",
    )
    second = build_correlation_clusters_v1(
        {"ETH": _returns(1.1), "BTC": _returns(1.0)},
        as_of_timestamp="2026-01-01T00:00:00Z",
    )

    assert first["assignments"] == second["assignments"]
    assert first["clusterPolicyHash"] == second["clusterPolicyHash"]
