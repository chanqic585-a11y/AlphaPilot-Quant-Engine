"""Schemas for V13.4.20 research-only probability gate candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ProbabilityGateCandidate:
    candidateGateId: str
    status: str
    allowedBuckets: list[str]
    minimumSampleCount: int
    minimumProfitFactor: float
    minimumExpectancy: float
    useForTrading: bool
    useForDryRun: bool
    sourceTable: str | None = None
    sourceTables: list[str] = field(default_factory=list)
    rejectedBuckets: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "ProbabilityGateCandidate":
        source_table = payload.get("sourceTable")
        source_tables = list(payload.get("sourceTables") or [])
        if source_table and source_table not in source_tables:
            source_tables.insert(0, str(source_table))
        return cls(
            candidateGateId=str(payload["candidateGateId"]),
            status=str(payload["status"]),
            sourceTable=str(source_table) if source_table else None,
            sourceTables=[str(item) for item in source_tables],
            allowedBuckets=[str(item) for item in payload.get("allowedBuckets", [])],
            rejectedBuckets=[str(item) for item in payload.get("rejectedBuckets", [])],
            minimumSampleCount=int(payload.get("minimumSampleCount", 50)),
            minimumProfitFactor=float(payload.get("minimumProfitFactor", 1.05)),
            minimumExpectancy=float(payload.get("minimumExpectancy", 0)),
            useForTrading=bool(payload.get("useForTrading")),
            useForDryRun=bool(payload.get("useForDryRun")),
            notes=[str(item) for item in payload.get("notes", [])],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
