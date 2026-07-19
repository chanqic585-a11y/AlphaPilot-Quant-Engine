from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from alphapilot.formal_validation.candidate_adapters import get_candidate_adapter
from alphapilot.formal_validation.executable_capital_policy import (
    build_capital_policy_v2,
)
from alphapilot.formal_validation.formal_input import FormalInputBundle
from alphapilot.formal_validation.v18_formal_reporting import (
    execute_v18_formal_campaign,
)
from alphapilot.standard_replication.tsmom_engine import (
    SELECTED_TSMOM_TRIALS,
    build_tsmom_candidate_spec,
)


def _frames() -> dict[str, pd.DataFrame]:
    dates = pd.date_range("2021-01-01", periods=520, freq="1D", tz="UTC")
    close = np.concatenate(
        (
            100.0 + np.sin(np.arange(220) / 9.0),
            np.linspace(132.0, 185.0, 120),
            np.linspace(108.0, 68.0, 180),
        )
    )
    result: dict[str, pd.DataFrame] = {}
    for offset, symbol in enumerate(
        ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
    ):
        scaled = close * (1.0 + offset * 0.04)
        frame = pd.DataFrame(
            {
                "date": dates,
                "open": np.roll(scaled, 1),
                "high": scaled * 1.002,
                "low": scaled * 0.998,
                "close": scaled,
                "volume": np.full(len(dates), 10_000_000.0 + offset),
                "funding_rate": np.zeros(len(dates)),
            }
        )
        frame.loc[0, "open"] = scaled[0]
        result[symbol] = frame
    return result


def _bundle(repo_root: Path) -> tuple[FormalInputBundle, object]:
    candidate_id = "v35_tsmom_crypto_adaptation"
    adapter = get_candidate_adapter(candidate_id)
    candidate_spec = build_tsmom_candidate_spec(candidate_id)
    candidate = adapter.resolve_candidate(
        repo_root=repo_root,
        preregistration={
            "sourceCandidateId": candidate_id,
            "selectedTrialId": SELECTED_TSMOM_TRIALS[candidate_id],
            "strategyDefinitionHash": candidate_spec["strategyDefinitionHash"],
            "exitPolicyHash": candidate_spec["exitPolicyHash"],
        },
    )
    frames = _frames()
    common_index = pd.DatetimeIndex(frames["BTC-USDT-SWAP"]["date"])
    preregistration = {
        "campaignId": "v36-tsmom-executor-contract-fixture",
        "sourceCandidateId": candidate_id,
        "selectedTrialId": SELECTED_TSMOM_TRIALS[candidate_id],
        "strategyDefinitionHash": candidate["strategyDefinitionHash"],
        "exitPolicyHash": candidate["exitPolicyHash"],
        "splitPolicy": {
            "commonStart": common_index[0].isoformat(),
            "commonCutoffExclusive": (common_index[-1] + pd.Timedelta(days=1)).isoformat(),
            "folds": [
                {
                    "foldId": "contract_fold",
                    "testStart": 200,
                    "testEndExclusive": 520,
                }
            ],
        },
        "capitalCompetitionPolicy": build_capital_policy_v2(),
        "costModel": {
            "baseRoundTripCostRate": 0.001,
            "historicalFundingMissingValue": None,
            "missingFundingMayBeFilledWithZero": False,
            "scenarios": [
                {"scenarioId": "base", "multiplier": 1.0},
                {"scenarioId": "cost_1_5x", "multiplier": 1.5},
                {"scenarioId": "cost_2_0x", "multiplier": 2.0},
            ],
        },
        "benchmarkPolicy": {"holdBars": 12},
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
                "maximumSingleMonthPositiveContribution": 1.0,
                "maximumSingleSymbolPositiveContribution": 1.0,
                "requiresCleanLockedOosForAdmission": True,
            },
        },
        "statisticalPolicy": {
            "neweyWest": {"maximumLagDays": 5, "oneSided": True},
            "comparableCandidatePanel": {
                "status": "unavailable_predeclared",
                "retroactiveConstructionAllowed": False,
                "decisionPolicy": "walk_forward_research_pass_statistics_unavailable",
            },
        },
        "stoppingRules": {
            "economicGateFailure": "archive_current_version",
            "implementationInvalid": "implementation_invalid_requires_new_campaign",
            "statisticsUnavailable": "walk_forward_research_pass_statistics_unavailable",
        },
        "lockedOosPolicy": {
            "contentRead": False,
            "accessCount": 0,
            "cleanLockedOosAvailable": False,
        },
    }
    return (
        FormalInputBundle(
            preregistration=preregistration,
            candidate=candidate,
            snapshot={"snapshotId": "v36-contract-snapshot"},
            frames=frames,
            commonIndex=common_index,
            inputMapping={"schemaVersion": "v36-contract-fixture", "verifiedPartitionCount": 3},
            holdoutLineage={"contentRead": False, "lockedOosAccessCount": 0},
        ),
        adapter,
    )


def test_tsmom_adapter_executes_through_the_complete_generic_formal_core(
    tmp_path: Path,
) -> None:
    bundle, adapter = _bundle(tmp_path)

    result = execute_v18_formal_campaign(
        bundle=bundle,
        repo_root=tmp_path,
        output_root=tmp_path / "formal",
        candidate_adapter=adapter,
    )

    manifest = json.loads(
        (tmp_path / "formal" / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert result["resultManifestHash"] == manifest["resultManifestHash"]
    assert manifest["candidateId"] == "v35_tsmom_crypto_adaptation"
    assert result["lockedOosAccessCount"] == 0
    assert result["releaseCount"] == 0
    assert result["demoArm"] is False
    assert result["orderCount"] == 0
