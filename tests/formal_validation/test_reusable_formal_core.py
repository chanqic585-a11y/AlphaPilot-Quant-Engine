from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import pytest

from alphapilot.formal_validation.candidate_adapter import (
    CandidateAdapter,
    CandidateAdapterContractError,
    CandidateAdapterIdentityError,
    resolve_candidate_signal_identity,
    validate_candidate_binding,
)
from alphapilot.formal_validation.policy_objects import build_v18_policy_objects
from alphapilot.scripts.run_formal_walk_forward import formal_artifact_root


REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class SyntheticCandidateAdapter:
    candidate_id: str = "synthetic_candidate_fixture_02"
    adapter_id: str = "synthetic_candidate_adapter"
    adapter_version: str = "1"

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
        del direction, expected_entry_timestamp, signal_context
        return f"{candidate_id}::synthetic::{symbol}::{signal_timestamp}"

    def resolve_candidate(
        self, *, repo_root: Path, preregistration: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        del repo_root
        return {
            "candidateId": self.candidate_id,
            "strategyDefinitionHash": preregistration["strategyDefinitionHash"],
            "exitPolicyHash": preregistration["exitPolicyHash"],
        }

    def replay(
        self,
        *,
        candidate: Mapping[str, Any],
        frames: Mapping[str, pd.DataFrame],
        round_trip_cost_rate: float,
    ) -> list[dict[str, Any]]:
        del candidate, frames, round_trip_cost_rate
        return []

    def run_parity(
        self, *, bundle: object, repo_root: Path
    ) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
        del bundle, repo_root
        return {"status": "passed", "passed": True}, [], []


def test_second_candidate_fixture_satisfies_shared_adapter_contract() -> None:
    adapter: CandidateAdapter = SyntheticCandidateAdapter()
    preregistration = {
        "sourceCandidateId": adapter.candidate_id,
        "strategyDefinitionHash": "strategy-hash",
        "exitPolicyHash": "exit-hash",
    }

    validate_candidate_binding(
        adapter=adapter,
        preregistration=preregistration,
        requested_candidate_id=adapter.candidate_id,
    )
    candidate = adapter.resolve_candidate(
        repo_root=REPO_ROOT, preregistration=preregistration
    )

    assert candidate["candidateId"] == "synthetic_candidate_fixture_02"


def test_second_candidate_fixture_uses_shared_signal_identity_contract() -> None:
    adapter = SyntheticCandidateAdapter()
    event = {
        "candidateId": adapter.candidate_id,
        "symbol": "BTC-USDT-SWAP",
        "direction": "short",
        "signalTimestamp": "2026-01-01T00:00:00+00:00",
        "entryTimestamp": "2026-01-01T04:00:00+00:00",
    }

    assert resolve_candidate_signal_identity(adapter=adapter, event=event) == (
        "synthetic_candidate_fixture_02::synthetic::BTC-USDT-SWAP::"
        "2026-01-01T00:00:00+00:00"
    )


def test_signal_identity_is_deterministic_and_symbol_scoped() -> None:
    adapter = SyntheticCandidateAdapter()
    event = {
        "candidateId": adapter.candidate_id,
        "symbol": "BTC-USDT-SWAP",
        "direction": "long",
        "signalTimestamp": "2026-01-01T00:00:00+00:00",
        "entryTimestamp": "2026-01-01T04:00:00+00:00",
    }

    first = resolve_candidate_signal_identity(adapter=adapter, event=event)
    second = resolve_candidate_signal_identity(adapter=adapter, event=dict(event))
    eth = resolve_candidate_signal_identity(
        adapter=adapter,
        event={**event, "symbol": "ETH-USDT-SWAP"},
    )

    assert first == second
    assert first != eth


def test_missing_signal_identity_contract_fails_closed() -> None:
    @dataclass(frozen=True)
    class IncompleteAdapter:
        candidate_id: str = "incomplete"
        adapter_id: str = "incomplete"
        adapter_version: str = "1"

    with pytest.raises(
        CandidateAdapterContractError,
        match="candidate_adapter_contract_incomplete",
    ):
        resolve_candidate_signal_identity(
            adapter=IncompleteAdapter(),  # type: ignore[arg-type]
            event={
                "candidateId": "incomplete",
                "symbol": "BTC-USDT-SWAP",
                "direction": "long",
                "signalTimestamp": "2026-01-01T00:00:00+00:00",
                "entryTimestamp": "2026-01-01T04:00:00+00:00",
            },
        )


def test_candidate_binding_rejects_cli_preregistration_mismatch() -> None:
    adapter = SyntheticCandidateAdapter()

    with pytest.raises(CandidateAdapterIdentityError, match="candidate_id_mismatch"):
        validate_candidate_binding(
            adapter=adapter,
            preregistration={"sourceCandidateId": adapter.candidate_id},
            requested_candidate_id="different-candidate",
        )


def test_policy_objects_are_independent_versioned_definitions() -> None:
    policies = build_v18_policy_objects()

    assert set(policies) == {"capacity", "cluster", "beta", "ranking"}
    for policy_id, policy in policies.items():
        assert policy.policy_id == policy_id
        assert policy.version
        assert policy.schema_version
        assert policy.definition_hash
        assert policy.definition["definitionHash"] == policy.definition_hash
        assert "candidateId" not in policy.definition


def test_formal_artifact_path_is_campaign_and_candidate_scoped(
    tmp_path: Path,
) -> None:
    destination = formal_artifact_root(
        tmp_path,
        campaign_id="campaign-001",
        candidate_id="candidate-002",
    )

    assert destination == tmp_path / "campaign-001" / "candidate-002"


def test_formal_core_modules_do_not_import_s01_implementation() -> None:
    modules = [
        REPO_ROOT / "alphapilot/formal_validation/candidate_adapter.py",
        REPO_ROOT / "alphapilot/formal_validation/formal_parity.py",
        REPO_ROOT / "alphapilot/formal_validation/formal_input.py",
        REPO_ROOT / "alphapilot/formal_validation/v18_formal_reporting.py",
        REPO_ROOT / "alphapilot/scripts/run_formal_walk_forward.py",
    ]
    forbidden = (
        "alphapilot.advisory_r_campaign",
        "formal_parity",
        "run_s01",
    )

    for path in modules:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        joined = "\n".join(imports)
        assert not any(value in joined for value in forbidden), (path, imports)


def test_formal_parity_has_no_unresolved_signal_id_symbol() -> None:
    path = REPO_ROOT / "alphapilot/formal_validation/formal_parity.py"
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    assigned = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }
    loaded_private_signal_helpers = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Load)
        and node.id == "_signal_id"
    }

    assert not (loaded_private_signal_helpers - assigned)
