from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .hashing import stable_hash


class SignalDefinitionUnreproducible(ValueError):
    """Raised when an archived signal cannot be reproduced without guessing."""


@dataclass(frozen=True)
class FrozenSignalDefinition:
    strategy_version_id: str
    signal_frozen: bool
    strategy_definition_hash: str
    signal_definition_hash: str
    frozen_definition: dict[str, Any]


_SIGNAL_FIELDS = (
    "signalEngine",
    "signalFamily",
    "timeframe",
    "direction",
    "signalWindow",
    "indicators",
    "thresholds",
    "universeRule",
    "entryRule",
    "signalExitRule",
    "exitPolicy",
    "targetR",
    "universePolicy",
)


def _canonical_signal_payload(definition: Mapping[str, Any]) -> dict[str, Any]:
    payload = {key: definition[key] for key in _SIGNAL_FIELDS if key in definition}
    forward_policy = definition.get("forwardSignalPolicy")
    if isinstance(forward_policy, Mapping):
        payload["forwardSignalPolicy"] = {
            key: forward_policy[key]
            for key in ("signalFamily", "parameters")
            if key in forward_policy
        }
    return payload


def freeze_signal_definition(
    strategy_version_id: str,
    definition: Mapping[str, Any],
) -> FrozenSignalDefinition:
    if not definition.get("signalEngine"):
        raise SignalDefinitionUnreproducible("signal_engine_missing")
    if not definition.get("timeframe") or not definition.get("direction"):
        raise SignalDefinitionUnreproducible("signal_identity_incomplete")
    forward_policy = definition.get("forwardSignalPolicy")
    has_registered_parameters = bool(
        isinstance(forward_policy, Mapping)
        and isinstance(forward_policy.get("parameters"), Mapping)
        and forward_policy["parameters"]
    )
    if (
        not definition.get("entryRule")
        and not definition.get("thresholds")
        and not has_registered_parameters
    ):
        raise SignalDefinitionUnreproducible("entry_rule_missing")

    frozen = json.loads(json.dumps(dict(definition), ensure_ascii=False))
    signal_payload = _canonical_signal_payload(frozen)
    return FrozenSignalDefinition(
        strategy_version_id=strategy_version_id,
        signal_frozen=True,
        strategy_definition_hash=stable_hash(frozen),
        signal_definition_hash=stable_hash(signal_payload),
        frozen_definition=frozen,
    )
