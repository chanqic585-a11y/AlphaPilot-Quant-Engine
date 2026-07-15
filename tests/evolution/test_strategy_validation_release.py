from __future__ import annotations

import json
from pathlib import Path

import pytest

from alphapilot.evolution.promotion.demo_risk_profile import build_demo_risk_profile
from alphapilot.evolution.promotion.strategy_validation_release import (
    build_strategy_validation_releases,
    write_strategy_validation_releases,
)
from alphapilot.evolution.registry.hashing import stable_hash
from tests.evolution.test_formal_backtest_evidence import formal_evidence, preregistration


def test_zero_formal_passes_produce_zero_releases() -> None:
    releases = build_strategy_validation_releases(
        evidences=[],
        preregistration=preregistration(),
        campaign_summary={"campaignId": "campaign_1", "formalPassCount": 0},
        artifact_manifest={"campaignId": "campaign_1", "manifestHash": "artifacts_1"},
        risk_profile=build_demo_risk_profile(),
        created_at="2026-07-16T00:00:00Z",
    )

    assert releases == []


def test_release_is_hash_bound_unapproved_and_limited_to_three() -> None:
    prereg = preregistration()
    template = dict(prereg["candidates"][0])
    prereg["candidates"] = []
    evidences = []
    for index in range(5):
        candidate_id = f"candidate_{index}"
        candidate = dict(template)
        candidate.update(
            candidateId=candidate_id,
            familyId=f"family_{index}",
            definitionHash=f"definition_{index}",
        )
        prereg["candidates"].append(candidate)
        evidence = formal_evidence()
        evidence.update(candidateId=candidate_id, candidateDefinitionHash=f"definition_{index}")
        evidence["gateEvidence"]["oosMetrics"]["profitFactor"] = 1.2 + index / 10
        evidence["formalGateHash"] = stable_hash(evidence["gateEvidence"], prefix="formal_gate")
        evidences.append(evidence)

    releases = build_strategy_validation_releases(
        evidences=evidences,
        preregistration=prereg,
        campaign_summary={"campaignId": "campaign_1", "formalPassCount": 5},
        artifact_manifest={"campaignId": "campaign_1", "manifestHash": "artifacts_1"},
        risk_profile=build_demo_risk_profile(),
        created_at="2026-07-16T00:00:00Z",
    )

    assert len(releases) == 3
    assert all(row["approvalRequired"] is True and row["approved"] is False for row in releases)
    assert all(row["environment"] == "demo" for row in releases)
    assert releases[0]["candidateId"] == "candidate_4"


def test_hash_addressed_release_cannot_be_overwritten(tmp_path: Path) -> None:
    releases = build_strategy_validation_releases(
        evidences=[formal_evidence()],
        preregistration=preregistration(),
        campaign_summary={"campaignId": "campaign_1", "formalPassCount": 1},
        artifact_manifest={"campaignId": "campaign_1", "manifestHash": "artifacts_1"},
        risk_profile=build_demo_risk_profile(),
        created_at="2026-07-16T00:00:00Z",
    )
    paths = write_strategy_validation_releases(releases, tmp_path)
    assert len(paths) == 1
    assert json.loads(paths[0].read_text(encoding="utf-8"))["releaseHash"] == releases[0]["releaseHash"]

    paths[0].write_text("{}", encoding="utf-8")
    with pytest.raises(FileExistsError):
        write_strategy_validation_releases(releases, tmp_path)
