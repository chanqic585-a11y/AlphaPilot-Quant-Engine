from __future__ import annotations

import unittest

from alphapilot.evolution.factor_mining.research_bandit import (
    ResearchArm,
    allocate_research_budget,
)


class ResearchBanditTests(unittest.TestCase):
    def test_allocation_is_deterministic_bounded_and_research_only(self) -> None:
        arms = [
            ResearchArm("factor_a", trials=10, meanReward=0.4, computeCost=1.0, noveltyScore=0.2),
            ResearchArm("factor_b", trials=2, meanReward=0.2, computeCost=0.5, noveltyScore=0.5),
            ResearchArm("factor_c", trials=20, meanReward=-0.1, computeCost=2.0, noveltyScore=0.1),
        ]

        first = allocate_research_budget(arms, total_budget=12, minimum_per_arm=1)
        second = allocate_research_budget(arms, total_budget=12, minimum_per_arm=1)

        self.assertEqual(first, second)
        self.assertEqual(first.allocatedBudget, 12)
        self.assertEqual(sum(item.evaluationUnits for item in first.allocations), 12)
        payload = first.to_dict()
        self.assertTrue(payload["researchOnly"])
        forbidden = {"symbol", "order", "positionSize", "executionAction", "leverage"}
        self.assertTrue(forbidden.isdisjoint(payload))
        for item in payload["allocations"]:
            self.assertTrue(forbidden.isdisjoint(item))

    def test_budget_smaller_than_required_minimum_fails(self) -> None:
        arms = [
            ResearchArm("a", trials=0, meanReward=0, computeCost=1, noveltyScore=0),
            ResearchArm("b", trials=0, meanReward=0, computeCost=1, noveltyScore=0),
        ]
        with self.assertRaises(ValueError):
            allocate_research_budget(arms, total_budget=1, minimum_per_arm=1)


if __name__ == "__main__":
    unittest.main()
