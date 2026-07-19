"""Frozen resource contract for the V37I bounded acquisition sprint."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Mapping

from alphapilot.evolution.registry.hashing import stable_hash


@dataclass(frozen=True)
class V37IBudget:
    maximumCampaigns: int
    maximumFamilies: int
    maximumInitialCandidates: int
    maximumVariantsPerFamily: int
    maximumStructuralRevisionPerFamily: int

    @classmethod
    def default(cls) -> "V37IBudget":
        return cls(
            maximumCampaigns=2,
            maximumFamilies=6,
            maximumInitialCandidates=12,
            maximumVariantsPerFamily=2,
            maximumStructuralRevisionPerFamily=1,
        )

    @property
    def policy_hash(self) -> str:
        return stable_hash(asdict(self), prefix="v37i_acquisition_budget")

    def validate(
        self,
        *,
        campaigns: int,
        families: int,
        candidates: int,
        variants_by_family: Mapping[str, int],
        structural_revisions_by_family: Mapping[str, int] | None = None,
    ) -> None:
        values = {
            "maximumCampaigns": (campaigns, self.maximumCampaigns),
            "maximumFamilies": (families, self.maximumFamilies),
            "maximumInitialCandidates": (
                candidates,
                self.maximumInitialCandidates,
            ),
        }
        for label, (actual, maximum) in values.items():
            if actual > maximum:
                raise ValueError(f"{label}_exceeded:{actual}>{maximum}")
        if any(
            count > self.maximumVariantsPerFamily
            for count in variants_by_family.values()
        ):
            raise ValueError("maximumVariantsPerFamily_exceeded")
        revisions = structural_revisions_by_family or {}
        if any(
            count > self.maximumStructuralRevisionPerFamily
            for count in revisions.values()
        ):
            raise ValueError("maximumStructuralRevisionPerFamily_exceeded")
