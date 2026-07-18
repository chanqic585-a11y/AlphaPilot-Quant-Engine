from __future__ import annotations

import json
from pathlib import Path

from alphapilot.research_factory.program_v26 import (
    audit_frozen_candidate_ranking_semantics,
    build_v25_ranking_semantics_clarification_sidecar,
    resolve_current_candidate,
    run_v26_semantic_closure,
)


def _candidate() -> dict[str, object]:
    return {
        "candidateId": "auto-trend_failure_reversal-4h-short-v2",
        "familyId": "trend_failure_reversal",
        "entryDefinition": {
            "setupId": "trend_failure_reversal",
            "setupVersion": "1",
            "signalAtClosedBarOnly": True,
            "entryAtNextBarOpen": True,
        },
        "direction": "short",
        "timeframe": "4h",
    }


def test_v25_clarification_preserves_capacity_and_reclassifies_ranking() -> None:
    sidecar = build_v25_ranking_semantics_clarification_sidecar()
    assert sidecar["capacitySemanticsResolved"] is True
    assert sidecar["capacityCertificationPassed"] is True
    assert sidecar["remainingFormalMissingFields"] == [
        "eventExtremeResidualZ",
        "recoverySizeZ",
    ]
    assert sidecar["clarifiedCurrentStatus"] == (
        "formal_data_blocked_ranking_semantics"
    )
    assert sidecar["oldCandidateMutable"] is False
    assert sidecar["authoritativeCandidateId"] == (
        "auto-trend_failure_reversal-4h-short-v2"
    )
    assert sidecar["legacyRouteCandidateIdAlias"] == (
        "auto-trend_failure-reversal-4h-short-v2"
    )
    assert sidecar["candidateIdentityAliasMismatchPreserved"] is True


def test_frozen_candidate_is_not_uniquely_derivable_without_new_hypothesis() -> None:
    audit = audit_frozen_candidate_ranking_semantics(
        hypothesis={
            "familyId": "trend_failure_reversal",
            "marketMechanism": "trend failure reversal",
        },
        candidate=_candidate(),
        preregistration={"candidateSpec": _candidate()},
        candidate_adapter_source=(
            "prior = ema_fast.shift(1) > ema_slow.shift(1)\n"
            "failure = close < ema_fast\n"
        ),
        freqtrade_adapter_source=(
            "prior = ema_fast.shift(1) > ema_slow.shift(1)\n"
            "failure = close < ema_fast\n"
        ),
        source_commit="frozen-source-commit",
    )

    assert audit["status"] == "not_derivable_without_new_hypothesis"
    assert audit["economicReadCount"] == 0
    assert audit["exitResultReadCount"] == 0
    assert audit["statisticalResultReadCount"] == 0
    assert audit["lockedOosReadCount"] == 0
    assert audit["s01DefaultApplied"] is False
    assert audit["formulaSearchCount"] == 0

    resolution = resolve_current_candidate(audit)
    assert resolution["candidateStatus"] == (
        "closed_current_candidate_ranking_semantics_not_derivable"
    )
    assert resolution["nextStage"] == "v27_new_candidate_research"
    assert resolution["formalLedger"] == {
        "claimCount": 0,
        "attemptCount": 0,
        "resultCount": 0,
        "resultReadCount": 0,
    }


def test_v26_runner_writes_hash_addressed_audit_without_mutating_source(
    tmp_path: Path,
) -> None:
    source_root = tmp_path / "source-program"
    source_root.mkdir()
    (source_root / "sentinel.json").write_text('{"immutable":true}\n', encoding="utf-8")
    before = (source_root / "sentinel.json").read_bytes()

    output = run_v26_semantic_closure(
        repo_root=Path(__file__).resolve().parents[2],
        reports_root=tmp_path / "reports",
        source_program_root=source_root,
        prompt_hash="prompt-hash",
        quant_baseline_commit="quant-baseline",
        console_baseline_commit="console-baseline",
        docs_baseline_commit="docs-baseline",
        source_commit="frozen-source-commit",
        generated_at="2026-07-18T00:00:00Z",
        hypothesis={
            "familyId": "trend_failure_reversal",
            "marketMechanism": "trend failure reversal",
        },
        candidate=_candidate(),
        preregistration={"candidateSpec": _candidate()},
        candidate_adapter_source="ema_fast ema_slow failure",
        freqtrade_adapter_source="ema_fast ema_slow failure",
    )

    root = Path(output["artifactRoot"])
    assert (source_root / "sentinel.json").read_bytes() == before
    assert json.loads((root / "program_state.json").read_text(encoding="utf-8"))[
        "stage"
    ] == "v26_completed_route_v27"
    assert json.loads(
        (root / "current_candidate_resolution.json").read_text(encoding="utf-8")
    )["nextStage"] == "v27_new_candidate_research"
    assert (root / "ranking_semantics_derivation_audit.md").is_file()
    assert json.loads((root / "artifact_manifest.json").read_text(encoding="utf-8"))[
        "artifactCount"
    ] >= 10
