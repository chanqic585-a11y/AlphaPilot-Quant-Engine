"""Shared schemas for public market data expansion.

These objects describe planned public-data inputs only. They do not fetch data,
use private endpoints, read accounts, create orders, or auto trade.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class PublicDataField:
    name: str
    valueType: str
    required: bool
    nullable: bool
    description: str
    sourceNotes: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicDataQualityRule:
    ruleId: str
    severity: str
    description: str
    failureHandling: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PublicDataSchema:
    schemaId: str
    version: str
    dataType: str
    storageStatus: str
    primaryKeys: list[str]
    fields: list[PublicDataField]
    qualityRules: list[PublicDataQualityRule]
    unavailableHandling: str
    safetyNotes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schemaId": self.schemaId,
            "version": self.version,
            "dataType": self.dataType,
            "storageStatus": self.storageStatus,
            "primaryKeys": self.primaryKeys,
            "fields": [item.to_dict() for item in self.fields],
            "qualityRules": [item.to_dict() for item in self.qualityRules],
            "unavailableHandling": self.unavailableHandling,
            "safetyNotes": self.safetyNotes,
        }


def public_data_safety_notes() -> list[str]:
    return [
        "Public market data only.",
        "No API key is required or stored.",
        "No private exchange endpoint is used.",
        "No account, position, order, Trade API, or Withdraw API access.",
        "Data is research context only and must not trigger trading.",
    ]
