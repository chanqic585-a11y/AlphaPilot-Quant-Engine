from __future__ import annotations

from alphapilot.formal_validation.pit_portfolio_context import (
    audit_pit_context_parity,
    freeze_pit_portfolio_context,
)
from alphapilot.formal_validation.ranking_evidence import (
    audit_ranking_evidence_parity,
    freeze_ranking_evidence,
)


def _ranking() -> dict[str, object]:
    return {
        "signalId": "signal-1",
        "signalTimestamp": "2026-01-01T04:00:00Z",
        "eventExtremeResidualZ": -2.7,
        "recoverySizeZ": 0.5,
        "liquidity30d": 5_000_000.0,
        "instrumentId": "BTC-USDT-SWAP",
        "sourceTimestamp": "2026-01-01T04:00:00Z",
        "availableAt": "2026-01-01T04:00:00Z",
    }


def test_ranking_evidence_is_frozen_and_projected_with_full_parity() -> None:
    core, rejected = freeze_ranking_evidence([_ranking()], ranking_policy_hash="rank")
    adapter, adapter_rejected = freeze_ranking_evidence(
        [_ranking()], ranking_policy_hash="rank"
    )
    audit = audit_ranking_evidence_parity(core, adapter)

    assert rejected == adapter_rejected == []
    assert audit["fieldParityPct"] == 100.0
    assert audit["hashParityPct"] == 100.0
    assert audit["postEntryDataUseCount"] == 0


def test_missing_ranking_field_is_rejected_not_zero_filled() -> None:
    row = _ranking()
    row["liquidity30d"] = None
    frozen, rejected = freeze_ranking_evidence([row], ranking_policy_hash="rank")

    assert frozen == []
    assert rejected[0]["reason"] == "reject_ranking_field_unavailable"


def test_pit_portfolio_context_hashes_match_between_core_and_adapter() -> None:
    state = {
        "contextTimestamp": "2026-01-01T04:00:00Z",
        "currentEquity": 100_000.0,
        "openPositions": [],
        "openRiskR": 0.0,
        "sameDirectionRiskR": 0.0,
        "clusterRiskByCluster": {},
        "portfolioBeta": 0.0,
        "concurrentPositionCount": 0,
        "symbolAlreadyOpen": False,
        "clusterMembership": "cluster-1",
        "assetBeta": 1.0,
        "capacityInputs": {"quoteTurnover30d": 5_000_000.0},
    }
    core = freeze_pit_portfolio_context(
        signal_id="signal-1", state=state, formal_policy_hash="policy"
    )
    adapter = freeze_pit_portfolio_context(
        signal_id="signal-1", state=state, formal_policy_hash="policy"
    )

    audit = audit_pit_context_parity([core], [adapter])
    assert audit["fieldParityPct"] == 100.0
    assert audit["hashParityPct"] == 100.0
    assert audit["resultReconstructionCount"] == 0
