from __future__ import annotations

import unittest
from pathlib import Path

from alphapilot.formal_validation.candidate_adapter import (
    CandidateAdapterContractError,
    CandidateAdapterIdentityError,
    validate_candidate_binding,
)
from alphapilot.standard_replication.candidate_adapter import (
    CanonicalReplicationCandidateAdapter,
)
from alphapilot.standard_replication.registry import ReplicationSourceRegistry


class CanonicalReplicationCandidateAdapterTests(unittest.TestCase):
    def setUp(self) -> None:
        repo_root = Path(__file__).resolve().parents[2]
        registry = ReplicationSourceRegistry.load(
            repo_root
            / "research"
            / "source_registry"
            / "strategy_research_source_registry.json"
        )
        self.item = registry.require("crypto_tsmom_turtle_v1")
        self.adapter = CanonicalReplicationCandidateAdapter(
            family=self.item,
            variant=self.item.variants[0],
        )

    def test_signal_identity_is_deterministic_and_candidate_scoped(self) -> None:
        arguments = {
            "candidate_id": self.adapter.candidate_id,
            "symbol": "BTC-USDT-SWAP",
            "direction": "long",
            "signal_timestamp": "2026-07-19T00:00:00+00:00",
            "expected_entry_timestamp": "2026-07-20T00:00:00+00:00",
            "signal_context": {"lookback": 120},
        }

        first = self.adapter.signal_identity(**arguments)
        second = self.adapter.signal_identity(**arguments)

        self.assertEqual(first, second)
        self.assertTrue(first.startswith("replication_signal_"))

    def test_adapter_enforces_exact_frozen_candidate_identity(self) -> None:
        preregistration = {"sourceCandidateId": self.adapter.candidate_id}

        validate_candidate_binding(
            adapter=self.adapter,
            preregistration=preregistration,
            requested_candidate_id=self.adapter.candidate_id,
        )

        with self.assertRaises(CandidateAdapterIdentityError):
            validate_candidate_binding(
                adapter=self.adapter,
                preregistration=preregistration,
                requested_candidate_id="different",
            )

    def test_v35_adapter_fails_closed_before_v36_execution_implementation(self) -> None:
        with self.assertRaisesRegex(
            CandidateAdapterContractError,
            "replication_not_executable_until_v36",
        ):
            self.adapter.replay(
                candidate={},
                frames={},
                round_trip_cost_rate=0.001,
            )


if __name__ == "__main__":
    unittest.main()
