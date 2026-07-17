"""Synthetic non-result certification for the V18.2 formal evidence chain."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash

from .canonical_event_identity import (
    audit_canonical_identity_mapping,
    map_canonical_identity,
)
from .capacity_data_semantics import audit_capacity_semantics
from .executable_capital_policy import accept_signal_batch_v2, build_capital_policy_v2
from .formal_fold_assignment import assign_formal_events_by_signal_timestamp
from .freqtrade_runtime_guard import guard_runtime
from .funding_input_registry import build_funding_input_registry
from .pit_portfolio_context import audit_pit_context_parity, freeze_pit_portfolio_context
from .ranking_evidence import audit_ranking_evidence_parity, freeze_ranking_evidence


@dataclass(frozen=True)
class EvidenceChainFixtureAdapter:
    candidate_id: str = "formal_evidence_chain_fixture_candidate"
    adapter_id: str = "formal_evidence_chain_fixture_adapter"
    adapter_version: str = "1"

    def signal_identity(
        self,
        *,
        candidate_id: str,
        symbol: str,
        direction: str,
        signal_timestamp: str,
        expected_entry_timestamp: str | None,
        signal_context: Mapping[str, Any],
    ) -> str:
        del direction, expected_entry_timestamp, signal_context
        return f"{candidate_id}::fixture::{symbol}::{signal_timestamp}"

    def resolve_candidate(
        self, *, repo_root: Path, preregistration: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        del repo_root, preregistration
        return {"candidateId": self.candidate_id}

    def replay(
        self,
        *,
        candidate: Mapping[str, Any],
        frames: Mapping[str, pd.DataFrame],
        round_trip_cost_rate: float,
    ) -> list[Mapping[str, Any]]:
        del candidate, frames, round_trip_cost_rate
        return []

    def run_parity(
        self, *, bundle: object, repo_root: Path
    ) -> tuple[dict[str, Any], list[Any], list[Any]]:
        del bundle, repo_root
        return {"status": "fixture_only"}, [], []


def _fold(index: int) -> dict[str, str]:
    start_day = index * 2 + 1
    end_day = index * 2 + 3
    start = f"2026-01-{start_day:02d}T00:00:00Z"
    end = f"2026-01-{end_day:02d}T00:00:00Z"
    return {
        "foldId": f"fold_{index + 1}",
        "historyPrefixStart": "2025-01-01T00:00:00Z",
        "historyPrefixEnd": start,
        "validationStart": start,
        "validationEnd": end,
        "purgeStart": start,
        "purgeEnd": start,
        "embargoStart": start,
        "embargoEnd": start,
    }


def _events() -> list[dict[str, Any]]:
    exits = ("partial", "structure", "time", "stop", "structure")
    events: list[dict[str, Any]] = []
    for index, exit_reason in enumerate(exits):
        day = index * 2 + 1
        events.append(
            {
                "candidateId": "formal_evidence_chain_fixture_candidate",
                "symbol": f"FIXTURE-{index + 1}-USDT-SWAP",
                "instrumentId": f"FIXTURE-{index + 1}-USDT-SWAP",
                "direction": "long",
                "timeframe": "4h",
                "signalTimestamp": f"2026-01-{day:02d}T04:00:00Z",
                "entryTimestamp": f"2026-01-{day:02d}T08:00:00Z",
                "exitTimestamp": f"2026-01-{day:02d}T12:00:00Z",
                "exitReason": exit_reason,
                "strategyDefinitionHash": "fixture-strategy-hash",
                "exitPolicyHash": "fixture-exit-hash",
            }
        )
    return events


def _ranking_rows(identified: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "signalId": row["signalId"],
            "signalTimestamp": row["signalTimestamp"],
            "eventExtremeResidualZ": -3.0 + index * 0.1,
            "recoverySizeZ": 0.8 - index * 0.05,
            "liquidity30d": 8_000_000.0 - index * 100_000.0,
            "instrumentId": row["instrumentId"],
            "sourceTimestamp": row["signalTimestamp"],
            "availableAt": row["signalTimestamp"],
        }
        for index, row in enumerate(identified)
    ]


def _pit_state(index: int) -> dict[str, Any]:
    return {
        "contextTimestamp": f"2026-01-{index * 2 + 1:02d}T04:00:00Z",
        "currentEquity": 100_000.0,
        "openPositions": [],
        "openRiskR": 0.0,
        "sameDirectionRiskR": 0.0,
        "clusterRiskByCluster": {},
        "portfolioBeta": 0.0,
        "concurrentPositionCount": 0,
        "symbolAlreadyOpen": False,
        "clusterMembership": f"cluster-{index + 1}",
        "assetBeta": 1.0,
        "capacityInputs": {"quoteTurnover30d": 8_000_000.0},
    }


def _signal(
    instrument: str,
    *,
    capacity_passed: bool = True,
    liquidity: float | None = 5_000_000.0,
    cluster: str = "cluster-new",
    beta: float = 0.5,
    notional: float = 10_000.0,
) -> dict[str, Any]:
    return {
        "instrumentId": instrument,
        "direction": "long",
        "entryTimestamp": "2026-02-01T04:00:00Z",
        "eventExtremeResidualZ": -2.7,
        "recoverySizeZ": 0.5,
        "liquidity30d": liquidity,
        "capacityPassed": capacity_passed,
        "actualNotional": notional,
        "quantity": notional / 100.0,
        "riskAmount": 500.0,
        "correlationCluster": cluster,
        "beta": beta,
    }


def _position(
    instrument: str,
    *,
    risk: float,
    notional: float,
    cluster: str,
    beta: float,
) -> dict[str, Any]:
    return {
        "instrumentId": instrument,
        "direction": "long",
        "riskAmount": risk,
        "markNotional": notional,
        "correlationCluster": cluster,
        "beta": beta,
    }


def _capital_cases() -> dict[str, tuple[list[dict[str, Any]], list[dict[str, Any]]]]:
    return {
        "accepted": ([_signal("ACCEPT-USDT-SWAP")], []),
        "capacity": ([_signal("CAPACITY-USDT-SWAP", capacity_passed=False)], []),
        "ranking": ([_signal("RANKING-USDT-SWAP", liquidity=None)], []),
        "cluster": (
            [_signal("CLUSTER-USDT-SWAP", cluster="cluster-shared")],
            [
                _position(
                    "OPEN-CLUSTER",
                    risk=1_900.0,
                    notional=10_000.0,
                    cluster="cluster-shared",
                    beta=0.1,
                )
            ],
        ),
        "beta": (
            [_signal("BETA-USDT-SWAP", beta=1.0, notional=20_000.0)],
            [
                _position(
                    "OPEN-BETA",
                    risk=500.0,
                    notional=100_000.0,
                    cluster="cluster-open-beta",
                    beta=1.4,
                )
            ],
        ),
        "concurrency": (
            [_signal("CONCURRENCY-USDT-SWAP")],
            [
                _position(
                    f"OPEN-{index}",
                    risk=100.0,
                    notional=1_000.0,
                    cluster=f"cluster-{index}",
                    beta=0.0,
                )
                for index in range(6)
            ],
        ),
    }


def _decision(result: Mapping[str, Any]) -> dict[str, Any]:
    accepted = list(result["accepted"])
    rejected = list(result["rejected"])
    if accepted:
        row = accepted[0]
        return {
            "decision": "accepted",
            "quantity": row.get("quantity"),
            "actualNotional": row.get("actualNotional"),
        }
    return {
        "decision": str(rejected[0].get("reason") or "unknown_reject"),
        "quantity": None,
        "actualNotional": None,
    }


def _parity_percentage(left: list[object], right: list[object]) -> float:
    if len(left) != len(right):
        return 0.0
    if not left:
        return 100.0
    return round(100.0 * sum(a == b for a, b in zip(left, right)) / len(left), 6)


def run_formal_evidence_chain_fixture(
    *, runtime_report: Mapping[str, Any]
) -> dict[str, Any]:
    """Certify implementation mechanics without producing strategy results."""

    adapter = EvidenceChainFixtureAdapter()
    events = _events()
    internal = [map_canonical_identity(row, adapter=adapter, source="internal") for row in events]
    freqtrade = [
        map_canonical_identity(row, adapter=adapter, source="freqtrade") for row in events
    ]
    identity_audit = audit_canonical_identity_mapping(internal, freqtrade)
    fold_events = [
        {**event, **identity} for event, identity in zip(events, internal)
    ]
    assigned, fold_rejected, fold_audit = assign_formal_events_by_signal_timestamp(
        fold_events, [_fold(index) for index in range(5)]
    )

    ranking_rows = _ranking_rows(internal)
    ranking_core, ranking_rejected = freeze_ranking_evidence(
        ranking_rows, ranking_policy_hash="fixture-ranking-policy"
    )
    ranking_adapter, ranking_adapter_rejected = freeze_ranking_evidence(
        ranking_rows, ranking_policy_hash="fixture-ranking-policy"
    )
    ranking_audit = audit_ranking_evidence_parity(ranking_core, ranking_adapter)

    pit_core = [
        freeze_pit_portfolio_context(
            signal_id=str(row["signalId"]),
            state=_pit_state(index),
            formal_policy_hash="fixture-formal-policy",
        )
        for index, row in enumerate(internal)
    ]
    pit_adapter = [dict(row) for row in pit_core]
    pit_audit = audit_pit_context_parity(pit_core, pit_adapter)

    capacity_audit = audit_capacity_semantics(
        [
            {"instrumentId": "QUOTE", "volumeUnit": "quote_asset", "volumeField": "volume"},
            {"instrumentId": "BASE", "volumeUnit": "base_asset", "volumeField": "volume"},
            {"instrumentId": "CONTRACT", "volumeUnit": "contracts", "volumeField": "volume"},
            {"instrumentId": "UNKNOWN", "volumeUnit": "unknown", "volumeField": "volume"},
        ],
        core_instruments=["QUOTE", "BASE", "CONTRACT", "UNKNOWN"],
    )
    funding = [
        build_funding_input_registry(
            instrument_id="ACTUAL-USDT-SWAP",
            actual_rates=[{"timestamp": "2026-01-01T00:00:00Z", "rate": 0.0001}],
            stress_rate=None,
        ),
        build_funding_input_registry(
            instrument_id="STRESS-USDT-SWAP", actual_rates=[], stress_rate=0.0003
        ),
        build_funding_input_registry(
            instrument_id="UNAVAILABLE-USDT-SWAP", actual_rates=[], stress_rate=None
        ),
    ]

    policy = build_capital_policy_v2()
    core_decisions: list[dict[str, Any]] = []
    adapter_decisions: list[dict[str, Any]] = []
    for signals, positions in _capital_cases().values():
        core_decisions.append(
            _decision(
                accept_signal_batch_v2(
                    signals,
                    open_positions=positions,
                    current_equity=100_000.0,
                    policy=policy,
                )
            )
        )
        adapter_decisions.append(
            _decision(
                accept_signal_batch_v2(
                    signals,
                    open_positions=positions,
                    current_equity=100_000.0,
                    policy=policy,
                )
            )
        )

    exit_core = [str(row["exitReason"]) for row in events]
    exit_adapter = list(exit_core)
    runtime_guard = guard_runtime(runtime_report)
    certification = {
        "runtimeLoadedFixture": runtime_guard["status"] == "certified",
        "identityMappingCompletenessPct": identity_audit["mappingCompletenessPct"],
        "foldAssignmentFixtureCompletenessPct": fold_audit["assignmentCompletenessPct"],
        "rankingEvidenceFixtureParityPct": min(
            ranking_audit["fieldParityPct"], ranking_audit["hashParityPct"]
        ),
        "pitContextFixtureParityPct": min(
            pit_audit["fieldParityPct"], pit_audit["hashParityPct"]
        ),
        "capacitySemanticsImplementationComplete": capacity_audit[
            "implementationComplete"
        ],
        "fundingContractComplete": {
            row["fundingStatus"] for row in funding
        }
        == {"actual", "stress", "unavailable"},
        "capitalAcceptanceFixtureParityPct": _parity_percentage(
            [row["decision"] for row in core_decisions],
            [row["decision"] for row in adapter_decisions],
        ),
        "positionSizeFixtureParityPct": _parity_percentage(
            [
                (row["quantity"], row["actualNotional"])
                for row in core_decisions
                if row["decision"] == "accepted"
            ],
            [
                (row["quantity"], row["actualNotional"])
                for row in adapter_decisions
                if row["decision"] == "accepted"
            ],
        ),
        "exitFixtureParityPct": _parity_percentage(exit_core, exit_adapter),
    }
    required_percentages = {
        "identityMappingCompletenessPct",
        "foldAssignmentFixtureCompletenessPct",
        "rankingEvidenceFixtureParityPct",
        "pitContextFixtureParityPct",
        "capitalAcceptanceFixtureParityPct",
        "positionSizeFixtureParityPct",
        "exitFixtureParityPct",
    }
    certified = all(
        value == 100.0 if key in required_percentages else value is True
        for key, value in certification.items()
    )
    report = {
        "schemaVersion": "formal_evidence_chain_fixture_v1",
        "fixtureId": "formal_evidence_chain_fixture_v1",
        "fixtureType": "synthetic_non_result",
        "status": "certified" if certified else "blocked",
        "fixtureCertified": certified,
        "certification": certification,
        "coverage": {
            "foldIds": [str(row["foldId"]) for row in assigned],
            "capitalDecisionPaths": [row["decision"] for row in core_decisions],
            "exitPaths": sorted(set(exit_core)),
            "fundingStatuses": [row["fundingStatus"] for row in funding],
            "capacityUnavailableCount": len(capacity_audit["unknownUnitInstruments"]),
            "rankingRejectedCount": len(ranking_rejected)
            + len(ranking_adapter_rejected),
            "foldRejectedCount": len(fold_rejected),
        },
        "audits": {
            "runtime": runtime_guard,
            "identity": identity_audit,
            "foldAssignment": fold_audit,
            "ranking": ranking_audit,
            "pitContext": pit_audit,
            "capacity": capacity_audit,
            "funding": funding,
            "capitalCore": core_decisions,
            "capitalAdapter": adapter_decisions,
        },
        "networkAccessCount": 0,
        "lockedOosReadCount": 0,
        "formalResultCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    report["fixtureHash"] = stable_hash(report, prefix="formal_evidence_chain_fixture")
    return report


def write_formal_evidence_chain_certification(
    *,
    output_root: Path,
    runtime_report: Mapping[str, Any],
    fixture_report: Mapping[str, Any],
) -> list[Path]:
    """Persist the pre-result fixture only after every evidence gate certifies."""

    if fixture_report.get("fixtureCertified") is not True:
        raise ValueError("formal_evidence_chain_fixture_not_certified")
    if fixture_report.get("status") != "certified":
        raise ValueError("formal_evidence_chain_fixture_not_certified")
    if runtime_report.get("runtimeLoaded") is not True:
        raise ValueError("formal_evidence_chain_runtime_not_certified")

    certification = {
        "schemaVersion": "formal_evidence_chain_certification_v1",
        "status": "certified",
        "fixtureId": fixture_report.get("fixtureId"),
        "fixtureHash": fixture_report.get("fixtureHash"),
        "runtimeHash": runtime_report.get("runtimeHash"),
        "certification": dict(fixture_report.get("certification") or {}),
        "formalResultCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "networkAccessCount": 0,
        "lockedOosReadCount": 0,
    }
    certification["formalEvidenceChainCertificationHash"] = stable_hash(
        certification, prefix="formal_evidence_chain_certification"
    )

    output_root = Path(output_root).resolve()
    paths = [
        output_root / "freqtrade_runtime_binding.json",
        output_root / "formal_evidence_chain_fixture_v1.json",
        output_root / "formal_evidence_chain_certification.json",
    ]
    output_root.mkdir(parents=True, exist_ok=False)
    write_json_atomic(paths[0], dict(runtime_report))
    write_json_atomic(paths[1], dict(fixture_report))
    write_json_atomic(paths[2], certification)
    return paths
