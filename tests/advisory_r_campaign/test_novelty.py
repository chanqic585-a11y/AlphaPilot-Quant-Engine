from __future__ import annotations

import json

from alphapilot.advisory_r_campaign.novelty import build_novelty_audit


def test_novelty_audit_reads_history_and_records_overlap_without_replacement(tmp_path) -> None:
    inventory = {
        "strategies": [
            {
                "strategyId": "old-1",
                "strategyFamilyId": "btc_lead_lag",
                "strategyFamily": "BTC lead lag",
                "strategyName": "BTC lead lag continuation",
                "definition": {"entry": "BTC impulse lag"},
                "parameters": {"exit": "trailing"},
            },
            {
                "strategyId": "old-2",
                "strategyFamilyId": "other",
                "strategyFamily": "Other",
                "strategyName": "Unrelated",
                "definition": {},
                "parameters": {},
            },
        ]
    }
    path = tmp_path / "inventory.json"
    path.write_text(json.dumps(inventory), encoding="utf-8")
    candidate = {
        "candidateId": "new-1",
        "familyId": "btc_lead_lag",
        "humanHypothesisZh": "BTC impulse 后 alt 存在 lag continuation",
        "entryDefinition": {"kind": "lagged_underreaction"},
        "exitPolicy": {"mode": "partial_then_trailing"},
    }

    audit = build_novelty_audit([candidate], path)

    assert audit["historyStrategyIdentityCount"] == 2
    assert audit["postResultCandidateReplacementAllowed"] is False
    assert audit["candidates"][0]["historicalFamilyMatches"] == ["old-1"]
    assert audit["candidates"][0]["noveltyStatus"] == "overlap_recorded_frozen_candidate_retained"
