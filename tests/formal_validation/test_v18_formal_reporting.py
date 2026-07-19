from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass, replace
from typing import Any, Mapping, Sequence

import pandas as pd

from alphapilot.formal_validation.executable_capital_policy import (
    build_capital_policy_v2,
)
from alphapilot.formal_validation.formal_input import FormalInputBundle
from alphapilot.formal_validation.formal_parity import canonicalize_formal_event
from alphapilot.formal_validation.formal_stress import build_s01_benchmark
from alphapilot.formal_validation.v18_formal_execution import (
    build_signal_feature_evidence,
)
from alphapilot.formal_validation.v18_formal_reporting import (
    _apply_stable_rejections,
    execute_v18_formal_campaign,
)


def test_stable_rejection_accepts_canonical_signal_id_without_symbol() -> None:
    replay = {
        "decisions": [],
        "rejectionBreakdown": {},
        "rawSignalCount": 0,
        "rejectedSignalCount": 0,
    }

    result = _apply_stable_rejections(
        replay,
        [
            {
                "canonicalSignalId": "S01::canonical::signal-1",
                "exactInstrumentId": "BTC-USDT-SWAP",
                "reason": "reject_ranking_field_unavailable",
            }
        ],
    )

    assert result["decisions"] == [
        {
            "signalId": "S01::canonical::signal-1",
            "instrumentId": "BTC-USDT-SWAP",
            "accepted": False,
            "reason": "reject_ranking_field_unavailable",
            "actualNotional": None,
            "riskAmount": None,
        }
    ]
    assert result["rawSignalCount"] == 1
    assert result["rejectedSignalCount"] == 1

@dataclass(frozen=True)
class _SyntheticAdapter:
    candidate_id: str = "S01"
    adapter_id: str = "synthetic-reporting-adapter"
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
        assert candidate_id == self.candidate_id
        return f"{candidate_id}::synthetic::{symbol}::{signal_timestamp}"

    def run_parity(self, **_: object):
        raise AssertionError("test injects parity runner")

    def replay(self, **_: object):
        raise AssertionError("test injects replay runner")

    def build_formal_ranking_evidence(
        self,
        *,
        events: Sequence[Mapping[str, Any]],
        frames: Mapping[str, pd.DataFrame],
        candidate: Mapping[str, Any],
        include_source_bar_hashes: bool = False,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        return build_signal_feature_evidence(
            events,
            frames,
            candidate,
            include_source_bar_hashes=include_source_bar_hashes,
        )

    def build_formal_benchmark(
        self,
        *,
        events: Sequence[Mapping[str, Any]],
        frames: Mapping[str, pd.DataFrame],
        preregistration: Mapping[str, Any],
    ) -> dict[str, Any]:
        del preregistration
        return build_s01_benchmark(events, frames, hold_bars=12)



def _frames() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2025-01-01", periods=160, freq="12h", tz="UTC")
    btc_close = [100.0 + index * 0.08 for index in range(len(dates))]
    eth_close = [110.0 + index * 0.12 for index in range(len(dates))]
    eth_close[143:146] = [118.0, 119.0, 122.0]

    def frame(close: list[float], volume: float) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "date": dates,
                "open": close,
                "high": [value + 1.0 for value in close],
                "low": [value - 1.0 for value in close],
                "close": close,
                "volume": [volume] * len(close),
            }
        )

    return {
        "BTC-USDT-SWAP": frame(btc_close, 2_000_000.0),
        "ETH-USDT-SWAP": frame(eth_close, 1_500_000.0),
    }


def _raw_event(frames: dict[str, pd.DataFrame]) -> dict[str, object]:
    frame = frames["ETH-USDT-SWAP"]
    return {
        "candidateId": "S01",
        "symbol": "ETH-USDT-SWAP",
        "direction": "long",
        "signalIndex": 145,
        "entryIndex": 146,
        "exitIndex": 148,
        "signalTimestamp": frame.iloc[145]["date"].isoformat(),
        "entryTimestamp": frame.iloc[146]["date"].isoformat(),
        "entryPrice": float(frame.iloc[146]["open"]),
        "initialStopPrice": float(frame.iloc[146]["open"]) - 5.0,
        "riskDistance": 5.0,
        "exitPolicyHash": "exit-policy",
        "legs": [
            {
                "fraction": 1.0,
                "reason": "maximum_hold",
                "triggerTimestamp": frame.iloc[147]["date"].isoformat(),
                "executionTimestamp": frame.iloc[148]["date"].isoformat(),
                "price": float(frame.iloc[148]["open"]),
                "grossR": 0.5,
                "feesR": 0.02,
                "slippageR": 0.01,
                "spreadProxyR": 0.01,
                "fundingR": 0.0,
                "netR": 0.46,
                "isGapFill": False,
                "ambiguousPath": False,
            }
        ],
    }


