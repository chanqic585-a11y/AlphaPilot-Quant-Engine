"""Bounded, point-in-time-aware factor registry."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash


@dataclass(frozen=True)
class FactorDefinition:
    factorId: str
    name: str
    theme: str
    formula: str
    requiredFields: tuple[str, ...]
    pointInTimeReady: bool
    sourceArtifactId: str | None = None
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["requiredFields"] = list(self.requiredFields)
        result["definitionHash"] = stable_hash(result, prefix="factor_definition")
        return result


class FactorRegistry:
    def __init__(self, *, max_factors: int = 36):
        if not 1 <= max_factors <= 36:
            raise ValueError("factor registry must be bounded to 1..36 factors")
        self.max_factors = max_factors
        self._items: dict[str, FactorDefinition] = {}

    def register(self, definition: FactorDefinition) -> None:
        if len(self._items) >= self.max_factors:
            raise ValueError("bounded factor registry is full")
        if definition.factorId in self._items:
            raise ValueError(f"duplicate factorId: {definition.factorId}")
        if not definition.pointInTimeReady:
            raise ValueError("factor is not point-in-time ready")
        if not definition.requiredFields:
            raise ValueError("requiredFields must not be empty")
        self._items[definition.factorId] = definition

    def list(self) -> list[FactorDefinition]:
        return [self._items[key] for key in sorted(self._items)]

    def to_rows(self) -> list[dict[str, Any]]:
        return [item.to_dict() for item in self.list()]
