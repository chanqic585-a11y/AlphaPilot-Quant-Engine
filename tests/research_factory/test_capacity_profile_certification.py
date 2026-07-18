from __future__ import annotations

import pandas as pd

from alphapilot.research_factory.capacity_profile_certification import (
    certify_real_signal_capacity,
)
from alphapilot.research_factory.data_capability import (
    build_capacity_data_capability,
)
from alphapilot.research_factory.data_profiles import (
    build_verified_capacity_profile,
)


def _audit() -> dict[str, object]:
    records = []
    for symbol in ("BTC-USDT-SWAP", "ETH-USDT-SWAP"):
        for timeframe in ("1h", "4h", "1d"):
            records.append(
                {
                    "datasetId": f"{symbol}_{timeframe}",
                    "instrumentId": symbol,
                    "timeframe": timeframe,
                    "rowCount": 20_000,
                    "contentHash": f"hash-{symbol}-{timeframe}",
                    "sourceExchange": "unverified_local_exchange",
                    "marketType": "swap",
                    "selectedVolumeColumn": "volume_quote_currency",
                    "declaredVolumeUnit": "quote_asset",
                    "start": "2020-01-01T00:00:00Z",
                    "end": "2026-01-01T00:00:00Z",
                    "availableAtRule": "candle_close_timestamp",
                    "volumeSemantics": {
                        "status": "verified",
                        "route": "A",
                        "semanticType": "exact_quote_turnover",
                        "verificationHash": f"verification-{symbol}-{timeframe}",
                    },
                }
            )
    return {"records": records, "auditHash": "audit-hash"}


def test_verified_capacity_profile_is_data_only_and_ready() -> None:
    audit = _audit()
    capability = build_capacity_data_capability(audit)
    profile = build_verified_capacity_profile(
        volume_audit=audit,
        capacity_capability=capability,
        required_timeframes=["1h", "4h", "1d"],
        minimum_history_rows=10_000,
        required_instruments=["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
    )

    assert profile["profileId"] == "ohlcv_verified_capacity_v2"
    assert profile["status"] == "ready"
    assert profile["eligibleInstruments"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    assert profile["selectionUsesEconomicResults"] is False
    assert profile["sourceExchange"] == "unverified_local_exchange"
    assert profile["marketType"] == "swap"
    assert profile["instrumentSet"] == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    assert profile["timeframes"] == ["1d", "1h", "4h"]
    assert profile["commonCutoff"] == {
        "start": "2020-01-01T00:00:00Z",
        "end": "2026-01-01T00:00:00Z",
    }
    assert profile["turnoverField"] == "volume_quote_currency"
    assert profile["turnoverUnit"] == "quote_asset"
    assert profile["availableAt"] == "candle_close_timestamp"
    assert profile["minimumLookback"] == {"unit": "rows", "value": 10_000}
    assert profile["coverageByInstrument"]["BTC-USDT-SWAP"]["4h"] == {
        "rowCount": 20_000,
        "start": "2020-01-01T00:00:00Z",
        "end": "2026-01-01T00:00:00Z",
        "contentHash": "hash-BTC-USDT-SWAP-4h",
    }
    assert profile["profileHash"].startswith("data_profile_")


class _SignalOnlyAdapter:
    def load_signals(self, *, candidate, frames):
        del candidate
        return [
            {
                "signalId": "signal-1",
                "symbol": "BTC-USDT-SWAP",
                "direction": "short",
                "signalTimestamp": frames["BTC-USDT-SWAP"].iloc[200]["date"].isoformat(),
                "entryTimestamp": frames["BTC-USDT-SWAP"].iloc[201]["date"].isoformat(),
                "entryPrice": float(frames["BTC-USDT-SWAP"].iloc[201]["open"]),
                "signalBarIndex": 200,
            }
        ]

    def replay(self, **kwargs):  # pragma: no cover - a call is a contract violation
        raise AssertionError(f"economic replay must not be called: {kwargs}")


def test_real_signal_certification_reads_no_pnl_exit_or_statistics() -> None:
    dates = pd.date_range("2023-01-01", periods=220, freq="4h", tz="UTC")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [100.0 + index * 0.1 for index in range(220)],
            "high": [101.0 + index * 0.1 for index in range(220)],
            "low": [99.0 + index * 0.1 for index in range(220)],
            "close": [100.2 + index * 0.1 for index in range(220)],
            "volume": [10_000_000.0] * 220,
        }
    )
    report = certify_real_signal_capacity(
        adapter=_SignalOnlyAdapter(),
        candidate={
            "candidateId": "candidate-1",
            "direction": "short",
            "timeframe": "4h",
            "initialStop": {"atrPeriod": 14, "atrMultiple": 1.25},
        },
        frames={"BTC-USDT-SWAP": frame},
        capacity_profile={
            "profileId": "ohlcv_verified_capacity_v2",
            "profileHash": "data_profile_ready",
            "status": "ready",
            "eligibleInstruments": ["BTC-USDT-SWAP"],
            "turnoverSemanticsByInstrument": {
                "BTC-USDT-SWAP": {
                    "4h": {"semanticType": "exact_quote_turnover", "route": "A"}
                }
            },
        },
        current_equity=10_000.0,
    )

    assert report["rawSignalCount"] == 1
    assert report["assignedEventCount"] == 1
    assert report["capacityInputAvailableCount"] == 1
    assert report["capacityCalculationCount"] == 1
    assert report["capacityPassCount"] == 1
    assert report["economicResultReadCount"] == 0
    assert report["exitResultReadCount"] == 0
    assert report["statisticalResultReadCount"] == 0
    assert report["certificationStatus"] == "passed"


