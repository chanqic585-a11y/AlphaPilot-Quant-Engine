from __future__ import annotations

import unittest

from alphapilot.evolution.factor_dsl.parser import parse_expression
from alphapilot.evolution.factor_mining.generator import GeneratedFactorCandidate
from alphapilot.evolution.factor_mining.semantic_deduplicator import deduplicate_candidates


class SemanticDeduplicatorTests(unittest.TestCase):
    def test_equivalent_alias_and_commutative_expressions_collapse(self) -> None:
        candidates = [
            GeneratedFactorCandidate.from_expression(
                parentIds=("a",), mutationType="window", expression=parse_expression("ts_mean(close, 20.0)")
            ),
            GeneratedFactorCandidate.from_expression(
                parentIds=("b",), mutationType="window", expression=parse_expression("rolling_mean(close, 20)")
            ),
            GeneratedFactorCandidate.from_expression(
                parentIds=("c",), mutationType="cross", expression=parse_expression("close + volume")
            ),
            GeneratedFactorCandidate.from_expression(
                parentIds=("d",), mutationType="cross", expression=parse_expression("volume + close")
            ),
        ]

        result = deduplicate_candidates(candidates)

        self.assertEqual(len(result.uniqueCandidates), 2)
        self.assertEqual(result.duplicateCount, 2)
        self.assertEqual(len(result.duplicateMap), 2)


if __name__ == "__main__":
    unittest.main()
