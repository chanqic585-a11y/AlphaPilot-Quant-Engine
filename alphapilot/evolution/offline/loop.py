"""Run a bounded offline feedback loop that can only create shadow research."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from alphapilot.evolution.factor_mining.correlation_filter import filter_correlated_candidates
from alphapilot.evolution.models.champion_challenger import compare_champion_challenger
from alphapilot.evolution.orchestrator import EvolutionCycleConfig, run_evolution_cycle
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.strategies.candidate_builder import (
    StrategyCandidateDraft,
    build_strategy_candidate,
)

from .evidence_feedback import (
    build_failure_attribution,
    build_research_triggers,
    ingest_evidence_classed_outcomes,
)


@dataclass(frozen=True)
class OfflineEvolutionConfig:
    minimumFormalOutcomes: int = 30
    researchBudget: int = 48
    maxGeneratedFactors: int = 24
    correlationThreshold: float = 0.90
    minimumCorrelationObservations: int = 30

    def __post_init__(self) -> None:
        if self.minimumFormalOutcomes <= 0:
            raise ValueError("minimumFormalOutcomes must be positive")
        if self.researchBudget <= 0 or self.maxGeneratedFactors <= 0:
            raise ValueError("Offline evolution budget and cap must be positive")
        if not 0 < self.correlationThreshold <= 1:
            raise ValueError("correlationThreshold must be in (0, 1]")
        if self.minimumCorrelationObservations < 2:
            raise ValueError("minimumCorrelationObservations must be at least two")


def _release_fingerprints(repository: RegistryRepository) -> dict[str, dict[str, str]]:
    return {
        "forwardReleases": {
            row.forwardReleaseId: row.contentHash for row in repository.list_forward_releases()
        },
        "demoReleases": {
            row.demoReleaseId: row.contentHash for row in repository.list_demo_releases()
        },
        "liveCandidatePackages": {
            row.liveCandidatePackageId: row.contentHash
            for row in repository.list_live_candidate_packages()
        },
        "liveReleases": {
            row.liveReleaseId: row.contentHash for row in repository.list_live_releases()
        },
    }


def _model_metrics(model: Any) -> dict[str, Any]:
    payload = model.payload if isinstance(model.payload, dict) else {}
    artifact = payload.get("artifact") if isinstance(payload.get("artifact"), dict) else {}
    metrics = artifact.get("metrics") if isinstance(artifact.get("metrics"), dict) else {}
    training = (
        artifact.get("trainingEvidence")
        if isinstance(artifact.get("trainingEvidence"), dict)
        else {}
    )
    validation = payload.get("validation") if isinstance(payload.get("validation"), dict) else {}
    return {
        "logLoss": metrics.get("logLoss"),
        "brierScore": metrics.get("brierScore"),
        "foldCount": training.get("foldCount", validation.get("foldCount", 0)),
        "costStressPassed": bool(validation.get("costStressPassed")),
        "stabilityPassed": bool(validation.get("stabilityPassed")),
        "calibrationPassed": bool(validation.get("calibrationPassed")),
    }


def _champion_challenger(repository: RegistryRepository) -> dict[str, Any]:
    models = repository.list_models()
    if len(models) < 2:
        return {
            "status": "blocked_fewer_than_two_registered_models",
            "modelCount": len(models),
            "autoReplacesRunningRelease": False,
        }
    champions = [row for row in models if row.status in {"champion", "demo_champion"}]
    champion = champions[-1] if champions else models[0]
    challenger = next((row for row in reversed(models) if row.modelId != champion.modelId), None)
    if challenger is None:
        return {
            "status": "blocked_challenger_missing",
            "modelCount": len(models),
            "autoReplacesRunningRelease": False,
        }
    try:
        decision = compare_champion_challenger(
            champion_model_id=champion.modelId,
            challenger_model_id=challenger.modelId,
            champion_metrics=_model_metrics(champion),
            challenger_metrics=_model_metrics(challenger),
        )
        return {"status": "completed", "decision": decision.to_dict()}
    except (TypeError, ValueError) as exc:
        return {
            "status": "blocked_incomplete_model_validation",
            "reason": str(exc),
            "championModelId": champion.modelId,
            "challengerModelId": challenger.modelId,
            "autoReplacesRunningRelease": False,
        }


def _correlation_review(
    *,
    candidate_series: dict[str, list[float]] | None,
    reference_series: dict[str, list[float]] | None,
    config: OfflineEvolutionConfig,
) -> dict[str, Any]:
    if not candidate_series:
        return {
            "status": "blocked_missing_materialized_factor_values",
            "acceptedIds": [],
            "inventedFactorValues": False,
        }
    try:
        result = filter_correlated_candidates(
            candidate_series=candidate_series,
            reference_series=reference_series,
            threshold=config.correlationThreshold,
            minimum_observations=config.minimumCorrelationObservations,
        )
    except ValueError as exc:
        return {
            "status": "blocked_invalid_factor_series",
            "reason": str(exc),
            "acceptedIds": [],
            "inventedFactorValues": False,
        }
    return {
        "status": "completed",
        "acceptedIds": result.acceptedIds,
        "rejected": [asdict(item) for item in result.rejected],
        "threshold": result.threshold,
        "observationCount": result.observationCount,
        "inventedFactorValues": False,
    }


def _rollback_readiness(repository: RegistryRepository) -> dict[str, Any]:
    releases = repository.list_demo_releases()
    rollback_targets = [
        str(row.release.get("rollbackTargetDemoReleaseId") or "")
        for row in releases
        if str(row.release.get("rollbackTargetDemoReleaseId") or "").strip()
    ]
    return {
        "demoReleaseCount": len(releases),
        "explicitRollbackTargetCount": len(rollback_targets),
        "driftEventCount": repository.count("DriftEvents"),
        "stopNewEntriesBeforeRollback": True,
        "manageExistingPositionsByOriginalRelease": True,
        "automaticLiveRollbackAllowed": False,
        "liveActionAllowed": False,
    }


def run_offline_evolution_loop(
    *,
    repository: RegistryRepository,
    config: OfflineEvolutionConfig | None = None,
    candidate_factor_series: dict[str, list[float]] | None = None,
    reference_factor_series: dict[str, list[float]] | None = None,
    candidate_drafts: list[StrategyCandidateDraft] | None = None,
) -> dict[str, Any]:
    settings = config or OfflineEvolutionConfig()
    release_before = _release_fingerprints(repository)
    ingestion = ingest_evidence_classed_outcomes(repository.list_outcomes())
    attribution = build_failure_attribution(ingestion)
    triggers = build_research_triggers(
        ingestion,
        attribution,
        minimum_formal_outcomes=settings.minimumFormalOutcomes,
    )
    generation_triggers = [item for item in triggers if item["allowsFactorGeneration"]]
    enough_evidence = ingestion.formalOutcomeCount >= settings.minimumFormalOutcomes
    if enough_evidence and generation_triggers:
        generation = run_evolution_cycle(
            repository=repository,
            config=EvolutionCycleConfig(
                researchBudget=settings.researchBudget,
                maxCandidates=settings.maxGeneratedFactors,
            ),
        )
    else:
        generation = {
            "status": (
                "blocked_no_formal_feedback_evidence"
                if not enough_evidence
                else "completed_no_actionable_factor_trigger"
            ),
            "maximumLifecycleStage": "shadow_research",
            "generatedCandidateCount": 0,
            "newRegisteredFactorDefinitionCount": 0,
            "createsStrategyCandidate": False,
            "createsDemoRelease": False,
            "createsOrders": False,
        }

    correlation = _correlation_review(
        candidate_series=candidate_factor_series,
        reference_series=reference_factor_series,
        config=settings,
    )
    model_review = _champion_challenger(repository)
    registration_rows: list[dict[str, Any]] = []
    registration_allowed = (
        enough_evidence
        and generation.get("status") == "completed_shadow_research"
        and correlation.get("status") == "completed"
        and bool(correlation.get("acceptedIds"))
    )
    for draft in candidate_drafts or []:
        if not registration_allowed:
            registration_rows.append(
                {
                    "name": draft.name,
                    "status": "blocked_offline_validation_incomplete",
                    "createsDemoRelease": False,
                }
            )
            continue
        accepted_factor_ids = set(correlation.get("acceptedIds") or [])
        linked_factor_ids = draft.evidence.get("correlationAcceptedFactorIds")
        if (
            not isinstance(linked_factor_ids, list)
            or not linked_factor_ids
            or not set(str(item) for item in linked_factor_ids).issubset(accepted_factor_ids)
        ):
            registration_rows.append(
                {
                    "name": draft.name,
                    "status": "blocked_candidate_not_bound_to_correlation_review",
                    "createsDemoRelease": False,
                }
            )
            continue
        try:
            candidate = build_strategy_candidate(draft, repository=repository)
            registration_rows.append(
                {
                    "name": draft.name,
                    "status": "registered_shadow_candidate",
                    "strategyCandidateId": candidate.strategyCandidateId,
                    "contentHash": candidate.contentHash,
                    "createsDemoRelease": False,
                }
            )
        except ValueError as exc:
            registration_rows.append(
                {
                    "name": draft.name,
                    "status": "blocked_candidate_contract_invalid",
                    "reason": str(exc),
                    "createsDemoRelease": False,
                }
            )

    release_after = _release_fingerprints(repository)
    if release_after != release_before:
        raise RuntimeError("Offline evolution attempted to mutate a running release")
    core = {
        "config": asdict(settings),
        "acceptedOutcomeIds": ingestion.to_dict()["acceptedOutcomeIds"],
        "triggerIds": [item["triggerId"] for item in triggers],
        "releaseFingerprints": release_before,
    }
    loop_id = stable_hash(core, prefix="offline_evolution_loop")
    if not enough_evidence:
        status = "blocked_no_formal_feedback_evidence"
    elif generation_triggers:
        status = "completed_shadow_research_only"
    else:
        status = "completed_no_change_required"
    return {
        "loopId": loop_id,
        "version": "V13.22.0",
        "status": status,
        "maximumLifecycleStage": "shadow_candidate",
        "config": asdict(settings),
        "evidenceIngestion": ingestion.to_dict(),
        "failureAttribution": attribution,
        "researchTriggers": triggers,
        "boundedFactorGeneration": generation,
        "correlationReview": correlation,
        "championChallengerReview": model_review,
        "candidateRegistration": {
            "allowed": registration_allowed,
            "requestedCount": len(candidate_drafts or []),
            "registeredCount": sum(row["status"] == "registered_shadow_candidate" for row in registration_rows),
            "rows": registration_rows,
        },
        "releaseLineage": {
            "before": release_before,
            "after": release_after,
            "unchanged": True,
        },
        "rollbackReadiness": _rollback_readiness(repository),
        "safetyBoundary": {
            "offlineOnly": True,
            "runningChampionImmutable": True,
            "onlineModelMutation": False,
            "autoReplacesRunningRelease": False,
            "createsDemoRelease": False,
            "createsLiveRelease": False,
            "createsOrders": False,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
        },
    }
