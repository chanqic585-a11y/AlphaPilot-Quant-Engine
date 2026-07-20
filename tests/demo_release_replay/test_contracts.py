from __future__ import annotations

import json
from pathlib import Path

from alphapilot.demo_release_replay.contracts import (
    load_replay_contracts,
    normalize_demo_release_contract,
)


def _payload(candidate_id: str, timeframe: str) -> dict[str, object]:
    return {
        "demoReleaseId": f"demo_release_{candidate_id}",
        "contractHash": f"contract_{candidate_id}",
        "releaseContentHash": f"content_{candidate_id}",
        "strategyCandidateId": candidate_id,
        "status": "demo_eligible",
        "releaseMode": "experimental_override",
        "strategy": {
            "familyKey": "short_rejection",
            "forwardSignalPolicy": {
                "family": "short_rejection",
                "direction": "short",
                "parameters": {"rsi_high": 60, "targetRewardRiskRatio": 2.0},
            },
            "marketDefinition": {
                "exchange": "okx",
                "instrumentType": "SWAP",
                "settleCurrency": "USDT",
                "timeframe": timeframe,
            },
        },
        "overrideAudit": {
            "actor": "user_manual",
            "bypassedEvidence": ["local_forward_samples"],
        },
        "apiKey": "must-not-leak",
        "secretKey": "must-not-leak",
        "privateAccountPayload": {"balance": 1000},
    }


def test_normalization_preserves_only_auditable_replay_identity() -> None:
    normalized = normalize_demo_release_contract(_payload("candidate_1", "1h"))

    assert normalized.demo_release_id == "demo_release_candidate_1"
    assert normalized.contract_hash == "contract_candidate_1"
    assert normalized.release_content_hash == "content_candidate_1"
    assert normalized.strategy_candidate_id == "candidate_1"
    assert normalized.family_key == "short_rejection"
    assert normalized.timeframe == "1h"
    assert normalized.direction == "short"
    assert normalized.parameters["targetRewardRiskRatio"] == 2.0
    assert normalized.release_mode == "experimental_override"
    assert normalized.override_actor == "user_manual"
    assert normalized.bypassed_evidence == ("local_forward_samples",)


def test_normalized_evidence_drops_credentials_and_unknown_private_fields() -> None:
    evidence = normalize_demo_release_contract(_payload("candidate_2", "1d")).to_dict()
    serialized = json.dumps(evidence, sort_keys=True)

    assert "apiKey" not in serialized
    assert "secretKey" not in serialized
    assert "privateAccountPayload" not in serialized
    assert set(evidence) == {
        "bypassedEvidence",
        "contractHash",
        "demoReleaseId",
        "direction",
        "familyKey",
        "marketDefinition",
        "overrideActor",
        "parameters",
        "releaseContentHash",
        "releaseMode",
        "sourcePath",
        "status",
        "strategyCandidateId",
        "timeframe",
    }


def test_directory_loader_is_deterministic_and_bounded(tmp_path: Path) -> None:
    for candidate_id, timeframe in (("candidate_b", "1d"), ("candidate_a", "1h")):
        path = tmp_path / f"{candidate_id}.json"
        path.write_text(json.dumps(_payload(candidate_id, timeframe)), encoding="utf-8")

    loaded = load_replay_contracts(tmp_path, expected_count=2)

    assert [row.strategy_candidate_id for row in loaded] == ["candidate_a", "candidate_b"]
    assert all(row.source_path for row in loaded)
