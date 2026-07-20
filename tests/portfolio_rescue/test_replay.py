from __future__ import annotations

from alphapilot.portfolio_rescue.contracts import RiskPolicy
from alphapilot.portfolio_rescue.replay import replay_policy


def _trade(
    candidate: str,
    pair: str,
    entry: str,
    exit_: str,
    net_r: float,
    direction: str = "long",
) -> dict[str, object]:
    return {
        "candidateId": candidate,
        "family": candidate,
        "pair": pair,
        "direction": direction,
        "entryDate": entry,
        "exitDate": exit_,
        "netR": net_r,
        "grossR": net_r + 0.1,
        "feeR": 0.1,
        "exitReason": "target" if net_r > 0 else "stop",
    }


def test_replay_applies_chronological_concurrency_direction_and_pair_cooldown() -> None:
    trades = [
        _trade("a", "BTC", "2025-01-01T00:00:00Z", "2025-01-03T00:00:00Z", 1.0),
        _trade("b", "ETH", "2025-01-02T00:00:00Z", "2025-01-04T00:00:00Z", 1.0, "short"),
        _trade("c", "SOL", "2025-01-02T12:00:00Z", "2025-01-05T00:00:00Z", 1.0),
        _trade("a", "BTC", "2025-01-05T00:00:00Z", "2025-01-06T00:00:00Z", 1.0),
    ]
    policy = RiskPolicy("bounded", 7, 2, 1, 0)

    result = replay_policy(trades, policy)

    assert [row["candidateId"] for row in result.accepted_trades] == ["a", "b"]
    assert result.rejection_counts["same_direction_cap"] == 1
    assert result.rejection_counts["pair_cooldown"] == 1
    assert result.metrics["tradeCount"] == 2


def test_losing_pair_cooldown_uses_only_losses_known_after_exit() -> None:
    trades = [
        _trade("a", "BTC", "2025-01-01T00:00:00Z", "2025-01-03T00:00:00Z", -1.0),
        _trade("b", "BTC", "2025-01-02T00:00:00Z", "2025-01-02T12:00:00Z", 0.5),
        _trade("c", "BTC", "2025-01-04T00:00:00Z", "2025-01-05T00:00:00Z", 0.5),
    ]
    policy = RiskPolicy("loss_cooldown", 0, 99, 99, 21)

    result = replay_policy(trades, policy)

    assert [row["candidateId"] for row in result.accepted_trades] == ["a", "b"]
    assert result.rejection_counts["losing_pair_cooldown"] == 1


def test_replay_emits_stress_monthly_and_sleeve_attribution() -> None:
    trades = [
        _trade("a", "BTC", "2025-01-01T00:00:00Z", "2025-01-02T00:00:00Z", 1.0),
        _trade("b", "ETH", "2025-02-01T00:00:00Z", "2025-02-02T00:00:00Z", -0.4),
        _trade("a", "SOL", "2025-03-01T00:00:00Z", "2025-03-02T00:00:00Z", 0.8),
    ]
    policy = RiskPolicy("baseline", 0, 99, 99, 0, additional_cost_stress_r=(0.05, 0.10))

    result = replay_policy(trades, policy)

    assert set(result.sleeve_attribution) == {"a", "b"}
    assert result.monthly_consistency["positiveMonthRatio"] == 2 / 3
    assert result.stress_metrics["plus_0.10R"]["expectancyR"] < result.metrics["expectancyR"]
    assert result.to_dict()["status"] == "development_only"
    assert result.to_dict()["releaseCount"] == 0
