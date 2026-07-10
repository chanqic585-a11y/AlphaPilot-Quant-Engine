from __future__ import annotations

import unittest

from alphapilot.evolution.factor_dsl.parser import parse_expression
from alphapilot.evolution.factor_dsl.validator import validate_factor_expression
from alphapilot.evolution.factor_mining.generator import (
    FactorSeed,
    GenerationConfig,
    generate_factor_candidates,
)


class FactorGeneratorTests(unittest.TestCase):
    def test_generation_is_deterministic_bounded_and_dsl_valid(self) -> None:
        seeds = [
            FactorSeed("mean_close", parse_expression("rolling_mean(close, 20)")),
            FactorSeed("delta_close", parse_expression("delta(close, 3)")),
        ]
        config = GenerationConfig(
            allowedWindows=(3, 10, 20, 30),
            fieldReplacements={"close": ("volume",)},
            crossOperators=("safe_add", "safe_multiply"),
            maxCandidates=12,
        )
        field_types = {"close": "number", "volume": "number"}

        first = generate_factor_candidates(seeds, field_types=field_types, config=config)
        second = generate_factor_candidates(seeds, field_types=field_types, config=config)

        self.assertEqual([item.candidateId for item in first], [item.candidateId for item in second])
        self.assertLessEqual(len(first), 12)
        self.assertGreater(len(first), 2)
        self.assertTrue(
            all(validate_factor_expression(item.expressionAst, field_types=field_types).valid for item in first)
        )
        self.assertTrue(all(item.researchOnly for item in first))
        self.assertTrue(all(item.mutationType in {"window", "field", "cross"} for item in first))

    def test_invalid_seed_and_unapproved_replacement_are_not_emitted(self) -> None:
        seeds = [FactorSeed("bad", parse_expression("rolling_mean(missing, 20)"))]
        config = GenerationConfig(
            allowedWindows=(10, 20),
            fieldReplacements={"missing": ("future_return",)},
            maxCandidates=10,
        )

        candidates = generate_factor_candidates(
            seeds,
            field_types={"close": "number"},
            config=config,
        )

        self.assertEqual(candidates, [])


if __name__ == "__main__":
    unittest.main()
