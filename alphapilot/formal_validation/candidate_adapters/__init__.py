"""Composition-layer registry for built-in formal candidate adapters."""

from __future__ import annotations

from pathlib import Path

from alphapilot.formal_validation.candidate_adapter import CandidateAdapter
from alphapilot.research_factory.generated_candidate_adapter import (
    GeneratedDirectionalEventAdapter,
)
from alphapilot.standard_replication.candidate_adapter import (
    CanonicalReplicationCandidateAdapter,
)
from alphapilot.standard_replication.registry import (
    ReplicationFamily,
    ReplicationSourceRegistry,
    ReplicationVariant,
)
from alphapilot.standard_replication.tsmom_engine import SELECTED_TSMOM_TRIALS
from alphapilot.standard_replication.tsmom_engine import build_tsmom_candidate_spec

from .s01 import S01CandidateAdapter


def get_candidate_adapter(candidate_id: str) -> CandidateAdapter:
    """Resolve a built-in adapter without leaking it into the formal core."""

    normalized = str(candidate_id or "").strip()
    if normalized == S01CandidateAdapter.CANDIDATE_ID:
        return S01CandidateAdapter()
    if normalized.startswith("auto-"):
        return GeneratedDirectionalEventAdapter(candidate_id=normalized)
    if normalized in SELECTED_TSMOM_TRIALS:
        repo_root = Path(__file__).resolve().parents[3]
        registry = ReplicationSourceRegistry.load(
            repo_root
            / "research"
            / "source_registry"
            / "strategy_research_source_registry.json"
        )
        candidate = build_tsmom_candidate_spec(normalized)
        if normalized == "v37e_tsmom_daily_capacity_successor":
            source_family = registry.require("crypto_tsmom_turtle_v1")
            variant = ReplicationVariant(
                candidate_id=normalized,
                adaptation="metadata_only_capacity_successor",
                definition_path=(
                    "research/canonical_replications/"
                    "crypto_tsmom_daily_capacity_successor_v1.json"
                ),
            )
            family = ReplicationFamily(
                family_id=str(candidate["familyId"]),
                title="Crypto daily TSMOM metadata-capacity successor",
                source=source_family.source,
                mechanism=(
                    "Persistent daily directional trends with a bounded "
                    "holding horizon for purged validation."
                ),
                formula=(
                    "sign(120-day return) with 55-day Donchian confirmation, "
                    "ATR risk and an 18-day maximum hold"
                ),
                parameters={"timeframes": ["1d"], "maximumHoldBars": [18]},
                universe=source_family.universe,
                cost_assumptions=source_family.cost_assumptions,
                adaptation_limits=(
                    "metadata-only change before locked OOS read",
                    "new candidate identity required",
                    "no locked OOS tuning",
                ),
                replication_state="formal_successor",
                variants=(variant,),
            )
        else:
            family = registry.require(str(candidate["familyId"]))
            variant = next(
                row for row in family.variants if row.candidate_id == normalized
            )
        return CanonicalReplicationCandidateAdapter(
            family=family,
            variant=variant,
        )
    raise KeyError(f"candidate_adapter_not_registered:{normalized}")


__all__ = [
    "GeneratedDirectionalEventAdapter",
    "CanonicalReplicationCandidateAdapter",
    "get_candidate_adapter",
    "S01CandidateAdapter",
]
