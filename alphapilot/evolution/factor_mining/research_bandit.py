"""UCB-style allocator that controls research compute only."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResearchArm:
    candidateId: str
    trials: int
    meanReward: float
    computeCost: float
    noveltyScore: float


@dataclass(frozen=True)
class ResearchAllocation:
    candidateId: str
    evaluationUnits: int
    priorityScore: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidateId": self.candidateId,
            "evaluationUnits": self.evaluationUnits,
            "priorityScore": self.priorityScore,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ResearchAllocationPlan:
    totalBudget: int
    allocatedBudget: int
    allocations: list[ResearchAllocation]
    researchOnly: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "totalBudget": self.totalBudget,
            "allocatedBudget": self.allocatedBudget,
            "allocations": [item.to_dict() for item in self.allocations],
            "researchOnly": self.researchOnly,
        }


def allocate_research_budget(
    arms: list[ResearchArm],
    *,
    total_budget: int,
    minimum_per_arm: int = 0,
    maximum_per_arm: int | None = None,
    exploration_weight: float = 0.5,
    cost_penalty: float = 0.1,
) -> ResearchAllocationPlan:
    if not arms or total_budget <= 0:
        raise ValueError("Non-empty arms and a positive budget are required")
    if minimum_per_arm < 0 or (maximum_per_arm is not None and maximum_per_arm < minimum_per_arm):
        raise ValueError("Invalid per-arm allocation limits")
    if len({arm.candidateId for arm in arms}) != len(arms):
        raise ValueError("Research arm ids must be unique")
    for arm in arms:
        values = [arm.meanReward, arm.computeCost, arm.noveltyScore]
        if arm.trials < 0 or arm.computeCost <= 0 or not all(math.isfinite(value) for value in values):
            raise ValueError(f"Invalid research arm: {arm.candidateId}")
    required = len(arms) * minimum_per_arm
    if required > total_budget:
        raise ValueError("Budget is smaller than required minimum allocations")

    ordered = sorted(arms, key=lambda item: item.candidateId)
    allocations = {arm.candidateId: minimum_per_arm for arm in ordered}
    remaining = total_budget - required
    total_trials = sum(arm.trials for arm in ordered) + 1

    def score(arm: ResearchArm) -> float:
        effective_trials = arm.trials + allocations[arm.candidateId] + 1
        exploration = exploration_weight * math.sqrt(math.log(total_trials + total_budget) / effective_trials)
        return arm.meanReward + exploration + arm.noveltyScore - cost_penalty * arm.computeCost

    while remaining > 0:
        eligible = [
            arm
            for arm in ordered
            if maximum_per_arm is None or allocations[arm.candidateId] < maximum_per_arm
        ]
        if not eligible:
            break
        selected = max(eligible, key=lambda arm: (score(arm), arm.candidateId))
        allocations[selected.candidateId] += 1
        remaining -= 1

    result = [
        ResearchAllocation(
            candidateId=arm.candidateId,
            evaluationUnits=allocations[arm.candidateId],
            priorityScore=score(arm),
            reason="research_ucb_with_novelty_and_compute_cost",
        )
        for arm in ordered
        if allocations[arm.candidateId] > 0
    ]
    allocated_budget = sum(item.evaluationUnits for item in result)
    return ResearchAllocationPlan(total_budget, allocated_budget, result)
