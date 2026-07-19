"""Structured sandbox audit records."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class SourceAudit:
    passed: bool
    reasons: tuple[str, ...]
    imports: tuple[str, ...]
    calls: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["reasons"] = list(self.reasons)
        result["imports"] = list(self.imports)
        result["calls"] = list(self.calls)
        return result
