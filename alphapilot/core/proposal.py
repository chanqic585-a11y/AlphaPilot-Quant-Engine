"""Trade proposal data structures.

V13.2 only defines research and control-plane schemas. A proposal is not an
order and must pass risk and human gates before any future execution design.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class EntryPlan:
    entry_type: str
    estimated_entry_price: float | None
    stop_loss_pct: float
    take_profit_pct: float
    time_stop_bars: int


@dataclass
class RiskPlan:
    account_equity: float
    risk_per_trade_pct: float
    effective_stop_distance: float
    position_notional: float
    leverage: float
    margin_mode: str


@dataclass
class ModelVote:
    model_id: str
    vote: str
    confidence: float | None = None
    rationale: str | None = None


@dataclass
class NewsContext:
    source: str
    headline: str
    sentiment: str
    risk_flag: str | None = None


@dataclass
class TradeProposal:
    proposal_id: str
    created_at: str
    strategy_id: str
    symbol: str
    market: str
    direction: str
    timeframe: str
    signal_source: str
    entry_plan: EntryPlan
    risk_plan: RiskPlan
    signal_reasons: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    model_votes: list[ModelVote] = field(default_factory=list)
    news_context: list[NewsContext] = field(default_factory=list)
    decision: str = "research_only"
    workflow_step: str = "proposal_created"

    def to_dict(self) -> dict:
        """Serialize the proposal for audit/report output."""
        return asdict(self)
