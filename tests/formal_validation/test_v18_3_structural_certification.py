from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

import pandas as pd

from alphapilot.formal_validation.v18_3_structural_certification import (
    certify_signal_evidence_structure,
    signal_evidence_structural_certification_contract,
)


def _frame() -> pd.DataFrame:
    dates = pd.date_range("2026-01-01", periods=160, freq="4h", tz="UTC")
    return pd.DataFrame(
        {
            "date": dates,
            "open": range(160),
            "high": [value + 2 for value in range(160)],
            "low": [value - 1 for value in range(160)],
            "close": [value + 1 for value in range(160)],
            "volume": [1_000_000 + value for value in range(160)],
        }
    )


@dataclass
class _Adapter:
    candidate_id: str = "candidate-synthetic"
    adapter_id: str = "synthetic-adapter"
    adapter_version: str = "1"
    replay_called: bool = False

    def load_signals(self, *, candidate, frames):
        del candidate, frames
        return [
            {
                "candidateId": self.candidate_id,
                "signalId": "signal-1",
                "symbol": "BTC-USDT-SWAP",
                "instrumentId": "BTC-USDT-SWAP",
                "direction": "long",
                "signalTimestamp": "2026-01-20T00:00:00+00:00",
                "entryTimestamp": "2026-01-20T04:00:00+00:00",
                "expectedEntryTimestamp": "2026-01-20T04:00:00+00:00",
                "exitTimestamp": "2026-01-20T08:00:00+00:00",
                "structuralOnly": True,
                "economicResultComputationDisabled": True,
                "exitReplayDisabled": True,
            }
        ]

    def replay(self, **kwargs):
        del kwargs
        self.replay_called = True
        raise AssertionError("structural certification must not replay exits")


def _bundle() -> SimpleNamespace:
    split = {
        "splitPolicyHash": "split-hash",
        "folds": [
            {
                "foldId": "fold-1",
                "trainStartTimestamp": "2026-01-01T00:00:00Z",
                "trainEndExclusiveTimestamp": "2026-01-10T00:00:00Z",
                "purgeStartTimestamp": "2026-01-10T00:00:00Z",
                "purgeEndExclusiveTimestamp": "2026-01-11T00:00:00Z",
                "embargoStartTimestamp": "2026-01-11T00:00:00Z",
                "embargoEndExclusiveTimestamp": "2026-01-12T00:00:00Z",
                "testStartTimestamp": "2026-01-12T00:00:00Z",
                "testEndExclusiveTimestamp": "2026-02-01T00:00:00Z",
            }
        ],
    }
    candidate = {
        "candidateId": "candidate-synthetic",
        "timeframe": "4h",
        "featureDefinition": {"residualWindow": 10, "recoveryBars": 1},
    }
    snapshot = {
        "snapshotHash": "snapshot-hash",
        "datasetReferences": [
            {
                "instrumentId": "BTC-USDT-SWAP",
                "timeframe": "4h",
                "provider": "okx",
                "sha256": "partition-hash",
            }
        ],
    }
    preregistration = {
        "campaignId": "campaign-v18-2",
        "sourceCandidateId": "candidate-synthetic",
        "splitPolicy": split,
        "splitPolicyHash": "split-hash",
        "signalRankingPolicyHash": "ranking-hash",
    }
    return SimpleNamespace(
        preregistration=preregistration,
        candidate=candidate,
        snapshot=snapshot,
        frames={"BTC-USDT-SWAP": _frame()},
    )


def test_structural_certification_uses_signals_without_economic_replay() -> None:
    adapter = _Adapter()

    result = certify_signal_evidence_structure(
        bundle=_bundle(), candidate_adapter=adapter
    )

    assert result["status"] == "certified"
    assert result["rawEventCount"] == 1
    assert result["assignedValidationEventCount"] == 1
    assert result["rankingEvidenceRecordCount"] == 1
    assert result["rankingEvidenceRecordMissingCount"] == 0
    assert result["rankingEvidenceStatusMissingCount"] == 0
    assert result["rankingEvidenceRecordCoveragePct"] == 100.0
    assert result["rankingEvidenceStatusCoveragePct"] == 100.0
    assert result["rankingEvidenceParityPct"] == 100.0
    assert result["economicMetricReadCount"] == 0
    assert result["exitReplayCount"] == 0
    assert result["formalRunClaimCount"] == 0
    assert result["resultMetricWriterDisabled"] is True
    assert result["lockedOosAccessCount"] == 0
    assert adapter.replay_called is False


def test_structural_certification_contract_forbids_economic_stages() -> None:
    contract = signal_evidence_structural_certification_contract()

    assert contract["productionPathRequired"] is True
    assert contract["economicResultComputationDisabled"] is True
    assert contract["exitReplayDisabled"] is True
    assert contract["resultMetricWriterDisabled"] is True
    assert contract["formalRunClaimBudget"] == 0
    assert contract["lockedOosAccessBudget"] == 0
    assert contract["contractHash"].startswith(
        "v18_3_signal_evidence_structural_certification_contract_"
    )

