from __future__ import annotations

import pytest

from alphapilot.validation.hashing import stable_hash
from alphapilot.validation.signal_freezer import (
    SignalDefinitionUnreproducible,
    freeze_signal_definition,
)


def test_stable_hash_is_key_order_independent() -> None:
    assert stable_hash({"b": 2, "a": [1, 3]}) == stable_hash(
        {"a": [1, 3], "b": 2}
    )


def test_signal_hash_is_stable_and_freezes_signal_fields() -> None:
    definition = {
        "signalEngine": "short_cycle_v1",
        "timeframe": "1h",
        "direction": "long",
        "signalWindow": 20,
        "universeRule": "registered_snapshot",
        "entryRule": {"kind": "sweep_reclaim", "threshold": 1.2},
        "signalExitRule": {"kind": "fixed_horizon", "bars": 8},
    }

    first = freeze_signal_definition("v1", definition)
    second = freeze_signal_definition("v1", dict(reversed(list(definition.items()))))

    assert first.signal_frozen is True
    assert first.signal_definition_hash == second.signal_definition_hash
    assert first.frozen_definition["entryRule"]["threshold"] == 1.2


def test_missing_executable_signal_engine_is_not_inferred_from_name() -> None:
    with pytest.raises(SignalDefinitionUnreproducible):
        freeze_signal_definition(
            "v1",
            {
                "strategyName": "1H sweep reclaim",
                "timeframe": "1h",
                "direction": "long",
            },
        )


def test_registered_forward_signal_parameters_are_a_reproducible_entry_rule() -> None:
    definition = {
        "signalEngine": "short_cycle_v1",
        "signalFamily": "windowed_breakout_retest_long",
        "timeframe": "1d",
        "direction": "long",
        "forwardSignalPolicy": {
            "signalFamily": "windowed_breakout_retest_long",
            "parameters": {"lookback": 30, "breakout_buffer": 0.001},
        },
        "universePolicy": "point_in_time_dynamic_liquid_usdt_swap",
        "targetR": 2.0,
    }

    frozen = freeze_signal_definition("v-registered", definition)

    assert frozen.signal_frozen is True
    assert frozen.frozen_definition["forwardSignalPolicy"]["parameters"]["lookback"] == 30


def test_research_metadata_does_not_change_signal_identity() -> None:
    base = {
        "signalEngine": "short_cycle_v1",
        "signalFamily": "windowed_breakout_retest_long",
        "timeframe": "1h",
        "direction": "long",
        "forwardSignalPolicy": {
            "parameters": {"lookback": 48, "stop_atr": 1.2},
        },
        "targetR": 2.0,
    }
    first = freeze_signal_definition("v1", {**base, "researchPack": "pack_a"})
    second = freeze_signal_definition("v2", {**base, "researchPack": "pack_b"})

    assert first.strategy_definition_hash != second.strategy_definition_hash
    assert first.signal_definition_hash == second.signal_definition_hash
