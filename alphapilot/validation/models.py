from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CandidateVersion:
    strategy_version_id: str
    strategy_family: str
    strategy_name: str
    display_label_zh: str
    timeframe: str
    tier: str
    historical_profit_factor: float | None
    historical_average_net_r: float | None
    historical_trade_count: int | None
    requires_prefilter: bool
    historical_prefilter_passed: bool
    source_definition_hash: str | None = None
    source_signal_hash: str | None = None
    parent_strategy_version_id: str | None = None
    auto_optimization_generation: int | None = None


@dataclass(frozen=True)
class CandidateDeduplicationReport:
    candidate_version_count: int
    candidate_family_count: int
    canonical_representative_count: int
    duplicate_version_count: int
    canonical_candidates: list[CandidateVersion] = field(default_factory=list)
    version_to_representative: dict[str, str] = field(default_factory=dict)
    family_definition_conflicts: dict[str, list[str]] = field(default_factory=dict)

