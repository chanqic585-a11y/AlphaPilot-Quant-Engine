from __future__ import annotations

import importlib.util
from pathlib import Path
import subprocess
import sys

import pandas as pd
import pytest

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.advisory_r_campaign.signals import _signal_series
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.formal_validation.phase1_contracts import (
    FORMAL_PREREGISTRATION_PATH,
    build_s01_formal_preregistration,
    verify_s01_formal_preregistration,
    write_s01_formal_preregistration,
)
from alphapilot.formal_validation.s01_freqtrade_translation import s01_entry_mask
from alphapilot.formal_validation.timerange_io_guard import build_formal_io_contract


REPO_ROOT = Path(__file__).resolve().parents[2]
S01_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"


def _s01_candidate() -> dict[str, object]:
    return next(row for row in build_candidate_inventory() if row["candidateId"] == S01_ID)


def test_s01_formal_preregistration_freezes_one_candidate_and_five_folds() -> None:
    payload = build_s01_formal_preregistration(REPO_ROOT)

    assert payload["sourceCandidateId"] == S01_ID
    assert payload["candidateCount"] == 1
    assert payload["parameterChanges"] == 0
    assert payload["exitPolicyChanges"] == 0
    assert payload["universeChanges"] == 0
    assert payload["costChanges"] == 0
    assert payload["coreUniverse"]["instrumentCount"] == 20
    assert payload["splitPolicy"]["foldCount"] == 5
    assert len(payload["splitPolicy"]["folds"]) == 5
    assert payload["purgeBars"] >= 24
    assert payload["embargoBars"] >= 24
    assert payload["capitalCompetitionPolicy"]["duplicateSymbolPolicy"] == "reject_while_open"
    assert payload["lockedOosPolicy"]["contentRead"] is False
    assert payload["lockedOosPolicy"]["formalWalkForwardMayRunWithoutCleanHoldout"] is True
    assert payload["lockedOosPolicy"]["admissionRequiresCleanHoldout"] is True

    core = {key: value for key, value in payload.items() if key != "preregistrationHash"}
    assert payload["preregistrationHash"] == stable_hash(
        core, prefix="s01_formal_walk_forward_preregistration"
    )
    assert verify_s01_formal_preregistration(payload) is True


def test_s01_formal_preregistration_writer_uses_frozen_path(tmp_path: Path) -> None:
    payload = build_s01_formal_preregistration(REPO_ROOT)

    path = write_s01_formal_preregistration(payload, tmp_path)

    assert path.relative_to(tmp_path) == FORMAL_PREREGISTRATION_PATH
    assert path.is_file()


def test_timerange_guard_separates_data_outputs_and_locked_oos(tmp_path: Path) -> None:
    input_root = tmp_path / "data"
    input_root.mkdir()
    input_path = input_root / "market.parquet"
    input_path.write_bytes(b"immutable-market-data")

    contract = build_formal_io_contract(
        input_root=input_root,
        input_paths=[input_path],
        output_root=tmp_path / "reports" / "formal",
        requested_start="2021-01-22T04:00:00Z",
        requested_end="2026-05-15T04:00:00Z",
        allowed_start="2021-01-22T04:00:00Z",
        allowed_end="2026-05-15T04:00:00Z",
        forbidden_roots=[tmp_path / "locked_oos_content"],
    )

    assert contract["status"] == "ready"
    assert contract["inputCount"] == 1
    assert contract["outputIsolated"] is True
    assert len(contract["contractHash"]) == 64

    with pytest.raises(ValueError, match="output_root must be outside input_root"):
        build_formal_io_contract(
            input_root=input_root,
            input_paths=[input_path],
            output_root=input_root / "results",
            requested_start="2021-01-22T04:00:00Z",
            requested_end="2026-05-15T04:00:00Z",
            allowed_start="2021-01-22T04:00:00Z",
            allowed_end="2026-05-15T04:00:00Z",
        )

    with pytest.raises(ValueError, match="requested timerange exceeds frozen boundary"):
        build_formal_io_contract(
            input_root=input_root,
            input_paths=[input_path],
            output_root=tmp_path / "reports" / "late",
            requested_start="2021-01-22T04:00:00Z",
            requested_end="2026-05-15T08:00:00Z",
            allowed_start="2021-01-22T04:00:00Z",
            allowed_end="2026-05-15T04:00:00Z",
        )


def test_s01_pure_translation_matches_formal_event_engine() -> None:
    candidate = _s01_candidate()
    dates = pd.date_range("2024-01-01", periods=260, freq="4h", tz="UTC")
    market_close = pd.Series(100.0 + pd.Series(range(260), dtype="float64") * 0.02, index=dates)
    btc_close = pd.Series(150.0 - pd.Series(range(260), dtype="float64") * 0.12, index=dates)
    pair_close = market_close.copy()
    pair_close.iloc[220:223] = [88.0, 91.0, 95.0]
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": pair_close.to_numpy(),
            "high": pair_close.to_numpy() + 1.0,
            "low": pair_close.to_numpy() - 1.0,
            "close": pair_close.to_numpy(),
            "volume": 1000.0,
        }
    )

    formal = _signal_series(
        candidate,
        frame,
        btc_close=btc_close,
        market_close=market_close,
    ).eq(1)
    translated = s01_entry_mask(
        frame=frame,
        btc_close=btc_close,
        market_close=market_close,
        feature_definition=candidate["featureDefinition"],
        entry_definition=candidate["entryDefinition"],
    )

    pd.testing.assert_series_equal(translated.reset_index(drop=True), formal.reset_index(drop=True))


def test_freqtrade_adapter_is_research_only_and_bound_to_s01() -> None:
    path = REPO_ROOT / "user_data" / "strategies" / "AlphaPilotS01BearRecovery4H.py"
    spec = importlib.util.spec_from_file_location("alphapilot_s01_freqtrade", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    strategy = module.AlphaPilotS01BearRecovery4H
    assert strategy.candidate_id == S01_ID
    assert strategy.timeframe == "4h"
    assert strategy.strategy_status == "formal_research_only"
    assert strategy.dry_run_approved is False
    assert strategy.live_trading_approved is False


def test_phase1_command_entrypoints_exist() -> None:
    assert (REPO_ROOT / "scripts" / "generate_s01_formal_preregistration.py").is_file()
    assert (REPO_ROOT / "scripts" / "validate_formal_timerange.py").is_file()


@pytest.mark.parametrize(
    "script_name",
    [
        "generate_s01_formal_preregistration.py",
        "validate_formal_timerange.py",
    ],
)
def test_phase1_command_entrypoints_run_directly(script_name: str) -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / script_name), "--help"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "ModuleNotFoundError" not in result.stderr
