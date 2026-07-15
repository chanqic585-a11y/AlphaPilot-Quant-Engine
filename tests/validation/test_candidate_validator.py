from __future__ import annotations

from alphapilot.validation.candidate_validator import (
    benjamini_hochberg,
    contribution_concentration,
    effective_sample_size,
    sample_assessment,
    validate_candidate,
)


def test_effective_sample_size_penalizes_positive_serial_correlation() -> None:
    independent = effective_sample_size([1.0, -1.0, 1.0, -1.0, 1.0, -1.0])
    clustered = effective_sample_size([1.0, 1.0, 1.0, -1.0, -1.0, -1.0])

    assert independent["effectiveTradeCount"] == 6
    assert clustered["effectiveTradeCount"] < 6


def test_one_day_exploratory_range_never_satisfies_hard_sample_gate() -> None:
    result = sample_assessment(
        timeframe="1d",
        trade_count=42,
        effective_trade_count=42,
        duration_days=400,
        threshold={
            "minimumDurationDays": 365,
            "minimumEffectiveTrades": 50,
            "exploratoryTradeRange": [30, 49],
        },
    )

    assert result["exploratoryOnly"] is True
    assert result["passed"] is False


def test_contribution_concentration_uses_positive_contributions_only() -> None:
    result = contribution_concentration(
        {
            "BTC": {"totalNetR": 6.0},
            "ETH": {"totalNetR": 3.0},
            "SOL": {"totalNetR": -20.0},
        }
    )

    assert result["largestPositiveContributionShare"] == 2 / 3
    assert result["largestPositiveContributor"] == "BTC"


def test_benjamini_hochberg_is_monotonic_and_never_below_raw_p() -> None:
    adjusted = benjamini_hochberg({"a": 0.01, "b": 0.04, "c": 0.03})

    assert set(adjusted) == {"a", "b", "c"}
    assert all(adjusted[key] >= raw for key, raw in {"a": 0.01, "b": 0.04, "c": 0.03}.items())
    assert adjusted["a"] <= adjusted["c"] <= adjusted["b"]


def _trade(index: int, net_r: float, *, split: str, fold: int | None = None) -> dict:
    gross_r = net_r + 0.10
    return {
        "instrumentId": "BTC-USDT-SWAP" if index % 2 == 0 else "ETH-USDT-SWAP",
        "direction": "long",
        "entryTimestampMs": index * 86_400_000,
        "exitTimestampMs": index * 86_400_000 + 3_600_000,
        "entryReferencePrice": 100.0,
        "exitReferencePrice": 101.0,
        "grossR": gross_r,
        "feeR": 0.05,
        "slippageR": 0.05,
        "fundingR": 0.0,
        "netR": net_r,
        "mfeR": max(net_r, 0.0) + 0.5,
        "maeR": min(net_r, 0.0) - 0.25,
        "regime": "trend",
        "setupName": "synthetic",
        "exitReason": "target" if net_r > 0 else "stop",
        "split": split,
        "fold": fold,
    }


def _preregistration(candidate: dict) -> dict:
    return {
        "candidates": [candidate],
        "primaryRiskModelId": "model_1",
        "sensitivityRiskModelIds": ["model_2", "model_3"],
        "riskModels": {
            "model_1": {"role": "primary_acceptance", "riskPerTradePct": 0.25},
            "model_2": {"role": "sensitivity_only", "riskPerTradePct": 0.5},
            "model_3": {"role": "sensitivity_only", "riskPerTradePct": 0.25},
        },
        "costModel": {"stressMultipliers": [1.0, 1.5, 2.0]},
        "sampleThresholds": {
            "1h": {"minimumDurationDays": 1, "minimumEffectiveTrades": 2},
            "15m": {"minimumDurationDays": 1, "minimumEffectiveTrades": 2},
        },
        "passThresholds": {
            "signal": {
                "profitFactor": 1.10,
                "averageNetR": 0.05,
                "probabilityAverageNetRPositive": 0.50,
                "positiveAverageRWalkForwardRatio": 0.50,
            },
            "locked": {
                "profitFactorExclusive": 1.0,
                "averageNetRExclusive": 0.0,
                "totalRExclusive": 0.0,
            },
            "costStress": {"multiplier": 1.5, "profitFactor": 1.0, "averageNetR": 0.0},
            "stability": {
                "maximumSingleSymbolPositiveContribution": 1.0,
                "maximumSingleMonthPositiveContribution": 1.0,
                "minimumPositiveWalkForwardWindows": 2,
            },
            "primaryRisk": {
                "historicalMaximumDrawdownPct": 15.0,
                "monteCarlo95MaximumDrawdownPct": 25.0,
            },
        },
        "resourceLimits": {"bootstrapDraws": 100, "monteCarloDraws": 100},
        "seedRegistry": {"bootstrap": 11, "monteCarlo": 17},
    }


def test_contaminated_locked_evidence_remains_diagnostic_only() -> None:
    candidate = {
        "strategyVersionId": "candidate-a",
        "strategyFamily": "family-a",
        "displayLabelZh": "测试候选",
        "tier": "A",
        "timeframe": "1h",
        "direction": "long",
        "historicalPrefilter": {"required": False, "passed": False},
    }
    trades = [
        *[_trade(i, 1.0 if i % 3 else -0.5, split="development") for i in range(4)],
        *[_trade(i + 10, 1.0 if i % 3 else -0.5, split="walk_forward", fold=i % 2) for i in range(4)],
        *[_trade(i + 20, 1.0 if i % 3 else -0.5, split="locked_oos") for i in range(4)],
    ]
    evidence = {
        "signalReproducible": True,
        "cleanLockedSampleAvailable": False,
        "lockedSampleStatus": "无污染锁定样本不可用",
        "historicalPointInTimeUniverse": False,
        "diagnosticReplayOnly": True,
        "trades": trades,
        "manifests": {"walk-forward.json": {"folds": [{}, {}]}},
    }

    result = validate_candidate(
        candidate,
        evidence,
        _preregistration(candidate),
        candidate_index=0,
    )

    assert result["decision"]["status"] == "locked_sample_unavailable"
    assert result["decision"]["hardPass"] is False
    assert result["lockedSample"]["diagnosticOnly"] is True
    assert result["executionEligibility"]["executionEligible"] is False


def test_tier_c_prefilter_stops_thin_edge_before_expensive_layers() -> None:
    candidate = {
        "strategyVersionId": "candidate-c",
        "strategyFamily": "family-c",
        "displayLabelZh": "薄边候选",
        "tier": "C",
        "timeframe": "15m",
        "direction": "short",
        "historicalPrefilter": {
            "required": True,
            "passed": False,
            "profitFactor": 1.01,
            "averageNetR": 0.01,
            "tradeCount": 200,
        },
    }
    evidence = {
        "signalReproducible": True,
        "cleanLockedSampleAvailable": False,
        "lockedSampleStatus": "无污染锁定样本不可用",
        "historicalPointInTimeUniverse": False,
        "diagnosticReplayOnly": True,
        "trades": [_trade(0, 0.01, split="locked_oos")],
        "manifests": {"walk-forward.json": {"folds": []}},
    }

    result = validate_candidate(
        candidate,
        evidence,
        _preregistration(candidate),
        candidate_index=1,
    )

    assert result["decision"]["status"] == "prefilter_stopped"
    assert result["fullValidationExecuted"] is False
    assert result["monteCarlo"] is None
