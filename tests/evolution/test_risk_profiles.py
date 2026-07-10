from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.evolution.registry.repositories import RegistryRepository
from alphapilot.evolution.risk_profiles import (
    activate_risk_profile,
    build_risk_profile_record,
    conservative_profile,
    register_default_risk_profiles,
)


class RiskProfileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.connection = connect_registry(Path(self.directory.name) / "registry.sqlite")
        self.repository = RegistryRepository(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.directory.cleanup()

    def test_defaults_are_immutable_and_activation_is_audited(self) -> None:
        defaults = register_default_risk_profiles(self.repository)
        active = activate_risk_profile(
            self.repository,
            defaults["live_canary"],
            actor="user_manual",
            reason="unit_test",
        )

        self.assertEqual(self.repository.count("RiskProfiles"), 4)
        self.assertEqual(self.repository.count("RiskProfileActivations"), 1)
        self.assertEqual(active.riskProfileId, defaults["live_canary"].riskProfileId)
        self.assertEqual(
            self.repository.get_active_risk_profile("live_canary"),
            defaults["live_canary"],
        )

    def test_custom_multi_strategy_profile_is_versioned(self) -> None:
        spec = replace(
            conservative_profile("live_canary", version=2),
            profileKey="live_canary_operator",
            name="Live Canary Operator",
            maxActiveStrategies=3,
            maxConcurrentPositions=5,
            maxPositionsPerStrategy=2,
            maxPositionsPerSymbol=1,
            maxOrderNotionalUsdt=150.0,
            maxLeverage=2,
            maxOpenRiskPercent=2.0,
            maxStrategyOpenRiskPercent=1.0,
            maxSymbolOpenRiskPercent=0.5,
            maxDirectionOpenRiskPercent=1.5,
            maxCorrelatedOpenRiskPercent=1.0,
        )
        record = build_risk_profile_record(spec)
        self.repository.create_risk_profile(record)

        self.assertEqual(record.version, 2)
        self.assertEqual(record.profile["maxActiveStrategies"], 3)
        self.assertEqual(record.profile["maxConcurrentPositions"], 5)

    def test_unbounded_profile_is_rejected(self) -> None:
        spec = replace(
            conservative_profile("live_canary"),
            profileKey="unsafe",
            maxLeverage=20,
        )
        with self.assertRaises(ValueError):
            build_risk_profile_record(spec)


if __name__ == "__main__":
    unittest.main()
