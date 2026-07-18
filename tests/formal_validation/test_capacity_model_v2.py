from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from alphapilot.formal_validation.capacity_model import evaluate_capacity_v1


def _daily_rows(*, quote_volume: float | None = 10_000_000.0) -> list[dict[str, object]]:
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows: list[dict[str, object]] = []
    for offset in range(30):
        row: dict[str, object] = {
            "timestamp": (start + timedelta(days=offset)).isoformat(),
            "close": 100.0,
        }
        if quote_volume is not None:
            row["quoteVolume"] = quote_volume
        rows.append(row)
    return rows


def test_capacity_uses_prior_quote_turnover_and_risk_based_size() -> None:
    result = evaluate_capacity_v1(
        current_equity=10_000.0,
        entry_price=100.0,
        stop_price=95.0,
        entry_timestamp="2026-02-01T00:00:00Z",
        daily_liquidity=_daily_rows(),
        instrument_meta={
            "quantityStep": 0.1,
            "minimumQuantity": 0.1,
            "minimumNotional": 10.0,
        },
    )

    assert result["capacityPassed"] is True
    assert result["liquiditySource"] == "quote_volume"
    assert result["observationCount"] == 30
    assert result["riskBudget"] == pytest.approx(100.0)
    assert result["stopDistancePct"] == pytest.approx(0.05)
    assert result["riskBasedNotional"] == pytest.approx(2_000.0)
    assert result["capacityNotional"] == pytest.approx(5_000.0)
    assert result["actualNotional"] == pytest.approx(2_000.0)
    assert result["riskUtilization"] == pytest.approx(1.0)
    assert result["quantity"] == pytest.approx(20.0)
    assert result["lookaheadReadCount"] == 0


def test_capacity_rejects_low_utilization_and_current_day_data() -> None:
    rows = _daily_rows(quote_volume=1_000_000.0)
    rows.append(
        {
            "timestamp": "2026-02-01T12:00:00Z",
            "close": 100.0,
            "quoteVolume": 1_000_000_000.0,
        }
    )

    result = evaluate_capacity_v1(
        current_equity=10_000.0,
        entry_price=100.0,
        stop_price=95.0,
        entry_timestamp="2026-02-01T13:00:00Z",
        daily_liquidity=rows,
        instrument_meta={"quantityStep": 0.1, "minimumQuantity": 0.1},
    )

    assert result["capacityPassed"] is False
    assert result["reason"] == "risk_utilization_below_minimum"
    assert result["observationCount"] == 30
    assert result["capacityNotional"] == pytest.approx(500.0)
    assert result["riskUtilization"] == pytest.approx(0.25)


def test_capacity_derives_contract_turnover_only_with_verified_metadata() -> None:
    rows = _daily_rows(quote_volume=None)
    for row in rows:
        row["contractVolume"] = 10_000_000.0

    rejected = evaluate_capacity_v1(
        current_equity=10_000.0,
        entry_price=100.0,
        stop_price=95.0,
        entry_timestamp="2026-02-01T00:00:00Z",
        daily_liquidity=rows,
        instrument_meta={"quantityStep": 0.1},
    )
    accepted = evaluate_capacity_v1(
        current_equity=10_000.0,
        entry_price=100.0,
        stop_price=95.0,
        entry_timestamp="2026-02-01T00:00:00Z",
        daily_liquidity=rows,
        instrument_meta={
            "quantityStep": 0.1,
            "minimumQuantity": 0.1,
            "contractValue": 0.01,
            "contractMultiplier": 1.0,
            "contractVolumeSemanticsVerified": True,
        },
    )

    assert rejected["capacityPassed"] is False
    assert rejected["reason"] == "liquidity_semantics_unverified"
    assert accepted["capacityPassed"] is True
    assert accepted["liquiditySource"] == "contract_volume_derived_quote"


def test_formal_quote_turnover_uses_continuous_research_notional_without_lot_metadata() -> None:
    result = evaluate_capacity_v1(
        current_equity=10_000.0,
        entry_price=103.0,
        stop_price=97.0,
        entry_timestamp="2026-02-01T00:00:00Z",
        daily_liquidity=_daily_rows(),
        instrument_meta={},
    )

    expected_risk_notional = 100.0 / (6.0 / 103.0)
    assert result["capacityPassed"] is True
    assert result["actualNotional"] == pytest.approx(expected_risk_notional)
    assert result["quantity"] == pytest.approx(expected_risk_notional / 103.0)
    assert result["positionSizingMode"] == "continuous_research_notional"
