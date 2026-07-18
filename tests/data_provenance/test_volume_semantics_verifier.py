from __future__ import annotations

from alphapilot.data_provenance.volume_semantics_verifier import (
    verify_volume_semantics,
)


def test_raw_quote_currency_column_with_traceable_evidence_is_verified() -> None:
    result = verify_volume_semantics(
        {
            "rawColumnNames": ["open", "high", "low", "close", "volume_quote_currency"],
            "selectedVolumeColumn": "volume_quote_currency",
            "sourceFileHash": "abc123",
            "evidenceRefs": ["raw_multicolumn_file", "canonical_reader_mapping"],
        }
    )
    assert result["status"] == "verified"
    assert result["route"] == "A"
    assert result["semanticType"] == "exact_quote_turnover"


def test_unknown_column_or_missing_traceability_fails_closed() -> None:
    result = verify_volume_semantics(
        {
            "rawColumnNames": ["volume"],
            "selectedVolumeColumn": "volume",
            "sourceFileHash": "",
            "evidenceRefs": [],
        }
    )
    assert result["status"] == "capacity_semantics_unavailable"
    assert result["route"] == "E"


def test_verified_contract_volume_requires_versioned_contract_metadata() -> None:
    missing = verify_volume_semantics(
        {
            "rawColumnNames": ["vol"],
            "selectedVolumeColumn": "vol",
            "declaredVolumeUnit": "contracts",
            "sourceFileHash": "abc123",
            "evidenceRefs": ["official_api_schema"],
            "contractMetadata": {"contractSize": 0.01},
        }
    )
    complete = verify_volume_semantics(
        {
            "rawColumnNames": ["vol"],
            "selectedVolumeColumn": "vol",
            "declaredVolumeUnit": "contracts",
            "sourceFileHash": "abc123",
            "evidenceRefs": ["official_api_schema", "official_instrument_metadata"],
            "contractMetadata": {
                "contractSize": 0.01,
                "contractValueCurrency": "BTC",
                "quoteCurrency": "USDT",
                "contractType": "linear",
                "priceConversionRule": "contracts * contract_size * price",
                "metadataVersion": "okx_swap_contract_v1",
            },
        }
    )
    assert missing["status"] == "capacity_semantics_unavailable"
    assert complete["semanticType"] == "verified_contract_volume"
