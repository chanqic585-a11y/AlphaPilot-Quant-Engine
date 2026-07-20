"""Sanitized contract identities for offline research replay.

Only public strategy metadata needed to reproduce a signal is retained. Demo
credentials, account state, execution payloads, and unknown fields are never
copied into replay evidence.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping


def _freeze_mapping(value: Mapping[str, Any]) -> Mapping[str, Any]:
    frozen: dict[str, Any] = {}
    for key, item in value.items():
        if isinstance(item, Mapping):
            frozen[str(key)] = _freeze_mapping(item)
        elif isinstance(item, list):
            frozen[str(key)] = tuple(item)
        else:
            frozen[str(key)] = item
    return MappingProxyType(frozen)


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


def _required_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"missing_or_invalid_{key}")
    return value.strip()


@dataclass(frozen=True)
class DemoReplayContract:
    demo_release_id: str
    contract_hash: str
    release_content_hash: str
    strategy_candidate_id: str
    family_key: str
    timeframe: str
    direction: str
    parameters: Mapping[str, Any]
    market_definition: Mapping[str, Any]
    release_mode: str
    status: str
    override_actor: str | None
    bypassed_evidence: tuple[str, ...]
    source_path: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bypassedEvidence": list(self.bypassed_evidence),
            "contractHash": self.contract_hash,
            "demoReleaseId": self.demo_release_id,
            "direction": self.direction,
            "familyKey": self.family_key,
            "marketDefinition": _plain(self.market_definition),
            "overrideActor": self.override_actor,
            "parameters": _plain(self.parameters),
            "releaseContentHash": self.release_content_hash,
            "releaseMode": self.release_mode,
            "sourcePath": self.source_path,
            "status": self.status,
            "strategyCandidateId": self.strategy_candidate_id,
            "timeframe": self.timeframe,
        }


def normalize_demo_release_contract(
    payload: Mapping[str, Any],
    *,
    source_path: str | Path | None = None,
) -> DemoReplayContract:
    strategy = payload.get("strategy")
    if not isinstance(strategy, Mapping):
        raise ValueError("missing_or_invalid_strategy")
    signal_policy = strategy.get("forwardSignalPolicy")
    market_definition = strategy.get("marketDefinition")
    if not isinstance(signal_policy, Mapping):
        raise ValueError("missing_or_invalid_forwardSignalPolicy")
    if not isinstance(market_definition, Mapping):
        raise ValueError("missing_or_invalid_marketDefinition")

    parameters = signal_policy.get("parameters", {})
    if not isinstance(parameters, Mapping):
        raise ValueError("missing_or_invalid_parameters")
    override_audit = payload.get("overrideAudit")
    if not isinstance(override_audit, Mapping):
        override_audit = {}
    bypassed = override_audit.get("bypassedEvidence", payload.get("bypassedEvidence", []))
    if not isinstance(bypassed, (list, tuple)):
        raise ValueError("missing_or_invalid_bypassedEvidence")

    family_key = strategy.get("familyKey") or signal_policy.get("family")
    if not isinstance(family_key, str) or not family_key:
        raise ValueError("missing_or_invalid_familyKey")
    actor = override_audit.get("actor")

    return DemoReplayContract(
        demo_release_id=_required_text(payload, "demoReleaseId"),
        contract_hash=_required_text(payload, "contractHash"),
        release_content_hash=_required_text(payload, "releaseContentHash"),
        strategy_candidate_id=_required_text(payload, "strategyCandidateId"),
        family_key=family_key,
        timeframe=_required_text(market_definition, "timeframe"),
        direction=_required_text(signal_policy, "direction"),
        parameters=_freeze_mapping(parameters),
        market_definition=_freeze_mapping(market_definition),
        release_mode=_required_text(payload, "releaseMode"),
        status=_required_text(payload, "status"),
        override_actor=str(actor) if actor is not None else None,
        bypassed_evidence=tuple(str(item) for item in bypassed),
        source_path=str(Path(source_path).resolve()) if source_path else None,
    )


def load_replay_contracts(
    directory: str | Path,
    *,
    expected_count: int | None = None,
) -> tuple[DemoReplayContract, ...]:
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(root)
    rows = []
    for path in sorted(root.glob("*.json"), key=lambda item: item.name.lower()):
        payload = json.loads(path.read_text(encoding="utf-8"))
        rows.append(normalize_demo_release_contract(payload, source_path=path))
    rows.sort(key=lambda item: item.strategy_candidate_id)
    if expected_count is not None and len(rows) != expected_count:
        raise ValueError(f"unexpected_contract_count:{len(rows)}!={expected_count}")
    return tuple(rows)
