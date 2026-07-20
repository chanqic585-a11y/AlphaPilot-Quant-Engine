from __future__ import annotations

import json
from pathlib import Path

from alphapilot.demo_release_replay.adapters import ReplayResult
from alphapilot.demo_release_replay.contracts import normalize_demo_release_contract
from alphapilot.demo_release_replay.evidence import write_replay_evidence


def _contract(candidate_id: str):
    return normalize_demo_release_contract(
        {
            "demoReleaseId": f"release_{candidate_id}",
            "contractHash": f"contract_{candidate_id}",
            "releaseContentHash": f"content_{candidate_id}",
            "strategyCandidateId": candidate_id,
            "status": "demo_eligible",
            "releaseMode": "experimental_override",
            "strategy": {
                "familyKey": "family",
                "forwardSignalPolicy": {
                    "family": "family",
                    "direction": "long",
                    "parameters": {"targetRewardRiskRatio": 2.0},
                },
                "marketDefinition": {"exchange": "okx", "timeframe": "1d"},
            },
            "overrideAudit": {
                "actor": "user_manual",
                "bypassedEvidence": ["local_forward_samples"],
            },
        }
    )


def _result(candidate_id: str) -> ReplayResult:
    trade = {
        "candidateId": candidate_id,
        "direction": "long",
        "entryDate": "2025-01-01T00:00:00Z",
        "entryPrice": 100.0,
        "exitDate": "2025-01-02T00:00:00Z",
        "exitPrice": 102.0,
        "exitReason": "target",
        "family": "family",
        "feeR": 0.1,
        "grossR": 2.0,
        "holdCandles": 1,
        "netR": 1.9,
        "pair": "BTC/USDT:USDT",
        "sourceExchange": "okx_public",
        "stopPrice": 99.0,
        "targetPrice": 102.0,
        "timeframe": "1d",
    }
    metrics = {"tradeCount": 1, "profitFactor": None, "expectancyR": 1.9, "totalR": 1.9}
    return ReplayResult(
        candidate_id=candidate_id,
        family="family",
        timeframe="1d",
        direction="long",
        selected_pairs=("BTC/USDT:USDT",),
        trades=(trade,),
        metrics=metrics,
        split_metrics={"train": metrics, "validation": {}, "test": {}},
    )


def test_evidence_writer_emits_bounded_research_only_bundle(tmp_path: Path) -> None:
    contracts = tuple(_contract(candidate_id) for candidate_id in ("candidate_a", "candidate_b"))
    results = {candidate_id: _result(candidate_id) for candidate_id in ("candidate_a", "candidate_b")}
    originals = {
        candidate_id: {
            "candidateId": candidate_id,
            "approved": True,
            "metrics": {"tradeCount": 1, "profitFactor": 1.2},
        }
        for candidate_id in results
    }

    summary = write_replay_evidence(tmp_path, contracts, results, originals, expected_count=2)

    assert summary["status"] == "research_replay_only"
    assert summary["contractCount"] == 2
    assert summary["replayCount"] == 2
    assert summary["releaseCountCreated"] == 0
    assert (tmp_path / "contract_inventory.json").exists()
    assert (tmp_path / "comparison.csv").exists()
    assert (tmp_path / "replay_summary.md").exists()
    assert (tmp_path / "trade_ledgers" / "candidate_a.parquet").exists()
    manifest = json.loads((tmp_path / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifactCount"] >= 6
    assert all(row["sha256"] for row in manifest["artifacts"])
