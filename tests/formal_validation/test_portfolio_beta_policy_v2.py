from __future__ import annotations
from datetime import datetime, timedelta, timezone

import pytest

from alphapilot.formal_validation.portfolio_beta_policy import (
    estimate_portfolio_betas_v1,
    project_portfolio_beta_v1,
)


def _returns(multiplier: float, *, count: int = 80) -> list[dict[str, object]]:
    start = datetime(2025, 10, 1, tzinfo=timezone.utc)
    return [
        {
            "timestamp": (start + timedelta(days=offset)).isoformat(),
            "return": ((offset % 11) - 5) * 0.001 * multiplier,
        }
        for offset in range(count)
    ]


def test_beta_uses_prior_aligned_daily_returns_and_rejects_missing_history() -> None:
    result = estimate_portfolio_betas_v1(
        {
            "BTC-USDT-SWAP": _returns(1.0),
            "ETH-USDT-SWAP": _returns(1.5),
            "HEDGE-USDT-SWAP": _returns(-0.5),
            "NEW-USDT-SWAP": _returns(1.0, count=20),
        },
        as_of_timestamp="2026-01-01T00:00:00Z",
    )

    assert result["betas"]["BTC-USDT-SWAP"] == pytest.approx(1.0)
    assert result["betas"]["ETH-USDT-SWAP"] == pytest.approx(1.5)
    assert result["betas"]["HEDGE-USDT-SWAP"] == pytest.approx(-0.5)
    assert result["rejected"]["NEW-USDT-SWAP"] == "insufficient_aligned_history"
    assert result["lookaheadReadCount"] == 0


def test_projected_beta_preserves_direction_sign() -> None:
    result = project_portfolio_beta_v1(
        open_positions=[
            {"direction": "long", "markNotional": 2_000.0, "beta": 1.0},
            {"direction": "short", "markNotional": 1_000.0, "beta": 1.5},
        ],
        candidate={"direction": "short", "markNotional": 500.0, "beta": -0.5},
        current_equity=10_000.0,
    )

    assert result["currentPortfolioBeta"] == pytest.approx(0.05)
    assert result["candidateContribution"] == pytest.approx(0.025)
    assert result["projectedPortfolioBeta"] == pytest.approx(0.075)
