from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from alphapilot.formal_validation.canonical_event_identity import (
    audit_canonical_identity_mapping,
    map_canonical_identity,
)


@dataclass(frozen=True)
class Adapter:
    candidate_id: str = "fixture_candidate"
    adapter_id: str = "fixture_adapter"
    adapter_version: str = "1"

    def signal_identity(self, **kwargs: Any) -> str:
        return (
            f"{kwargs['candidate_id']}::fixture::{kwargs['symbol']}::"
            f"{kwargs['signal_timestamp']}"
        )

    def resolve_candidate(self, **_: Any) -> Mapping[str, Any]:
        return {}

    def replay(self, **_: Any) -> list[Mapping[str, Any]]:
        return []

    def run_parity(self, **_: Any) -> tuple[dict[str, Any], list[Any], list[Any]]:
        return {}, [], []


def _event(symbol: str = "BTC-USDT-SWAP") -> dict[str, object]:
    return {
        "candidateId": "fixture_candidate",
        "symbol": symbol,
        "direction": "long",
        "timeframe": "4h",
        "signalTimestamp": "2026-01-01T00:00:00Z",
        "entryTimestamp": "2026-01-01T04:00:00Z",
        "strategyDefinitionHash": "strategy-hash",
        "exitPolicyHash": "exit-hash",
    }


def test_internal_and_freqtrade_events_map_to_one_authoritative_identity() -> None:
    adapter = Adapter()
    internal = map_canonical_identity(_event(), adapter=adapter, source="internal")
    freqtrade = map_canonical_identity(_event(), adapter=adapter, source="freqtrade")
    audit = audit_canonical_identity_mapping([internal], [freqtrade])

    assert internal["signalId"] == freqtrade["signalId"]
    assert internal["canonicalIdentityHash"] == freqtrade["canonicalIdentityHash"]
    assert internal["exactInstrumentId"] == "BTC-USDT-SWAP"
    assert internal["signalTimestampUtc"] == "2026-01-01T00:00:00Z"
    assert internal["expectedEntryTimestampUtc"] == "2026-01-01T04:00:00Z"
    assert audit["mappingCompletenessPct"] == 100.0
    assert audit["collisionCount"] == 0
    assert audit["unmappedInternalCount"] == 0
    assert audit["unmappedFreqtradeCount"] == 0


def test_identity_collision_is_detected() -> None:
    adapter = Adapter()
    btc = map_canonical_identity(_event(), adapter=adapter, source="internal")
    duplicate = {**btc, "canonicalIdentityHash": "different"}
    audit = audit_canonical_identity_mapping([btc, duplicate], [btc])

    assert audit["collisionCount"] == 1
    assert audit["status"] == "blocked"
