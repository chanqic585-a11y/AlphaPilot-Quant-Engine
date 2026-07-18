from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from alphapilot.formal_validation.freqtrade_runtime import PINNED_FREQTRADE_IMAGE
from alphapilot.formal_validation.freqtrade_runtime_guard import guard_runtime
from alphapilot.formal_validation.freqtrade_runtime_loader import (
    FreqtradeRuntimeRequest,
    FreqtradeRuntimeUnavailable,
    load_freqtrade_runtime,
)


def _request(tmp_path: Path) -> FreqtradeRuntimeRequest:
    config = tmp_path / "config.json"
    config.write_text("{}", encoding="utf-8")
    data = tmp_path / "data"
    data.mkdir()
    return FreqtradeRuntimeRequest(
        image_reference=PINNED_FREQTRADE_IMAGE,
        strategy_module="user_data.strategies.AlphaPilotS01BearRecovery4H",
        strategy_class="AlphaPilotS01BearRecovery4H",
        config_path=config,
        data_root=data,
        timerange="20240101-20260101",
    )


def test_exact_runtime_loads_and_binds_all_frozen_fields(tmp_path: Path) -> None:
    observed = {
        "pythonVersion": "3.14.6",
        "freqtradeVersion": "2026.6",
        "ccxtVersion": "4.5.61",
        "pandasVersion": "3.0.3",
        "numpyVersion": "2.4.6",
        "pyarrowVersion": "24.0.0",
        "strategyClass": "AlphaPilotS01BearRecovery4H",
        "strategyBase": "freqtrade.strategy.interface",
        "exitHooksLoaded": True,
    }

    def runner(*_: object, **__: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=0, stdout=json.dumps(observed), stderr="")

    report = load_freqtrade_runtime(
        _request(tmp_path), repo_root=Path(__file__).resolve().parents[2], runner=runner
    )
    guard = guard_runtime(report)

    assert report["runtimeRequested"] is True
    assert report["runtimeLoaded"] is True
    assert report["networkAccessCount"] == 0
    assert report["lockedOosReadCount"] == 0
    assert report["timezone"] == "UTC"
    assert report["runtimeHash"]
    assert guard["status"] == "certified"


def test_missing_runtime_fails_closed_without_fallback(tmp_path: Path) -> None:
    def runner(*_: object, **__: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=125, stdout="", stderr="image missing")

    with pytest.raises(FreqtradeRuntimeUnavailable, match="blocked_freqtrade_runtime"):
        load_freqtrade_runtime(
            _request(tmp_path), repo_root=tmp_path, runner=runner
        )
