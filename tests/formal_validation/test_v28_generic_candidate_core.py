from __future__ import annotations

import ast
from pathlib import Path

import pandas as pd

from alphapilot.formal_validation.candidate_adapter import (
    resolve_candidate_signal_identity,
    validate_candidate_binding,
)
from alphapilot.formal_validation.candidate_adapters.synthetic_fixture import (
    SyntheticCandidateAdapter,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def _frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": "2026-01-01T00:00:00Z",
                "open": 100.0,
                "high": 102.0,
                "low": 99.0,
                "close": 101.0,
                "volume": 10_000.0,
            }
        ]
    )


def test_two_synthetic_candidates_use_the_same_formal_adapter_contract() -> None:
    adapters = (
        SyntheticCandidateAdapter(candidate_id="synthetic-directional-a"),
        SyntheticCandidateAdapter(candidate_id="synthetic-directional-b"),
    )

    for adapter in adapters:
        preregistration = {
            "sourceCandidateId": adapter.candidate_id,
            "strategyDefinitionHash": f"strategy-{adapter.candidate_id}",
            "exitPolicyHash": "exit-v1",
        }
        validate_candidate_binding(
            adapter=adapter,
            preregistration=preregistration,
            requested_candidate_id=adapter.candidate_id,
        )
        candidate = adapter.resolve_candidate(
            repo_root=REPO_ROOT,
            preregistration=preregistration,
        )
        events = adapter.replay(
            candidate=candidate,
            frames={"BTC-USDT-SWAP": _frame()},
            round_trip_cost_rate=0.001,
        )

        assert len(events) == 1
        assert events[0]["candidateId"] == adapter.candidate_id
        assert resolve_candidate_signal_identity(adapter=adapter, event=events[0])


def test_formal_validation_core_has_no_s01_specific_imports() -> None:
    core_modules = (
        "candidate_adapter.py",
        "canonical_event_identity.py",
        "formal_input.py",
        "formal_parity.py",
    )
    for name in core_modules:
        path = REPO_ROOT / "alphapilot" / "formal_validation" / name
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imports: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.append(node.module or "")
        assert not any("s01" in imported.lower() for imported in imports), (
            path,
            imports,
        )