def _bundle() -> tuple[FormalInputBundle, list[dict[str, object]]]:
    frames = _frames()
    events = [_raw_event(frames)]
    policy = build_capital_policy_v2()
    preregistration = {
        "campaignId": "v18-test-campaign",
        "sourceCandidateId": "S01",
        "splitPolicy": {
            "commonStart": frames["BTC-USDT-SWAP"].iloc[0]["date"].isoformat(),
            "commonCutoffExclusive": (
                frames["BTC-USDT-SWAP"].iloc[-1]["date"]
                + pd.Timedelta(hours=12)
            ).isoformat(),
            "folds": [
                {
                    "foldId": "fold_001",
                    "testStart": 120,
                    "testEndExclusive": 160,
                }
            ],
        },
        "capitalCompetitionPolicy": policy,
        "costModel": {
            "historicalFundingMissingValue": None,
            "missingFundingMayBeFilledWithZero": False,
            "scenarios": [
                {"scenarioId": "base", "multiplier": 1.0},
                {"scenarioId": "cost_1_5x", "multiplier": 1.5},
                {"scenarioId": "cost_2_0x", "multiplier": 2.0},
            ],
        },
        "gates": {
            "economic": {
                "completeFoldCount": 1,
                "profitFactorMinimum": 1.05,
                "averageNetRMinimumExclusive": 0.0,
                "totalNetRMinimumExclusive": 0.0,
                "maximumDrawdownPercent": 25.0,
                "positiveFoldMinimum": 1,
                "cost1_5xProfitFactorMinimum": 1.0,
                "cost1_5xAverageNetRMinimumExclusive": 0.0,
                "cost1_5xTotalNetRMinimumExclusive": 0.0,
                "conservativeFundingAverageNetRMinimumExclusive": 0.0,
                "benchmarkTotalIncrementalNetRMinimumExclusive": 0.0,
                "benchmarkPositiveIncrementFoldMinimum": 1,
            },
            "riskAndEvidence": {
                "translationParity": 1.0,
                "exitLegParity": 1.0,
                "maximumSingleMonthPositiveContribution": 0.35,
                "maximumSingleSymbolPositiveContribution": 0.35,
                "requiresCleanLockedOosForAdmission": True,
            },
        },
        "statisticalPolicy": {
            "neweyWest": {"maximumLagDays": 5, "oneSided": True},
            "comparableCandidatePanel": {
                "status": "unavailable_predeclared",
                "retroactiveConstructionAllowed": False,
                "decisionPolicy": (
                    "route_to_walk_forward_research_pass_statistics_unavailable"
                ),
            },
        },
        "stoppingRules": {
            "economicGateFailure": "archive_s01_current_version",
            "implementationInvalid": "implementation_invalid_requires_new_campaign",
            "statisticsUnavailable": (
                "walk_forward_research_pass_statistics_unavailable"
            ),
        },
        "lockedOosPolicy": {
            "contentRead": False,
            "accessCount": 0,
            "cleanLockedOosAvailable": False,
        },
    }
    candidate = {
        "candidateId": "S01",
        "featureDefinition": {"residualWindow": 10, "recoveryBars": 2},
    }
    bundle = FormalInputBundle(
        preregistration=preregistration,
        candidate=candidate,
        snapshot={"snapshotId": "snapshot-test"},
        frames=frames,
        commonIndex=pd.DatetimeIndex(frames["BTC-USDT-SWAP"]["date"]),
        inputMapping={"schemaVersion": "test-input", "verifiedPartitionCount": 2},
        holdoutLineage={"contentRead": False, "lockedOosAccessCount": 0},
    )
    return bundle, events