class _WindowedSignalAdapter:
    def load_signals(self, *, candidate, frames):
        del candidate
        frame = frames["BTC-USDT-SWAP"]
        return [
            {
                "signalId": "before-window",
                "symbol": "BTC-USDT-SWAP",
                "direction": "short",
                "signalTimestamp": frame.iloc[100]["date"].isoformat(),
                "entryTimestamp": frame.iloc[101]["date"].isoformat(),
                "entryPrice": float(frame.iloc[101]["open"]),
                "signalBarIndex": 100,
            },
            {
                "signalId": "inside-window",
                "symbol": "BTC-USDT-SWAP",
                "direction": "short",
                "signalTimestamp": frame.iloc[200]["date"].isoformat(),
                "entryTimestamp": frame.iloc[201]["date"].isoformat(),
                "entryPrice": float(frame.iloc[201]["open"]),
                "signalBarIndex": 200,
            },
        ]


def test_capacity_certification_filters_to_frozen_formal_window() -> None:
    dates = pd.date_range("2022-12-01", periods=240, freq="4h", tz="UTC")
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": [100.0] * len(dates),
            "high": [101.0] * len(dates),
            "low": [99.0] * len(dates),
            "close": [100.2] * len(dates),
            "volume": [10_000_000.0] * len(dates),
        }
    )
    report = certify_real_signal_capacity(
        adapter=_WindowedSignalAdapter(),
        candidate={
            "candidateId": "candidate-windowed",
            "direction": "short",
            "timeframe": "4h",
            "initialStop": {"atrPeriod": 14, "atrMultiple": 1.25},
        },
        frames={"BTC-USDT-SWAP": frame},
        capacity_profile={
            "profileId": "ohlcv_verified_capacity_v2",
            "profileHash": "data_profile_ready",
            "status": "ready",
            "eligibleInstruments": ["BTC-USDT-SWAP"],
            "turnoverSemanticsByInstrument": {
                "BTC-USDT-SWAP": {
                    "4h": {"semanticType": "exact_quote_turnover", "route": "A"}
                }
            },
        },
        current_equity=10_000.0,
        signal_start="2023-01-01T00:00:00Z",
        signal_end_exclusive="2023-02-01T00:00:00Z",
    )

    assert report["unfilteredSignalCount"] == 2
    assert report["rawSignalCount"] == 1
    assert report["evidence"][0]["signalId"] == "inside-window"
    assert report["signalWindow"] == {
        "start": "2023-01-01T00:00:00Z",
        "endExclusive": "2023-02-01T00:00:00Z",
    }
