"""V35-service-compatible executor for bounded V36 research campaigns."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.standard_replication import ReplicationSourceRegistry

from .contracts import V36ContractError
from .development_replay import build_development_evidence
from .formal_routing import route_formal_outcomes
from .preregistration import build_preregistration
from .selection import project_development_evidence, select_stable_neighborhood


class AutomaticCandidateResearchExecutor:
    """Run frozen V36 inputs while preserving the V35 execution boundary."""

    def __init__(
        self,
        *,
        registry: ReplicationSourceRegistry,
        output_root: Path,
        campaign_inputs: Mapping[str, Mapping[str, object]],
        max_formal_runs: int = 4,
    ) -> None:
        self.registry = registry
        self.output_root = Path(output_root)
        self.campaign_inputs = dict(campaign_inputs)
        self.max_formal_runs = max_formal_runs

    def execute(self, job: Mapping[str, object]) -> dict[str, object]:
        campaign_id = str(job.get("campaignId") or "").strip()
        if not campaign_id or campaign_id not in self.campaign_inputs:
            raise V36ContractError("campaign_input_missing")
        campaign_input = self.campaign_inputs[campaign_id]
        self._validate_job_identity(job=job, campaign_input=campaign_input)
        comparison_panel = campaign_input.get("comparisonPanel")
        if not isinstance(comparison_panel, Mapping):
            raise V36ContractError("comparison_panel_missing")
        preregistration = build_preregistration(
            registry=self.registry,
            campaign_id=campaign_id,
            created_at=str(campaign_input.get("createdAt") or ""),
            comparison_panel=comparison_panel,
        )

        development_replay_audit: dict[str, Any]
        raw_development_evidence = list(campaign_input.get("developmentEvidence") or [])
        replay_config = campaign_input.get("developmentReplay")
        if raw_development_evidence:
            development_replay_audit = {
                "schemaVersion": "v36_development_replay_audit_v1",
                "status": "supplied_evidence",
                "campaignId": campaign_id,
                "evidenceCount": len(raw_development_evidence),
                "formalRunCount": 0,
                "resultReadCount": 0,
                "lockedOosReadCount": 0,
                "releaseCount": 0,
                "approvalCount": 0,
                "demoArm": False,
                "orderCount": 0,
                "privateAccountReadUsed": False,
                "tradeApiUsed": False,
                "withdrawApiUsed": False,
            }
        elif isinstance(replay_config, Mapping):
            raw_development_evidence, development_replay_audit = (
                build_development_evidence(
                    registry=self.registry,
                    preregistration=preregistration,
                    comparison_panel=comparison_panel,
                    replay_config=replay_config,
                )
            )
        else:
            development_replay_audit = {
                "schemaVersion": "v36_development_replay_audit_v1",
                "status": "not_requested",
                "campaignId": campaign_id,
                "evidenceCount": 0,
                "formalRunCount": 0,
                "resultReadCount": 0,
                "lockedOosReadCount": 0,
                "releaseCount": 0,
                "approvalCount": 0,
                "demoArm": False,
                "orderCount": 0,
                "privateAccountReadUsed": False,
                "tradeApiUsed": False,
                "withdrawApiUsed": False,
            }
        if "auditHash" not in development_replay_audit:
            development_replay_audit["auditHash"] = stable_hash(
                development_replay_audit, prefix="v36_development_replay_audit"
            )

        trial_lookup = {
            str(trial["trialId"]): trial
            for trials in preregistration["trialsByCandidate"].values()
            for trial in trials
        }
        projections_by_candidate: dict[str, list[dict[str, Any]]] = {}
        seen_trial_ids: set[str] = set()
        for raw_evidence in raw_development_evidence:
            if not isinstance(raw_evidence, Mapping):
                raise V36ContractError("development_evidence_invalid")
            trial_id = str(raw_evidence.get("trialId") or "")
            if trial_id not in trial_lookup:
                raise V36ContractError("development_trial_not_preregistered")
            if trial_id in seen_trial_ids:
                raise V36ContractError("duplicate_development_trial")
            seen_trial_ids.add(trial_id)
            frozen_trial = trial_lookup[trial_id]
            if raw_evidence.get("candidateId") != frozen_trial["candidateId"]:
                raise V36ContractError("candidate_identity_mismatch")
            if raw_evidence.get("strategyType") != frozen_trial["strategyType"]:
                raise V36ContractError("strategy_type_identity_mismatch")
            normalized_evidence = dict(raw_evidence)
            normalized_evidence["trialIndex"] = frozen_trial["trialIndex"]
            projection = project_development_evidence(normalized_evidence)
            projections_by_candidate.setdefault(
                str(projection["candidateId"]), []
            ).append(projection)

        selections: list[dict[str, Any]] = []
        missing_candidate_ids: list[str] = []
        for candidate_id, trials in preregistration["trialsByCandidate"].items():
            projections = projections_by_candidate.get(candidate_id, [])
            if len(projections) != len(trials):
                missing_candidate_ids.append(candidate_id)
                selections.append(
                    {
                        "schemaVersion": "v36_stable_neighborhood_v1",
                        "candidateId": candidate_id,
                        "eligible": False,
                        "selectedTrialId": None,
                        "reason": "development_evidence_missing",
                        "expectedTrialCount": len(trials),
                        "observedTrialCount": len(projections),
                        "lockedOosReadCount": 0,
                    }
                )
                continue
            selections.append(
                select_stable_neighborhood(
                    candidate_id=candidate_id,
                    projections=projections,
                )
            )

        formal_outcomes = list(campaign_input.get("formalOutcomes") or [])
        if len(formal_outcomes) > self.max_formal_runs:
            raise V36ContractError("formal_run_budget_exceeded")
        formal_route = route_formal_outcomes(
            preregistration=preregistration,
            selections=selections,
            formal_outcomes=formal_outcomes,
        )

        campaign_root = self.output_root / campaign_id
        development_projection = {
            "schemaVersion": "v36_development_projection_set_v1",
            "campaignId": campaign_id,
            "comparisonPanelHash": preregistration["comparisonPanelHash"],
            "projectionCount": sum(len(value) for value in projections_by_candidate.values()),
            "missingCandidateIds": sorted(missing_candidate_ids),
            "projections": [
                projection
                for candidate_id in sorted(projections_by_candidate)
                for projection in sorted(
                    projections_by_candidate[candidate_id],
                    key=lambda item: int(item["trialIndex"]),
                )
            ],
            "lockedOosReadCount": 0,
        }
        neighborhood_selection = {
            "schemaVersion": "v36_neighborhood_selection_set_v1",
            "campaignId": campaign_id,
            "comparisonPanelHash": preregistration["comparisonPanelHash"],
            "eligibleSelectionCount": sum(
                1 for selection in selections if selection["eligible"]
            ),
            "selections": selections,
            "lockedOosReadCount": 0,
        }
        immutable_releases = {
            "schemaVersion": "v36_immutable_release_set_v1",
            "campaignId": campaign_id,
            "releaseCount": formal_route["releaseCount"],
            "approved": False,
            "demoArm": False,
            "orders": 0,
            "releases": formal_route["immutableReleases"],
        }
        summary_core: dict[str, object] = {
            "schemaVersion": "v36_automatic_candidate_research_summary_v1",
            "campaignId": campaign_id,
            "registryId": self.registry.registry_id,
            "status": formal_route["status"],
            "candidateCount": preregistration["candidateCount"],
            "eligibleCandidateCount": preregistration["eligibleCandidateCount"],
            "trialCount": preregistration["trialCount"],
            "blockedFamilyCount": preregistration["blockedFamilyCount"],
            "blockedFamilyIds": preregistration["blockedFamilyIds"],
            "developmentProjectionCount": development_projection["projectionCount"],
            "developmentReplayStatus": development_replay_audit["status"],
            "developmentEvidenceCount": development_replay_audit["evidenceCount"],
            "stableSelectionCount": neighborhood_selection["eligibleSelectionCount"],
            "developmentPhaseStatus": (
                "stable_candidates_selected"
                if neighborhood_selection["eligibleSelectionCount"]
                else (
                    "development_evidence_missing"
                    if development_projection["missingCandidateIds"]
                    else "no_stable_candidates"
                )
            ),
            "formalRunCount": formal_route["formalRunCount"],
            "resultReadCount": formal_route["resultReadCount"],
            "lockedOosReadCount": formal_route["lockedOosReadCount"],
            "releaseCount": formal_route["releaseCount"],
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "privateAccountReadUsed": False,
        }
        summary_core["campaignHash"] = stable_hash(
            summary_core, prefix="v36_campaign"
        )

        artifacts: tuple[tuple[str, Mapping[str, object]], ...] = (
            ("preregistration.json", preregistration),
            ("development_replay_audit.json", development_replay_audit),
            ("development_projection.json", development_projection),
            ("neighborhood_selection.json", neighborhood_selection),
            ("formal_route.json", formal_route),
            ("immutable_releases.json", immutable_releases),
            ("campaign_summary.json", summary_core),
        )
        for filename, payload in artifacts:
            write_json_atomic(campaign_root / filename, payload)
        manifest = {
            "schemaVersion": "v36_artifact_manifest_v1",
            "campaignId": campaign_id,
            "campaignHash": summary_core["campaignHash"],
            "artifacts": [
                {
                    "path": filename,
                    "sha256": sha256_file(campaign_root / filename),
                }
                for filename, _payload in artifacts
            ],
        }
        manifest["manifestHash"] = stable_hash(manifest, prefix="v36_manifest")
        write_json_atomic(campaign_root / "artifact_manifest.json", manifest)

        return {
            **summary_core,
            "artifactPath": str((campaign_root / "campaign_summary.json").resolve()),
        }

    def _validate_job_identity(
        self,
        *,
        job: Mapping[str, object],
        campaign_input: Mapping[str, object],
    ) -> None:
        for field in ("campaignId", "familyIds", "candidateIds"):
            expected = campaign_input.get(field)
            actual = job.get(field)
            if field == "campaignId":
                if str(actual or "") != str(expected or ""):
                    raise V36ContractError("campaign_identity_mismatch")
                continue
            if sorted(str(value) for value in actual or []) != sorted(
                str(value) for value in expected or []
            ):
                raise V36ContractError(f"{field}_identity_mismatch")
