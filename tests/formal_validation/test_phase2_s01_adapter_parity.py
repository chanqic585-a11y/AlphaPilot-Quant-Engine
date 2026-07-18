from __future__ import annotations

from pathlib import Path

from alphapilot.formal_validation.s01_dual_engine_audit import (
    FROZEN_S01_INSTRUMENT_IDS,
    build_s01_synthetic_fixture,
    run_s01_synthetic_parity,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_synthetic_fixture_is_full_universe_and_has_real_signal() -> None:
    frames = build_s01_synthetic_fixture()

    assert tuple(sorted(frames)) == FROZEN_S01_INSTRUMENT_IDS
    assert len(frames) == 20
    assert all(len(frame) == 280 for frame in frames.values())


def test_actual_s01_adapter_matches_formal_events_and_exit_legs() -> None:
    report = run_s01_synthetic_parity(REPO_ROOT)

    assert report["status"] == "passed"
    assert report["actualStrategyAdapterInvoked"] is True
    assert report["frozenUniverseCount"] == 20
    assert report["formalSignalCount"] == 1
    assert report["adapterSignalCount"] == 1
    assert report["referenceEventCount"] == 1
    assert report["implementationEventCount"] == 1
    assert report["matchedEventCount"] == 1
    assert report["matchedLegCount"] == 2
    assert report["coveredExitReasons"] == ["partial_gap", "structure_exit"]
    assert report["lockedOosAccessCount"] == 0
    assert report["credentialReadCount"] == 0


def test_adapter_uses_frozen_universe_instead_of_runtime_whitelist() -> None:
    report = run_s01_synthetic_parity(REPO_ROOT)

    assert report["runtimeWhitelistIgnored"] is True
    assert report["adapterContextPairs"] == list(FROZEN_S01_INSTRUMENT_IDS)