def _parity_runner(*, bundle: FormalInputBundle, repo_root: Path):
    del repo_root
    _, raw_events = _bundle()
    adapter = _SyntheticAdapter(candidate_id=str(bundle.candidate["candidateId"]))
    reference = [
        canonicalize_formal_event(row, candidate_adapter=adapter)
        for row in raw_events
    ]
    report = {
        "status": "passed",
        "passed": True,
        "identityParityPct": 100.0,
        "exitLegParityPct": 100.0,
        "referenceEventCount": len(reference),
        "implementationEventCount": len(reference),
        "blockers": [],
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "campaignId": bundle.preregistration["campaignId"],
    }
    return report, reference, [dict(row) for row in reference]


def test_formal_reporting_publishes_complete_audit_without_fabricating_funding(
    tmp_path: Path,
) -> None:
    bundle, raw_events = _bundle()

    result = execute_v18_formal_campaign(
        bundle=bundle,
        repo_root=tmp_path,
        output_root=tmp_path / "formal",
        candidate_adapter=_SyntheticAdapter(),
        parity_runner=_parity_runner,
        raw_replay_runner=lambda **_: [dict(row) for row in raw_events],
    )

    required = {
        "fold_results.json",
        "fold_results.csv",
        "capital_competition_results.json",
        "capital_rejection_breakdown.json",
        "position_sizing_results.json",
        "portfolio_exposure_daily.parquet",
        "freqtrade_results.json",
        "translation_parity.json",
        "signal_identity_parity.json",
        "capital_policy_parity.json",
        "position_size_parity.json",
        "exit_leg_parity.json",
        "cost_stress.json",
        "funding_stress.json",
        "simple_benchmark_results.json",
        "daily_return_panel.parquet",
        "comparable_candidate_panel.parquet",
        "return_panel_audit.json",
        "trial_lineage.json",
        "newey_west_alpha.json",
        "benjamini_hochberg_fdr.json",
        "deflated_sharpe.json",
        "pbo.json",
        "white_reality_check.json",
        "spa.json",
        "concentration.json",
        "uncertainty_intervals.json",
        "gate_matrix.json",
        "route_decision.json",
        "failure_attribution.json",
        "campaign_summary.json",
        "campaign_summary.md",
        "artifact_manifest.json",
    }
    assert required <= {path.name for path in (tmp_path / "formal").iterdir()}
    assert result["route"] == "implementation_invalid_requires_new_campaign"
    assert result["resultManifestHash"]
    assert result["lockedOosAccessCount"] == 0
    assert result["releaseCount"] == 0
    assert result["demoArm"] is False
    assert result["orderCount"] == 0

    funding = pd.read_json(tmp_path / "formal" / "funding_stress.json", typ="series")
    assert funding["gateEvaluable"] is False
    assert funding["rawFundingMissingFilledWithZero"] is False
    comparable = pd.read_parquet(
        tmp_path / "formal" / "comparable_candidate_panel.parquet"
    )
    assert comparable.empty


