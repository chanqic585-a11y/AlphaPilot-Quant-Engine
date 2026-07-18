from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphapilot.research_factory.program_v28_32 import (
    ResearchRenewalBudget,
    build_research_renewal_program_id,
    run_research_renewal_program,
)
from alphapilot.scripts.run_v28_32_research_renewal import (
    build_catalog_readiness_audit,
)


def _candidate(
    candidate_id: str,
    *,
    family_id: str = "new-family",
    status: str = "formal_economic_failed",
    release_eligible: bool = False,
    revision_of: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidateId": candidate_id,
        "candidateHash": f"hash-{candidate_id}",
        "familyId": family_id,
        "strategyType": "directional_event_v2",
        "prefilterStatus": "passed",
        "formalStatus": status,
        "fullBacktestsUsed": 2,
        "releaseEligible": release_eligible,
    }
    if revision_of:
        payload["revisionOfCandidateId"] = revision_of
    return payload


def test_program_identity_is_deterministic_and_prompt_scoped() -> None:
    first = build_research_renewal_program_id("sha256:prompt-a")
    second = build_research_renewal_program_id("sha256:prompt-a")
    different = build_research_renewal_program_id("sha256:prompt-b")

    assert first == second
    assert first.startswith("automatic_strategy_renewal_v28_")
    assert first != different


def test_program_counts_budget_archives_failures_and_uses_dynamic_paths(
    tmp_path: Path,
) -> None:
    summary = run_research_renewal_program(
        reports_root=tmp_path,
        prompt_hash="sha256:prompt",
        implementation_commit="commit-1",
        generated_at="2026-07-18T00:00:00Z",
        campaigns=[
            {
                "campaignId": "campaign-01",
                "candidates": [
                    _candidate("candidate-a"),
                    _candidate("candidate-a-v2", revision_of="candidate-a"),
                ],
            }
        ],
    )

    assert summary["finalRoute"] == "completed_zero_qualified_candidates"
    assert summary["candidateCount"] == 2
    assert summary["archivedCount"] == 2
    assert summary["structuralRevisionCount"] == 1
    assert summary["budget"]["fullBacktestsUsed"] == 4
    candidate_path = (
        tmp_path
        / "automatic_research_program"
        / summary["programId"]
        / "campaigns"
        / "campaign-01"
        / "candidates"
        / "candidate-a-v2"
        / "candidate_result.json"
    )
    assert candidate_path.is_file()


def test_failed_identity_cannot_be_reused_and_family_gets_one_revision(
    tmp_path: Path,
) -> None:
    with pytest.raises(ValueError, match="failed_candidate_identity_reused"):
        run_research_renewal_program(
            reports_root=tmp_path,
            prompt_hash="sha256:reuse",
            implementation_commit="commit-1",
            generated_at="2026-07-18T00:00:00Z",
            campaigns=[
                {
                    "campaignId": "campaign-reuse",
                    "candidates": [
                        _candidate("candidate-a"),
                        _candidate("candidate-a"),
                    ],
                }
            ],
        )

    with pytest.raises(ValueError, match="structural_revision_budget_exceeded"):
        run_research_renewal_program(
            reports_root=tmp_path / "second",
            prompt_hash="sha256:revision",
            implementation_commit="commit-1",
            generated_at="2026-07-18T00:00:00Z",
            campaigns=[
                {
                    "campaignId": "campaign-revision",
                    "candidates": [
                        _candidate("candidate-a"),
                        _candidate("candidate-a-v2", revision_of="candidate-a"),
                        _candidate("candidate-a-v3", revision_of="candidate-a-v2"),
                    ],
                }
            ],
        )


def test_program_stops_after_first_release_eligible_candidate(tmp_path: Path) -> None:
    summary = run_research_renewal_program(
        reports_root=tmp_path,
        prompt_hash="sha256:winner",
        implementation_commit="commit-1",
        generated_at="2026-07-18T00:00:00Z",
        campaigns=[
            {
                "campaignId": "campaign-01",
                "candidates": [
                    _candidate(
                        "candidate-pass",
                        status="formal_pass",
                        release_eligible=True,
                    )
                ],
            },
            {
                "campaignId": "campaign-02",
                "candidates": [_candidate("must-not-run")],
            },
        ],
    )

    assert summary["finalRoute"] == "v30_completed_release_eligible"
    assert summary["campaignCount"] == 1
    assert summary["releaseEligibleCandidateIds"] == ["candidate-pass"]


def test_data_blocked_campaign_consumes_no_result_budget(tmp_path: Path) -> None:
    summary = run_research_renewal_program(
        reports_root=tmp_path,
        prompt_hash="sha256:data-blocked",
        implementation_commit="commit-1",
        generated_at="2026-07-18T00:00:00Z",
        campaigns=[
            {
                "campaignId": "campaign-data-audit",
                "status": "formal_data_blocked",
                "candidates": [],
            }
        ],
    )

    assert summary["finalRoute"] == "blocked_formal_data"
    assert summary["candidateCount"] == 0
    assert summary["budget"]["fullBacktestsUsed"] == 0
    assert summary["formalRunCount"] == 0
    assert summary["resultReadCount"] == 0


def test_completed_run_is_idempotent_and_ledger_is_not_duplicated(
    tmp_path: Path,
) -> None:
    kwargs = {
        "reports_root": tmp_path,
        "prompt_hash": "sha256:idempotent",
        "implementation_commit": "commit-1",
        "generated_at": "2026-07-18T00:00:00Z",
        "campaigns": [
            {
                "campaignId": "campaign-01",
                "candidates": [_candidate("candidate-a")],
            }
        ],
    }
    first = run_research_renewal_program(**kwargs)
    second = run_research_renewal_program(**kwargs)
    root = (
        tmp_path
        / "automatic_research_program"
        / str(first["programId"])
    )
    records = [
        json.loads(line)
        for line in (root / "program_ledger.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert second["summaryHash"] == first["summaryHash"]
    assert len(records) == 3
    assert ResearchRenewalBudget().maximum_campaigns == 2


def test_catalog_audit_blocks_unverified_local_ohlcv_before_candidate_identity() -> None:
    audit = build_catalog_readiness_audit(
        {
            "dataManifestHash": "manifest-1",
            "datasets": [
                {
                    "dataType": "ohlcv",
                    "provider": "user_confirmed_local_history",
                    "exchange": "unverified_local_exchange",
                    "isPointInTime": False,
                    "contentHash": "hash-1",
                    "rowCount": 10_000,
                }
            ],
        }
    )

    assert audit["formalReady"] is False
    assert audit["candidateIdentityCreated"] is False
    assert audit["formalRunCount"] == 0
    assert audit["blockers"] == ["ohlcv_provenance_or_pit_semantics_unverified"]


def test_catalog_audit_accepts_verified_point_in_time_ohlcv() -> None:
    audit = build_catalog_readiness_audit(
        {
            "dataManifestHash": "manifest-2",
            "datasets": [
                {
                    "dataType": "ohlcv",
                    "provider": "okx_public_rest",
                    "exchange": "okx",
                    "isPointInTime": True,
                    "contentHash": "hash-2",
                    "rowCount": 20_000,
                }
            ],
        }
    )

    assert audit["formalReady"] is True
    assert audit["blockers"] == []
