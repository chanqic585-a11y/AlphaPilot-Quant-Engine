"""Alpha191 metadata contract."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Alpha191Factor:
    factor_id: str
    display_name_zh: str
    category_zh: str
    manual_page: int | None
    manual_formula: str | None
    vibe_reference: str | None
    alpha101_reference: str | None
    canonical_formula: str | None
    required_columns: tuple[str, ...]
    required_operators: tuple[str, ...]
    windows: tuple[int, ...]
    cross_sectional: bool
    time_series: bool
    requires_benchmark: bool
    formula_status: str
    crypto_adaptation_status: str
    implementation_hash: str
    notes_zh: str

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        return {
            "factorId": value["factor_id"],
            "displayNameZh": value["display_name_zh"],
            "categoryZh": value["category_zh"],
            "manualPage": value["manual_page"],
            "manualFormula": value["manual_formula"],
            "vibeReference": value["vibe_reference"],
            "alpha101Reference": value["alpha101_reference"],
            "canonicalFormula": value["canonical_formula"],
            "requiredColumns": list(value["required_columns"]),
            "requiredOperators": list(value["required_operators"]),
            "windows": list(value["windows"]),
            "crossSectional": value["cross_sectional"],
            "timeSeries": value["time_series"],
            "requiresBenchmark": value["requires_benchmark"],
            "formulaStatus": value["formula_status"],
            "cryptoAdaptationStatus": value["crypto_adaptation_status"],
            "implementationHash": value["implementation_hash"],
            "notesZh": value["notes_zh"],
        }
