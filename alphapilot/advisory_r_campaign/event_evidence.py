"""Complete, deterministic event evidence for corrected Advisory-R campaigns."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from alphapilot.evolution.registry.hashing import stable_hash


EVENT_SCHEMA_FIELDS = (
    "trialId",
    "candidateId",
    "signalId",
    "symbol",
    "legs",
    "direction",
    "signalTimestamp",
    "entryTimestamp",
    "entryPrice",
    "initialStop",
    "initialRisk",
    "exitPolicyMode",
    "exitPolicyHash",
    "exitLegCount",
    "exitLegs",
    "triggerTimestamp",
    "executionTimestamp",
    "exitReason",
    "grossR",
    "feesR",
    "slippageR",
    "spreadR",
    "fundingR",
    "netR",
    "MFE",
    "MAE",
    "marketRegime",
    "month",
    "split",
    "foldId",
    "sourceDataHash",
    "implementationConformanceHash",
    "correctionCampaignId",
)


def _funding_unknown(_: Any) -> None:
    # The frozen snapshot has no funding series. A numeric engine default must not
    # be promoted into evidence that funding was observed.
    return None


def _market_legs(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    legs = raw.get("marketLegs")
    if isinstance(legs, list):
        return [dict(row) for row in legs]
    if str(raw.get("symbol")) == "PORTFOLIO":
        long_symbols = [str(value) for value in raw.get("longSymbols") or []]
        short_symbols = [str(value) for value in raw.get("shortSymbols") or []]
        if not long_symbols or not short_symbols:
            raise RuntimeError("portfolio event requires frozen long and short cohorts")
        long_weight = 0.5 / len(long_symbols)
        short_weight = 0.5 / len(short_symbols)
        return [
            {"symbol": symbol, "direction": "long", "weight": long_weight}
            for symbol in long_symbols
        ] + [
            {"symbol": symbol, "direction": "short", "weight": short_weight}
            for symbol in short_symbols
        ]
    return [{"symbol": str(raw["symbol"]), "direction": str(raw["side"])}]


def _event_direction(raw: Mapping[str, Any]) -> str:
    if str(raw.get("symbol")) == "PORTFOLIO":
        return "cross_sectional_long_short"
    return str(raw["side"])


def _exit_legs(raw: Mapping[str, Any]) -> list[dict[str, Any]]:
    result = []
    for row in raw.get("legs") or []:
        item = dict(row)
        result.append(
            {
                "fraction": float(item["fraction"]),
                "reason": str(item["reason"]),
                "triggerTimestamp": str(item["triggerTimestamp"]),
                "executionTimestamp": str(item["executionTimestamp"]),
                "price": float(item["price"]),
                "grossR": float(item["grossR"]),
                "feesR": float(item["feesR"]),
                "slippageR": float(item["slippageR"]),
                "spreadR": float(item.get("spreadProxyR") or 0.0),
                "fundingR": _funding_unknown(item.get("fundingR")),
                "netR": float(item["netR"]),
                "isGapFill": bool(item.get("isGapFill")),
                "ambiguousPath": bool(item.get("ambiguousPath")),
            }
        )
    if not result:
        raise RuntimeError("event evidence requires at least one formal exit leg")
    return result


def _signal_identity(raw: Mapping[str, Any], market_legs: Sequence[Mapping[str, Any]]) -> str:
    identity = {
        "candidateId": raw["candidateId"],
        "legs": [dict(row) for row in market_legs],
        "direction": _event_direction(raw),
        "signalTimestamp": raw["signalTimestamp"],
        "entryTimestamp": raw["entryTimestamp"],
    }
    return stable_hash(identity, prefix="advisory_r_signal")


def build_event_evidence(
    raw: Mapping[str, Any],
    *,
    trial_id: str,
    correction_campaign_id: str,
    implementation_conformance_hash: str,
    source_data_hash: str,
    market_regime: str,
) -> dict[str, Any]:
    market_legs = _market_legs(raw)
    exit_legs = _exit_legs(raw)
    final_leg = exit_legs[-1]
    entry_timestamp = str(raw["entryTimestamp"])
    event = {
        "trialId": trial_id,
        "candidateId": str(raw["candidateId"]),
        "signalId": _signal_identity(raw, market_legs),
        "symbol": str(raw["symbol"]),
        "legs": market_legs,
        "direction": _event_direction(raw),
        "signalTimestamp": str(raw["signalTimestamp"]),
        "entryTimestamp": entry_timestamp,
        "entryPrice": float(raw["entryPrice"]),
        "initialStop": float(raw["initialStopPrice"]),
        "initialRisk": float(raw["riskDistance"]),
        "exitPolicyMode": str(raw["exitPolicyMode"]),
        "exitPolicyHash": str(raw["exitPolicyHash"]),
        "exitLegCount": len(exit_legs),
        "exitLegs": exit_legs,
        "triggerTimestamp": final_leg["triggerTimestamp"],
        "executionTimestamp": final_leg["executionTimestamp"],
        "exitReason": final_leg["reason"],
        "grossR": float(raw["grossR"]),
        "feesR": float(raw["feesR"]),
        "slippageR": float(raw["slippageR"]),
        "spreadR": float(raw.get("spreadProxyR") or 0.0),
        "fundingR": _funding_unknown(raw.get("fundingR")),
        "netR": float(raw["netR"]),
        "MFE": float(raw.get("mfeR") or 0.0),
        "MAE": float(raw.get("maeR") or 0.0),
        "marketRegime": market_regime,
        "month": entry_timestamp[:7],
        "split": "development",
        "foldId": "representative_prefilter",
        "sourceDataHash": source_data_hash,
        "implementationConformanceHash": implementation_conformance_hash,
        "correctionCampaignId": correction_campaign_id,
        # Compatibility fields consumed by the existing metric layer.
        "mfeR": float(raw.get("mfeR") or 0.0),
        "maeR": float(raw.get("maeR") or 0.0),
        "spreadProxyR": float(raw.get("spreadProxyR") or 0.0),
        "realizedGrossR": float(raw["grossR"]),
        "realizedNetR": float(raw["netR"]),
        "partialExit": len(exit_legs) > 1,
        "profitGivebackR": float(raw.get("givebackR") or raw.get("profitGivebackR") or 0.0),
    }
    missing = [name for name in EVENT_SCHEMA_FIELDS if name not in event]
    if missing:
        raise RuntimeError(f"incomplete event evidence: {missing}")
    return event


def _parity_identity_from_raw(raw: Mapping[str, Any]) -> dict[str, Any]:
    market_legs = _market_legs(raw)
    exit_legs = _exit_legs(raw)
    return {
        "candidateId": str(raw["candidateId"]),
        "signalId": _signal_identity(raw, market_legs),
        "symbol": str(raw["symbol"]),
        "legs": market_legs,
        "direction": _event_direction(raw),
        "signalTimestamp": str(raw["signalTimestamp"]),
        "entryTimestamp": str(raw["entryTimestamp"]),
        "exitLegCount": len(exit_legs),
        "exitLegs": exit_legs,
    }


def _parity_identity_from_evidence(event: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "candidateId": str(event["candidateId"]),
        "signalId": str(event["signalId"]),
        "symbol": str(event["symbol"]),
        "legs": [dict(row) for row in event["legs"]],
        "direction": str(event["direction"]),
        "signalTimestamp": str(event["signalTimestamp"]),
        "entryTimestamp": str(event["entryTimestamp"]),
        "exitLegCount": int(event["exitLegCount"]),
        "exitLegs": [dict(row) for row in event["exitLegs"]],
    }


def verify_event_parity(
    raw_events: Sequence[Mapping[str, Any]],
    evidence_events: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    raw_identities = [_parity_identity_from_raw(row) for row in raw_events]
    evidence_identities = [_parity_identity_from_evidence(row) for row in evidence_events]
    passed = raw_identities == evidence_identities
    if not passed:
        raise RuntimeError("event parity failed: missing, extra, or changed event/leg")
    return {
        "schemaVersion": "advisory_r_implementation_parity_v1",
        "rawEventCount": len(raw_identities),
        "evidenceEventCount": len(evidence_identities),
        "missingEventCount": 0,
        "extraEventCount": 0,
        "changedEventCount": 0,
        "passed": True,
    }


def event_schema_report() -> dict[str, Any]:
    return {
        "schemaVersion": "advisory_r_candidate_event_schema_v2",
        "requiredFields": list(EVENT_SCHEMA_FIELDS),
        "fundingSemantics": "null_when_source_series_unavailable",
        "structureExecution": "confirmed_close_then_next_bar_open",
    }
