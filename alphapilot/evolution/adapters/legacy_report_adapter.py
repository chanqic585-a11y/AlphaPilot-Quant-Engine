"""Classify existing JSON reports without promoting them to runnable strategies."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


FACTOR_KEYS = {
    "factorcount",
    "factorreports",
    "candidatefactors",
    "factorcolumnsgenerated",
    "factorcoverage",
}
METRIC_KEYS = {
    "profitfactor",
    "tradecount",
    "winrate",
    "winratepct",
    "totalreturnpct",
    "maxdrawdownpct",
}
ENTRY_KEYS = {"entryrules", "entryconditions", "entrylogic", "entryrule", "entry"}
EXIT_KEYS = {
    "exitrules",
    "exitconditions",
    "exitlogic",
    "takeprofit",
    "takeprofitr",
    "stoploss",
    "stoplossr",
}
RISK_KEYS = {
    "riskrules",
    "riskpertradepct",
    "riskpersignalpct",
    "maxleverage",
    "maxdrawdownpct",
    "riskenvelope",
}


@dataclass(frozen=True)
class LegacyClassification:
    evidenceType: str
    strategyIdentity: str
    familyKey: str
    familyFingerprint: str
    ruleFingerprint: str | None
    candidateCapable: bool
    reasons: list[str]


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _reject_non_finite_json(value: str) -> None:
    raise ValueError(f"non_finite_json_number:{value}")


def load_json_object(path: Path) -> tuple[Any | None, str | None]:
    """Load a JSON research artifact.

    The compatibility name is retained because Phase 1 originally accepted
    objects only. Historical signal logs may be arrays, but scalar roots are
    not meaningful registry evidence and remain rejected.
    """
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8-sig"),
            parse_constant=_reject_non_finite_json,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        return None, f"{type(exc).__name__}: {exc}"
    if not isinstance(payload, (dict, list)):
        return None, "top_level_json_is_not_object_or_array"
    return payload, None


def _walk_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            keys.add(_normalize_key(str(key)))
            keys.update(_walk_keys(item))
    elif isinstance(value, list):
        for item in value:
            keys.update(_walk_keys(item))
    return keys


def _find_first_text(value: Any, names: tuple[str, ...]) -> str | None:
    targets = {_normalize_key(name) for name in names}
    if isinstance(value, dict):
        for key, candidate in value.items():
            if _normalize_key(str(key)) in targets and candidate not in (None, ""):
                return str(candidate)
        for item in value.values():
            candidate = _find_first_text(item, names)
            if candidate:
                return candidate
    elif isinstance(value, list):
        for item in value:
            candidate = _find_first_text(item, names)
            if candidate:
                return candidate
    return None


def _normalize_identity(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return re.sub(r"_(report|summary|result)$", "", normalized) or "unknown"


def _extract_rule_payload(payload: dict[str, Any]) -> dict[str, Any]:
    selected: dict[str, Any] = {}
    for key, value in payload.items():
        lowered = _normalize_key(key)
        if lowered in ENTRY_KEYS | EXIT_KEYS | RISK_KEYS or any(
            token in lowered for token in ("entry", "exit", "stoploss", "takeprofit", "riskrule")
        ):
            selected[key] = value
        elif isinstance(value, dict):
            nested = _extract_rule_payload(value)
            if nested:
                selected[key] = nested
    return selected


def classify_legacy_payload(path: Path, payload: Any) -> LegacyClassification:
    keys = _walk_keys(payload)
    identity = path.stem
    if isinstance(payload, dict):
        identity = _find_first_text(
            payload,
            (
                "strategyFamily",
                "strategyId",
                "candidateId",
                "poolId",
                "reportId",
            ),
        ) or identity
    family_key = _normalize_identity(identity)
    has_factor = bool(keys & FACTOR_KEYS) or "factor" in path.stem.lower()
    has_entry = bool(keys & ENTRY_KEYS)
    has_exit = bool(keys & EXIT_KEYS)
    has_risk = bool(keys & RISK_KEYS)
    has_metrics = bool(keys & METRIC_KEYS)
    candidate_capable = isinstance(payload, dict) and has_entry and has_exit and has_risk
    reasons: list[str] = []
    if has_factor:
        evidence_type = "factor_asset"
        reasons.append("factor_schema_or_filename_detected")
    elif isinstance(payload, list):
        evidence_type = "incomplete_evidence"
        reasons.append("top_level_array_research_artifact")
    elif candidate_capable:
        evidence_type = "strategy_candidate_evidence"
        reasons.append("entry_exit_and_risk_rules_detected")
    elif has_metrics:
        evidence_type = "report_summary"
        reasons.append("performance_metrics_without_complete_rules")
    else:
        evidence_type = "incomplete_evidence"
        reasons.append("missing_factor_or_complete_strategy_contract")
    rule_payload = _extract_rule_payload(payload) if candidate_capable else {}
    rule_fingerprint = stable_hash(rule_payload, prefix="rules") if rule_payload else None
    family_fingerprint = stable_hash(
        {"familyKey": family_key},
        prefix="family",
    )
    return LegacyClassification(
        evidenceType=evidence_type,
        strategyIdentity=identity,
        familyKey=family_key,
        familyFingerprint=family_fingerprint,
        ruleFingerprint=rule_fingerprint,
        candidateCapable=candidate_capable,
        reasons=reasons,
    )