def test_second_candidate_fixture_executes_through_the_same_formal_core(
    tmp_path: Path,
) -> None:
    bundle, raw_events = _bundle()
    candidate_id = "synthetic_candidate_fixture_02"
    synthetic_bundle = replace(
        bundle,
        preregistration={
            **bundle.preregistration,
            "sourceCandidateId": candidate_id,
        },
        candidate={**bundle.candidate, "candidateId": candidate_id},
    )
    synthetic_events = [
        {**dict(row), "candidateId": candidate_id} for row in raw_events
    ]
    synthetic_adapter = _SyntheticAdapter(candidate_id=candidate_id)
    canonical = [
        canonicalize_formal_event(row, candidate_adapter=synthetic_adapter)
        for row in synthetic_events
    ]

    def parity_runner(*, bundle: FormalInputBundle, repo_root: Path):
        del repo_root
        return (
            {
                "status": "passed",
                "passed": True,
                "identityParityPct": 100.0,
                "exitLegParityPct": 100.0,
                "referenceEventCount": len(canonical),
                "implementationEventCount": len(canonical),
                "blockers": [],
                "lockedOosAccessCount": 0,
                "releaseCount": 0,
                "demoArm": False,
                "orderCount": 0,
                "campaignId": bundle.preregistration["campaignId"],
            },
            [dict(row) for row in canonical],
            [dict(row) for row in canonical],
        )

    result = execute_v18_formal_campaign(
        bundle=synthetic_bundle,
        repo_root=tmp_path,
        output_root=tmp_path / "synthetic-formal",
        candidate_adapter=synthetic_adapter,
        parity_runner=parity_runner,
        raw_replay_runner=lambda **_: [dict(row) for row in synthetic_events],
    )

    manifest = json.loads(
        (tmp_path / "synthetic-formal" / "artifact_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    assert result["resultManifestHash"] == manifest["resultManifestHash"]
    assert manifest["candidateId"] == candidate_id
    assert manifest["candidateAdapter"] == {
        "adapterId": "synthetic-reporting-adapter",
        "adapterVersion": "1",
    }
    assert result["lockedOosAccessCount"] == 0
    assert result["releaseCount"] == 0
    assert result["demoArm"] is False
    assert result["orderCount"] == 0


def test_formal_reporting_is_atomic_when_parity_raises(tmp_path: Path) -> None:
    bundle, raw_events = _bundle()

    def failing_parity(**_: object):
        raise RuntimeError("parity failed before publication")

    try:
        execute_v18_formal_campaign(
            bundle=bundle,
            repo_root=tmp_path,
            output_root=tmp_path / "formal",
            candidate_adapter=_SyntheticAdapter(),
            parity_runner=failing_parity,
            raw_replay_runner=lambda **_: [dict(row) for row in raw_events],
        )
    except RuntimeError as error:
        assert str(error) == "parity failed before publication"
    else:
        raise AssertionError("expected parity failure")

    assert not (tmp_path / "formal" / "artifact_manifest.json").exists()
    assert not list((tmp_path / "formal").glob("fold_results.*"))


def test_v18_2_evidence_chain_publishes_complete_candidate_neutral_artifacts(
    tmp_path: Path,
) -> None:
    bundle, raw_events = _bundle()
    frame = bundle.frames["BTC-USDT-SWAP"]
    split = {
        **bundle.preregistration["splitPolicy"],
        "folds": [
            {
                "foldId": "fold_001",
                "trainStartTimestamp": frame.iloc[0]["date"].isoformat(),
                "trainEndExclusiveTimestamp": frame.iloc[115]["date"].isoformat(),
                "purgeStartTimestamp": frame.iloc[115]["date"].isoformat(),
                "purgeEndExclusiveTimestamp": frame.iloc[118]["date"].isoformat(),
                "embargoStartTimestamp": frame.iloc[118]["date"].isoformat(),
                "embargoEndExclusiveTimestamp": frame.iloc[120]["date"].isoformat(),
                "testStartTimestamp": frame.iloc[120]["date"].isoformat(),
                "testEndExclusiveTimestamp": (
                    frame.iloc[-1]["date"] + pd.Timedelta(hours=12)
                ).isoformat(),
            }
        ],
    }
    preregistration = {
        **bundle.preregistration,
        "splitPolicy": split,
        "strategyDefinitionHash": "strategy-hash",
        "exitPolicyHash": "exit-policy",
        "signalRankingPolicyHash": "ranking-policy",
        "formalPortfolioPolicyV2Hash": "portfolio-policy",
        "fundingRequiredForResearchOnly": False,
        "fundingRequiredForFormalEvidence": True,
    }
    snapshot = {
        **bundle.snapshot,
        "snapshotHash": "snapshot-hash",
        "datasetReferences": [
            {
                "instrumentId": symbol,
                "timeframe": "4h",
                "path": f"canonical/{symbol}/4h/data.parquet",
                "provider": "okx",
                "sha256": f"sha-{index}",
            }
            for index, symbol in enumerate(bundle.frames)
        ],
    }
    v18_2_bundle = replace(
        bundle,
        preregistration=preregistration,
        candidate={
            **bundle.candidate,
            "timeframe": "4h",
            "strategyDefinitionHash": "strategy-hash",
            "exitPolicyHash": "exit-policy",
        },
        snapshot=snapshot,
    )
    result = execute_v18_formal_campaign(
        bundle=v18_2_bundle,
        repo_root=tmp_path,
        output_root=tmp_path / "v18-2-formal",
        candidate_adapter=_SyntheticAdapter(),
        parity_runner=_parity_runner,
        raw_replay_runner=lambda **_: [dict(row) for row in raw_events],
        formal_evidence_chain={
            "enabled": True,
            "runtimeBinding": {
                "runtimeRequested": True,
                "runtimeLoaded": True,
                "strategyLoaded": True,
                "configLoaded": True,
                "dataRootValidated": True,
                "timerangeValidated": True,
                "networkAccessCount": 0,
                "lockedOosReadCount": 0,
                "runtimeHash": "runtime-hash",
            },
            "certification": {
                "status": "certified",
                "formalEvidenceChainCertificationHash": "certification-hash",
            },
        },
    )

    names = {path.name for path in (tmp_path / "v18-2-formal").iterdir()}
    assert {
        "canonical_event_identity_contract.json",
        "canonical_event_identity_mapping_audit.json",
        "canonical_event_identity_collision_audit.json",
        "formal_event_fold_assignment.json",
        "formal_event_fold_assignment.csv",
        "cross_fold_event_audit.json",
        "frozen_signal_ranking_evidence.parquet",
        "adapter_signal_ranking_evidence.parquet",
        "ranking_evidence_parity.json",
        "pit_portfolio_context.parquet",
        "adapter_pit_portfolio_context.parquet",
        "pit_context_parity.json",
        "capacity_data_semantics_by_symbol.json",
        "capacity_data_semantics_by_symbol.csv",
        "capacity_semantics_coverage.json",
        "funding_input_registry.json",
        "funding_input_coverage.json",
        "funding_stress_contract.json",
        "freqtrade_runtime_binding.json",
    } <= names
    identity = json.loads(
        (tmp_path / "v18-2-formal" / "canonical_event_identity_mapping_audit.json")
        .read_text(encoding="utf-8")
    )
    ranking = json.loads(
        (tmp_path / "v18-2-formal" / "ranking_evidence_parity.json").read_text(
            encoding="utf-8"
        )
    )
    pit = json.loads(
        (tmp_path / "v18-2-formal" / "pit_context_parity.json").read_text(
            encoding="utf-8"
        )
    )
    assert identity["mappingCompletenessPct"] == 100.0
    assert ranking["fieldParityPct"] == ranking["hashParityPct"] == 100.0
    assert pit["fieldParityPct"] == pit["hashParityPct"] == 100.0
    assert result["route"] != "implementation_invalid_requires_new_campaign"
    assert result["formalPass"] is False
    assert result["formalEvidenceCount"] == 0
    assert result["releaseCount"] == result["orderCount"] == 0

    v18_3_root = tmp_path / "v18-3-formal"
    v18_3_result = execute_v18_formal_campaign(
        bundle=v18_2_bundle,
        repo_root=tmp_path,
        output_root=v18_3_root,
        candidate_adapter=_SyntheticAdapter(),
        parity_runner=_parity_runner,
        raw_replay_runner=lambda **_: [dict(row) for row in raw_events],
        formal_evidence_chain={
            "enabled": True,
            "evidenceRecordVersion": "v18_3",
            "runtimeBinding": {
                "runtimeRequested": True,
                "runtimeLoaded": True,
                "strategyLoaded": True,
                "configLoaded": True,
                "dataRootValidated": True,
                "timerangeValidated": True,
                "networkAccessCount": 0,
                "lockedOosReadCount": 0,
                "runtimeHash": "runtime-hash",
            },
            "certification": {
                "status": "certified",
                "formalEvidenceChainCertificationHash": "certification-hash",
            },
        },
    )
    v18_3_names = {path.name for path in v18_3_root.iterdir()}
    assert {
        "formal_event_disposition_contract.json",
        "formal_event_disposition.parquet",
        "formal_event_disposition_sample.csv",
        "formal_event_disposition_audit.json",
        "formal_event_conservation_audit.json",
        "frozen_ranking_evidence.parquet",
        "adapter_ranking_evidence.parquet",
        "ranking_evidence_record_audit.json",
        "ranking_evidence_parity.json",
        "ranking_unavailable_reason_breakdown.json",
    } <= v18_3_names
    disposition_audit = json.loads(
        (v18_3_root / "formal_event_disposition_audit.json").read_text(
            encoding="utf-8"
        )
    )
    ranking_record_audit = json.loads(
        (v18_3_root / "ranking_evidence_record_audit.json").read_text(
            encoding="utf-8"
        )
    )
    assert disposition_audit["recordCoveragePct"] == 100.0
    assert disposition_audit["unclassifiedCount"] == 0
    assert ranking_record_audit["recordCoveragePct"] == 100.0
    assert ranking_record_audit["statusCoveragePct"] == 100.0
    assert v18_3_result["route"] != "implementation_invalid_requires_new_campaign"
    assert v18_3_result["formalEvidenceCount"] == 0
    assert v18_3_result["demoArm"] is False
    assert v18_3_result["orderCount"] == 0
