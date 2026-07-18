"""Verify volume meaning from traceable metadata, never from value shape."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


_TRACEABLE_EVIDENCE = {
    "raw_multicolumn_file",
    "manifest",
    "meta_json",
    "official_api_schema",
    "official_archive_schema",
    "pinned_library_market_semantics",
    "canonical_reader_mapping",
}
_QUOTE_COLUMNS = {"volume_quote_currency", "volCcyQuote", "quoteVolume"}
_BASE_COLUMNS = {"volume_base_currency", "volCcy", "baseVolume"}
_CONTRACT_KEYS = {
    "contractSize",
    "contractValueCurrency",
    "quoteCurrency",
    "contractType",
    "priceConversionRule",
    "metadataVersion",
}


def _result(
    metadata: Mapping[str, Any],
    *,
    status: str,
    route: str,
    semantic_type: str | None,
    reason: str | None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schemaVersion": "volume_semantics_verification_v1",
        "status": status,
        "route": route,
        "semanticType": semantic_type,
        "selectedVolumeColumn": str(metadata.get("selectedVolumeColumn") or ""),
        "reason": reason,
    }
    payload["verificationHash"] = stable_hash(
        payload, prefix="volume_semantics_verification"
    )
    return payload


def verify_volume_semantics(metadata: Mapping[str, Any]) -> dict[str, Any]:
    selected = str(metadata.get("selectedVolumeColumn") or "")
    raw_columns = {str(value) for value in metadata.get("rawColumnNames") or ()}
    declared = str(metadata.get("declaredVolumeUnit") or "")
    source_hash = str(metadata.get("sourceFileHash") or "")
    evidence = {str(value) for value in metadata.get("evidenceRefs") or ()}
    traceable = bool(source_hash) and bool(evidence & _TRACEABLE_EVIDENCE)
    if not traceable or selected not in raw_columns:
        return _result(
            metadata,
            status="capacity_semantics_unavailable",
            route="E",
            semantic_type=None,
            reason="missing_traceable_source_or_selected_column",
        )
    if selected in _QUOTE_COLUMNS or declared == "quote_asset":
        return _result(
            metadata,
            status="verified",
            route="A",
            semantic_type="exact_quote_turnover",
            reason=None,
        )
    if selected in _BASE_COLUMNS or declared == "base_asset":
        return _result(
            metadata,
            status="verified",
            route="B",
            semantic_type="verified_base_volume",
            reason=None,
        )
    if declared == "contracts":
        contract_metadata = dict(metadata.get("contractMetadata") or {})
        if _CONTRACT_KEYS <= set(contract_metadata):
            return _result(
                metadata,
                status="verified",
                route="C",
                semantic_type="verified_contract_volume",
                reason=None,
            )
        return _result(
            metadata,
            status="capacity_semantics_unavailable",
            route="E",
            semantic_type=None,
            reason="incomplete_contract_metadata",
        )
    return _result(
        metadata,
        status="capacity_semantics_unavailable",
        route="E",
        semantic_type=None,
        reason="volume_unit_not_proven",
    )
