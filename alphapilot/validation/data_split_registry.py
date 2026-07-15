from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable

from .hashing import stable_hash


DateRange = tuple[str, str]


@dataclass(frozen=True)
class DataSplitManifest:
    development_range: DateRange
    validation_range: DateRange
    locked_range: DateRange
    development_symbols: tuple[str, ...]
    locked_symbols: tuple[str, ...]
    used_for_selection_ranges: tuple[DateRange, ...]
    used_for_selection_symbols: tuple[str, ...]
    split_manifest_hash: str


@dataclass(frozen=True)
class SplitContaminationAudit:
    used_for_selection_ranges: tuple[DateRange, ...]
    used_for_selection_symbols: tuple[str, ...]
    potential_leakage_flags: list[str]


def _ordered(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value) for value in values}))


def build_split_manifest(
    *,
    development_range: DateRange,
    validation_range: DateRange,
    locked_range: DateRange,
    development_symbols: Iterable[str],
    locked_symbols: Iterable[str],
    used_for_selection_ranges: Iterable[DateRange],
    used_for_selection_symbols: Iterable[str],
) -> DataSplitManifest:
    payload = {
        "development_range": tuple(development_range),
        "validation_range": tuple(validation_range),
        "locked_range": tuple(locked_range),
        "development_symbols": _ordered(development_symbols),
        "locked_symbols": _ordered(locked_symbols),
        "used_for_selection_ranges": tuple(
            sorted(tuple(value) for value in used_for_selection_ranges)
        ),
        "used_for_selection_symbols": _ordered(used_for_selection_symbols),
    }
    return DataSplitManifest(
        **payload,
        split_manifest_hash=stable_hash(payload),
    )


def _overlaps(left: DateRange, right: DateRange) -> bool:
    left_start, left_end = (date.fromisoformat(value) for value in left)
    right_start, right_end = (date.fromisoformat(value) for value in right)
    return max(left_start, right_start) <= min(left_end, right_end)


def audit_split_contamination(
    manifest: DataSplitManifest,
) -> SplitContaminationAudit:
    flags: list[str] = []
    if any(
        _overlaps(value, manifest.locked_range)
        for value in manifest.used_for_selection_ranges
    ):
        flags.append("locked_range_used_for_selection")
    if set(manifest.locked_symbols) & set(manifest.used_for_selection_symbols):
        flags.append("locked_symbol_used_for_selection")
    return SplitContaminationAudit(
        used_for_selection_ranges=manifest.used_for_selection_ranges,
        used_for_selection_symbols=manifest.used_for_selection_symbols,
        potential_leakage_flags=flags,
    )


def split_manifest_payload(manifest: DataSplitManifest) -> dict:
    return asdict(manifest)

