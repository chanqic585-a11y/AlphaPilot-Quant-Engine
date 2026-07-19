"""Candidate-neutral identity adapter for registered replication plans."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.formal_validation.candidate_adapter import (
    CandidateAdapterContractError,
    CandidateAdapterIdentityError,
    resolve_candidate_signal_identity,
)
from alphapilot.formal_validation.dual_engine_parity import (
    evaluate_dual_engine_parity,
)
from alphapilot.formal_validation.formal_parity import canonicalize_formal_event

from .registry import ReplicationFamily, ReplicationVariant
from .tsmom_engine import (
    SELECTED_TSMOM_TRIALS,
    TsmomReplayError,
    build_tsmom_candidate_spec,
    replay_tsmom_events,
)
from .tsmom_translated import translated_replay_tsmom_events


class CanonicalReplicationCandidateAdapter:
    """Execute only the two Development-selected V36 TSMOM identities."""

    adapter_version = "v36.0"

    def __init__(
        self,
        *,
        family: ReplicationFamily,
        variant: ReplicationVariant,
    ) -> None:
        if variant not in family.variants:
            raise CandidateAdapterIdentityError("variant_not_registered_for_family")
        self.family = family
        self.variant = variant
        self.candidate_id = variant.candidate_id
        self.adapter_id = f"canonical_replication:{family.family_id}"

    def signal_identity(
        self,
        *,
        candidate_id: str,
        symbol: str,
        direction: str,
        signal_timestamp: str,
        expected_entry_timestamp: str | None,
        signal_context: Mapping[str, Any],
    ) -> str:
        if str(candidate_id) != self.candidate_id:
            raise CandidateAdapterIdentityError("candidate_id_mismatch")
        identity = {
            "candidateId": self.candidate_id,
            "familyId": self.family.family_id,
            "symbol": str(symbol),
            "direction": str(direction),
            "signalTimestamp": str(signal_timestamp),
            "expectedEntryTimestamp": expected_entry_timestamp,
            "signalContext": dict(signal_context),
        }
        return stable_hash(identity, prefix="replication_signal")

    def resolve_candidate(
        self,
        *,
        repo_root: Path,
        preregistration: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        frozen_candidate_id = str(preregistration.get("sourceCandidateId") or "")
        if frozen_candidate_id != self.candidate_id:
            raise CandidateAdapterIdentityError("candidate_id_mismatch")
        if self.candidate_id not in SELECTED_TSMOM_TRIALS:
            raise CandidateAdapterContractError(
                "replication_not_executable_until_selected"
            )
        candidate = build_tsmom_candidate_spec(self.candidate_id)
        selected_trial = str(preregistration.get("selectedTrialId") or "")
        if selected_trial != str(candidate["selectedTrialId"]):
            raise CandidateAdapterIdentityError("selected_trial_mismatch")
        for key, error in (
            ("strategyDefinitionHash", "strategy_definition_hash_mismatch"),
            ("exitPolicyHash", "exit_policy_hash_mismatch"),
        ):
            frozen = str(preregistration.get(key) or "")
            if frozen and frozen != str(candidate[key]):
                raise CandidateAdapterIdentityError(error)
        return {
            **candidate,
            "adapterId": self.adapter_id,
            "adapterVersion": self.adapter_version,
            "adaptation": self.variant.adaptation,
            "definitionPath": self.variant.definition_path,
            "repoRoot": str(Path(repo_root).resolve()),
        }

    def replay(
        self,
        *,
        candidate: Mapping[str, Any],
        frames: Mapping[str, pd.DataFrame],
        round_trip_cost_rate: float,
    ) -> Sequence[Mapping[str, Any]]:
        if self.candidate_id not in SELECTED_TSMOM_TRIALS:
            raise CandidateAdapterContractError(
                "replication_not_executable_until_selected"
            )
        try:
            source_events = replay_tsmom_events(
                candidate=candidate,
                frames=frames,
                round_trip_cost_rate=round_trip_cost_rate,
            )
        except TsmomReplayError as error:
            raise CandidateAdapterContractError(str(error)) from error
        return [self._identify_event(event) for event in source_events]

    def run_parity(
        self,
        *,
        bundle: object,
        repo_root: Path,
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        del repo_root
        candidate = dict(getattr(bundle, "candidate"))
        frames = dict(getattr(bundle, "frames"))
        preregistration = dict(getattr(bundle, "preregistration", {}) or {})
        round_trip_cost = float(
            preregistration.get("costModel", {}).get(
                "baseRoundTripCostRate", 0.001
            )
        )
        reference_raw = list(
            self.replay(
                candidate=candidate,
                frames=frames,
                round_trip_cost_rate=round_trip_cost,
            )
        )
        try:
            translated_raw = [
                self._identify_event(event)
                for event in translated_replay_tsmom_events(
                    candidate=candidate,
                    frames=frames,
                    round_trip_cost_rate=round_trip_cost,
                )
            ]
        except TsmomReplayError as error:
            raise CandidateAdapterContractError(str(error)) from error
        reference = [self._canonical_event(event) for event in reference_raw]
        translated = [self._canonical_event(event) for event in translated_raw]
        report = evaluate_dual_engine_parity(reference, translated)
        exact = reference == translated
        report.update(
            {
                "schemaVersion": "v36_tsmom_formal_parity_v1",
                "status": "passed" if report["passed"] and exact else "failed",
                "passed": bool(report["passed"] and exact),
                "canonicalIdentityParityPct": 100.0 if exact else 0.0,
                "adapterRuntimeBase": (
                    "alphapilot.standard_replication.tsmom_translated"
                ),
                "coreEngineChangedForCandidate": False,
                "fullFormalInput": True,
                "syntheticFixtureOnly": False,
            }
        )
        return report, reference, translated

    def _identify_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        identified = dict(event)
        identified["signalId"] = resolve_candidate_signal_identity(
            adapter=self,
            event=identified,
        )
        return identified

    def _canonical_event(self, event: Mapping[str, Any]) -> dict[str, Any]:
        row = dict(event)
        row["exitLegs"] = [
            {
                "legIndex": 0,
                "legFraction": 1.0,
                "exitReason": str(row["exitReason"]),
                "triggerTimestamp": str(row["exitTriggerTimestamp"]),
                "executionTimestamp": str(row["exitTimestamp"]),
                "price": float(row["exitPrice"]),
                "grossR": float(row["grossR"]),
                "feesR": float(row["costR"]),
                "slippageR": 0.0,
                "spreadProxyR": 0.0,
                "fundingR": float(row["fundingR"]),
                "netR": float(row["netR"]),
                "isGapFill": False,
                "ambiguousPath": False,
            }
        ]
        return canonicalize_formal_event(row, candidate_adapter=self)
