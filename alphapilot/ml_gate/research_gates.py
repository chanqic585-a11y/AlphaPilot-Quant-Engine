"""Research gate criteria for AlphaPilot strategy candidates.

The gates in this module are research filters only. They do not approve live
trading, do not create orders, and do not connect to exchange private APIs.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ResearchGateCriteria:
    name: str
    min_trade_count: int
    min_win_rate_pct: float
    min_reward_risk_ratio: float
    target_reward_risk_ratio: float
    min_profit_factor: float
    max_drawdown_pct: float
    require_positive_total_return: bool = True
    min_recent_trade_count: int = 10
    min_recent_win_rate_pct: float | None = None
    min_recent_profit_factor: float | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


HARD_RESEARCH_GATE = ResearchGateCriteria(
    name="hard_research_to_paper_gate",
    min_trade_count=100,
    min_win_rate_pct=55,
    min_reward_risk_ratio=1.8,
    target_reward_risk_ratio=2.0,
    min_profit_factor=1.35,
    max_drawdown_pct=20,
    min_recent_trade_count=10,
    min_recent_win_rate_pct=50,
    min_recent_profit_factor=1.0,
    description="Strict V13.5 gate. Passing this is required before paper consideration.",
)


RELAXED_SHADOW_WATCHLIST_GATE = ResearchGateCriteria(
    name="relaxed_shadow_watchlist_gate",
    min_trade_count=80,
    min_win_rate_pct=52,
    min_reward_risk_ratio=1.4,
    target_reward_risk_ratio=2.0,
    min_profit_factor=1.2,
    max_drawdown_pct=35,
    min_recent_trade_count=8,
    min_recent_win_rate_pct=48,
    min_recent_profit_factor=0.85,
    description=(
        "Relaxed research gate for expanded-universe shadow watchlist candidates. "
        "This is not paper, Dry-run, or live-trading approval."
    ),
)


OBSERVATION_GATE = ResearchGateCriteria(
    name="observation_gate",
    min_trade_count=50,
    min_win_rate_pct=50,
    min_reward_risk_ratio=1.2,
    target_reward_risk_ratio=2.0,
    min_profit_factor=1.1,
    max_drawdown_pct=45,
    min_recent_trade_count=5,
    min_recent_win_rate_pct=None,
    min_recent_profit_factor=None,
    description="Loose research observation filter. Passing this only means the pattern is worth inspection.",
)


def evaluate_research_gate(
    metrics: dict[str, Any],
    recent_metrics: dict[str, Any] | None,
    criteria: ResearchGateCriteria,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    trade_count = metrics.get("tradeCount") or 0
    win_rate = metrics.get("winRatePct") or 0
    reward_risk = metrics.get("rewardRiskRatio") or 0
    profit_factor = metrics.get("profitFactor") or 0
    max_drawdown = metrics.get("maxDrawdownPct")
    total_return = metrics.get("totalReturnPct") or 0

    if trade_count < criteria.min_trade_count:
        reasons.append(f"trade_count_below_{criteria.min_trade_count}")
    if win_rate < criteria.min_win_rate_pct:
        reasons.append(f"win_rate_below_{criteria.min_win_rate_pct:g}")
    if reward_risk < criteria.min_reward_risk_ratio:
        reasons.append(f"reward_risk_below_{criteria.min_reward_risk_ratio:g}")
    if profit_factor < criteria.min_profit_factor:
        reasons.append(f"profit_factor_below_{criteria.min_profit_factor:g}")
    if max_drawdown is None or max_drawdown > criteria.max_drawdown_pct:
        reasons.append(f"max_drawdown_above_{criteria.max_drawdown_pct:g}")
    if criteria.require_positive_total_return and total_return <= 0:
        reasons.append("total_return_not_positive")

    if recent_metrics is not None:
        recent_count = recent_metrics.get("tradeCount") or 0
        if recent_count < criteria.min_recent_trade_count:
            reasons.append(f"recent_sample_below_{criteria.min_recent_trade_count}")
        else:
            if criteria.min_recent_win_rate_pct is not None:
                recent_win_rate = recent_metrics.get("winRatePct") or 0
                if recent_win_rate < criteria.min_recent_win_rate_pct:
                    reasons.append(f"recent_win_rate_below_{criteria.min_recent_win_rate_pct:g}")
            if criteria.min_recent_profit_factor is not None:
                recent_profit_factor = recent_metrics.get("profitFactor") or 0
                if recent_profit_factor < criteria.min_recent_profit_factor:
                    reasons.append(f"recent_profit_factor_below_{criteria.min_recent_profit_factor:g}")

    return len(reasons) == 0, reasons
