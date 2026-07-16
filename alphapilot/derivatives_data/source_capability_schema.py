"""Schema helpers for public historical-data capability evidence."""

from __future__ import annotations

from typing import Any


CAPABILITY_FIELDS = frozenset(
    {
        "provider",
        "exchange",
        "endpointOrArchive",
        "dataType",
        "marketType",
        "requiresAuth",
        "publicOnly",
        "licenseOrUsageTerms",
        "earliestAvailable",
        "latestAvailable",
        "symbolCoverage",
        "granularity",
        "pagination",
        "rateLimit",
        "maximumLookback",
        "historicalCompleteness",
        "pointInTimeSemantics",
        "knownLimitations",
        "probeStatus",
    }
)


def build_capability_record(**values: Any) -> dict[str, Any]:
    missing = sorted(CAPABILITY_FIELDS - values.keys())
    if missing:
        raise ValueError(f"capability record missing fields: {', '.join(missing)}")
    record = dict(values)
    if record["requiresAuth"] or not record["publicOnly"]:
        record["formalHistoricalEligible"] = False
    return record

