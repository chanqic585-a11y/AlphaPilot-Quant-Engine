"""Run a bounded factor-evolution cycle that stops at shadow research."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from alphapilot.evolution.factor_dsl.canonicalizer import canonical_field_name
from alphapilot.evolution.factor_dsl.parser import FactorSyntaxError, parse_expression
from alphapilot.evolution.factor_dsl.validator import validate_factor_expression
from alphapilot.evolution.factor_mining.generator import (
    FactorSeed,
    GenerationConfig,
    generate_factor_candidates,
)
from alphapilot.evolution.factor_mining.research_bandit import (
    ResearchArm,
    allocate_research_budget,
)
from alphapilot.evolution.factor_mining.semantic_deduplicator import deduplicate_candidates
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.registry.types import FactorDefinitionRecord


@dataclass(frozen=True)
class EvolutionCycleConfig:
    researchBudget: int = 96
    maxCandidates: int = 48
    allowedWindows: tuple[int, ...] = (3, 6, 12, 24, 48, 72)
    fieldReplacements: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "close": ("volume", "returns_1"),
            "volume": ("quote_volume",),
            "returns_1": ("btc_return_12",),
        }
    )
    additionalFieldTypes: dict[str, str] = field(default_factory=dict)
    crossOperators: tuple[str, ...] = ("safe_add", "safe_multiply")

    def to_dict(self) -> dict[str, Any]:
        return {
            "researchBudget": self.researchBudget,
            "maxCandidates": self.maxCandidates,
            "allowedWindows": list(self.allowedWindows),
            "fieldReplacements": {
                key: list(values) for key, values in sorted(self.fieldReplacements.items())
            },
            "additionalFieldTypes": dict(sorted(self.additionalFieldTypes.items())),
            "crossOperators": list(self.crossOperators),
        }


def _load_seed_factors(
    repository: RegistryRepository,
) -> tuple[list[FactorSeed], dict[str, str], list[dict[str, str]]]:
    seeds: list[FactorSeed] = []
    field_types: dict[str, str] = {}
    blocked: list[dict[str, str]] = []
    for record in repository.list_factor_definitions():
        definition = record.definition
        if not bool(definition.get("dslSupported")) or definition.get("seedEligible") is False:
            continue
        expression = definition.get("canonicalExpression") or record.expression
        source_definition = definition.get("sourceDefinition") or {}
        required_fields = source_definition.get("requiredFields") or definition.get("requiredFields") or []
        for field_name in required_fields:
            field_types[canonical_field_name(str(field_name))] = "number"
        try:
            parsed = parse_expression(str(expression))
        except FactorSyntaxError as exc:
            blocked.append({"factorDefinitionId": record.factorDefinitionId, "reason": str(exc)})
            continue
        seeds.append(FactorSeed(record.factorDefinitionId, parsed))
    return seeds, field_types, blocked


def run_evolution_cycle(
    *,
    repository: RegistryRepository,
    config: EvolutionCycleConfig | None = None,
) -> dict[str, Any]:
    settings = config or EvolutionCycleConfig()
    if settings.researchBudget <= 0 or settings.maxCandidates <= 0:
        raise ValueError("Evolution research budget and candidate cap must be positive")
    seeds, field_types, blocked_seeds = _load_seed_factors(repository)
    field_types.update(settings.additionalFieldTypes)
    generation_config = GenerationConfig(
        allowedWindows=settings.allowedWindows,
        fieldReplacements=settings.fieldReplacements,
        crossOperators=settings.crossOperators,
        maxCandidates=settings.maxCandidates,
    )
    generated = generate_factor_candidates(
        seeds,
        field_types=field_types,
        config=generation_config,
    )
    deduplicated = deduplicate_candidates(generated)
    new_registered_count = 0
    generated_records: list[dict[str, Any]] = []
    for candidate in deduplicated.uniqueCandidates:
        validation = validate_factor_expression(candidate.expressionAst, field_types=field_types)
        definition_payload = {
            "schemaVersion": "generated_factor_definition_v1",
            "dslSupported": True,
            "canonicalExpression": candidate.canonicalExpression,
            "expressionId": candidate.expressionId,
            "sourceDefinition": {"requiredFields": validation.requiredFields},
            "parentFactorDefinitionIds": list(candidate.parentIds),
            "mutationType": candidate.mutationType,
            "mutationDetail": candidate.mutationDetail,
            "seedEligible": False,
            "lifecycleStatus": "shadow_research",
            "researchOnly": True,
            "factorValuesMaterialized": False,
        }
        factor_definition_id = stable_hash(
            {"expressionId": candidate.expressionId, "schemaVersion": "generated_factor_definition_v1"},
            prefix="factor_definition_generated",
        )
        existed = repository.get_factor_definition(factor_definition_id) is not None
        repository.create_factor_definition(
            FactorDefinitionRecord(
                factorDefinitionId=factor_definition_id,
                name=f"Generated {candidate.mutationType} factor",
                version="V13.13.0-shadow",
                expression=candidate.canonicalExpression,
                definition=definition_payload,
                contentHash=stable_hash(definition_payload),
            )
        )
        if not existed:
            new_registered_count += 1
        generated_records.append(
            {
                **candidate.to_dict(),
                "factorDefinitionId": factor_definition_id,
                "validationFields": validation.requiredFields,
                "lifecycleStatus": "shadow_research",
            }
        )

    arms = [
        ResearchArm(
            candidateId=item.candidateId,
            trials=0,
            meanReward=0.0,
            computeCost=max(1.0, len(item.canonicalExpression) / 100),
            noveltyScore={"cross": 0.3, "field": 0.2, "window": 0.1}.get(
                item.mutationType, 0.0
            ),
        )
        for item in deduplicated.uniqueCandidates
    ]
    allocation = (
        allocate_research_budget(arms, total_budget=settings.researchBudget)
        if arms
        else None
    )
    cycle_core = {
        "version": "V13.13.0",
        "config": settings.to_dict(),
        "seedFactorIds": sorted(seed.factorId for seed in seeds),
        "candidateIds": sorted(item.candidateId for item in deduplicated.uniqueCandidates),
    }
    cycle_id = stable_hash(cycle_core, prefix="evolution_cycle")
    factor_run_count = repository.count("FactorRuns")
    result = {
        "cycleId": cycle_id,
        "version": "V13.13.0",
        "status": "completed_shadow_research",
        "maximumLifecycleStage": "shadow_research",
        "config": settings.to_dict(),
        "seedFactorCount": len(seeds),
        "blockedSeeds": blocked_seeds,
        "generatedCandidateCount": len(generated),
        "semanticUniqueCount": len(deduplicated.uniqueCandidates),
        "semanticDuplicateCount": deduplicated.duplicateCount,
        "newRegisteredFactorDefinitionCount": new_registered_count,
        "registeredGeneratedFactors": generated_records,
        "correlationFilterStatus": "blocked_missing_factor_values",
        "correlationFilterInventedValues": False,
        "researchAllocation": allocation.to_dict() if allocation else None,
        "registeredFactorRunCount": factor_run_count,
        "modelTrainingStatus": (
            "blocked_missing_registered_training_dataset"
            if factor_run_count == 0
            else "blocked_missing_materialized_feature_matrix_and_labels"
        ),
        "modelCount": repository.count("Models"),
        "strategyCandidateCount": repository.count("StrategyCandidates"),
        "demoReleaseCount": repository.count("DemoReleases"),
        "safetyBoundary": {
            "researchOnly": True,
            "banditAllocatesResearchOnly": True,
            "onlineModelMutation": False,
            "createsStrategyCandidate": False,
            "createsDemoRelease": False,
            "createsLiveRelease": False,
            "createsOrders": False,
            "usesApiKey": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
        },
    }
    repository.append_audit_event(
        eventType="evolution_cycle_completed",
        entityType="EvolutionCycle",
        entityId=cycle_id,
        payload={
            "maximumLifecycleStage": result["maximumLifecycleStage"],
            "seedFactorCount": result["seedFactorCount"],
            "generatedCandidateCount": result["generatedCandidateCount"],
            "modelTrainingStatus": result["modelTrainingStatus"],
            "createsDemoRelease": False,
            "createsOrders": False,
        },
    )
    return result
