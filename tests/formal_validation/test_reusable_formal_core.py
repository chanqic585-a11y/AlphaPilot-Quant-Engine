from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd
import pytest

from alphapilot.formal_validation.candidate_adapter import (
    CandidateAdapter,
    CandidateAdapterIdentityError,
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
