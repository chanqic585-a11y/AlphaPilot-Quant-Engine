"""Preregistered candidate catalog for the two V37I campaigns."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


@dataclass(frozen=True)
class CandidateSpec:
    campaign_id: str
    candidate_id: str
    family_id: str
    name: str
    mechanism: str
    timeframe: str
    source_path: str
    source_equivalence_class: str
    similarity_classification: str
    parameter_trials: tuple[dict[str, Any], ...]
    prefilter_blocker: str | None = None

    @property
    def candidate_hash(self) -> str:
        return stable_hash(self.to_dict(include_hash=False), prefix="v37i_candidate")

    def to_dict(self, *, include_hash: bool = True) -> dict[str, Any]:
        result = asdict(self)
        result["parameter_trials"] = [dict(value) for value in self.parameter_trials]
        if include_hash:
            result["candidate_hash"] = self.candidate_hash
        return result


def build_candidate_catalog() -> tuple[CandidateSpec, ...]:
    funding_source_trials = (
        {"enterFunding": 0.00010, "exitFunding": 0.0, "basisCapPct": 0.15, "minimumTurnover": 0.0, "costBps": 20.0},
        {"enterFunding": 0.00020, "exitFunding": 0.00002, "basisCapPct": 0.10, "minimumTurnover": 0.0, "costBps": 20.0},
        {"enterFunding": 0.00030, "exitFunding": 0.00005, "basisCapPct": 0.10, "minimumTurnover": 0.0, "costBps": 20.0},
    )
    funding_adaptation_trials = (
        {"enterFunding": 0.00015, "exitFunding": 0.00001, "basisCapPct": 0.12, "minimumTurnover": 1_000_000.0, "costBps": 20.0},
        {"enterFunding": 0.00025, "exitFunding": 0.00003, "basisCapPct": 0.10, "minimumTurnover": 2_000_000.0, "costBps": 40.0},
        {"enterFunding": 0.00035, "exitFunding": 0.00005, "basisCapPct": 0.08, "minimumTurnover": 3_000_000.0, "costBps": 60.0},
    )
    return (
        CandidateSpec(
            campaign_id="v37i_campaign_a_funding_carry",
            candidate_id="v37i_funding_carry_source_replication",
            family_id="crypto_funding_carry_v1",
            name="OKX positive-funding delta-neutral carry source replication",
            mechanism="spot long plus perpetual short receives positive funding after dual-leg costs",
            timeframe="8h_funding_event",
            source_path="research/canonical_replications/crypto_funding_carry_v1.json",
            source_equivalence_class="source_faithful_reproduction",
            similarity_classification="same_family_variant",
            parameter_trials=funding_source_trials,
        ),
        CandidateSpec(
            campaign_id="v37i_campaign_a_funding_carry",
            candidate_id="v37i_funding_carry_okx_adaptation",
            family_id="crypto_funding_carry_v1",
            name="OKX capacity-gated positive-funding carry adaptation",
            mechanism="funding carry with preregistered basis and turnover gates",
            timeframe="8h_funding_event",
            source_path="research/canonical_replications/crypto_funding_carry_v1.json",
            source_equivalence_class="clean_room_normalized_variant",
            similarity_classification="same_family_variant",
            parameter_trials=funding_adaptation_trials,
        ),
        CandidateSpec(
            campaign_id="v37i_campaign_b_source_faithful",
            candidate_id="v37i_turtle_source_faithful_candidate",
            family_id="crypto_tsmom_turtle_v1",
            name="Source-faithful Turtle Donchian candidate",
            mechanism="directional persistence with Donchian confirmation",
            timeframe="1d",
            source_path="research/canonical_replications/crypto_tsmom_turtle_v1.json",
            source_equivalence_class="source_faithful_reproduction",
            similarity_classification="exact_duplicate",
            parameter_trials=(
                {"lookbackBars": 60, "entryDonchianBars": 40, "exitDonchianBars": 20},
                {"lookbackBars": 120, "entryDonchianBars": 55, "exitDonchianBars": 20},
                {"lookbackBars": 240, "entryDonchianBars": 80, "exitDonchianBars": 30},
            ),
            prefilter_blocker="duplicate_archived_identity",
        ),
        CandidateSpec(
            campaign_id="v37i_campaign_b_source_faithful",
            candidate_id="v37i_distance_selected_pair_rv_source_faithful",
            family_id="crypto_pair_relative_value_v2",
            name="Distance-selected multi-asset pair relative value",
            mechanism="formation-window normalized-price distance followed by convergence trading",
            timeframe="8h_aligned_panel",
            source_path="research/canonical_replications/crypto_pair_relative_value_v1.json",
            source_equivalence_class="source_faithful_reproduction",
            similarity_classification="mechanism_related",
            parameter_trials=(
                {"formationBars": 90, "entryZ": 1.5, "maximumHoldBars": 30, "costBps": 20.0},
                {"formationBars": 180, "entryZ": 2.0, "maximumHoldBars": 60, "costBps": 40.0},
                {"formationBars": 270, "entryZ": 2.5, "maximumHoldBars": 90, "costBps": 60.0},
            ),
        ),
        CandidateSpec(
            campaign_id="v37i_campaign_b_source_faithful",
            candidate_id="v37i_funding_surprise_event_candidate",
            family_id="crypto_funding_event_v1",
            name="Causal funding-surprise event candidate",
            mechanism="post-settlement funding surprise with embargoed one-period basis exposure",
            timeframe="8h_funding_event",
            source_path="research/canonical_replications/crypto_event_driven_v1.json",
            source_equivalence_class="clean_room_normalized_variant",
            similarity_classification="mechanism_related",
            parameter_trials=(
                {"baselineBars": 30, "surpriseZ": 1.5, "basisCapPct": 0.20, "costBps": 20.0},
                {"baselineBars": 60, "surpriseZ": 2.0, "basisCapPct": 0.15, "costBps": 40.0},
                {"baselineBars": 90, "surpriseZ": 2.5, "basisCapPct": 0.10, "costBps": 60.0},
            ),
        ),
    )
