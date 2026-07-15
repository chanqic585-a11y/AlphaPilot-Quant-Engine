from __future__ import annotations

import json
from pathlib import Path

from alphapilot.research_factory_repair.methodology_reports import (
    write_methodology_reports,
)
from alphapilot.research_screening.gate_schema import PUBLIC_GATE_FIELDS


def test_methodology_reports_publish_explicit_v2_contract(tmp_path: Path) -> None:
    paths = write_methodology_reports(tmp_path)

    migration = json.loads(paths["gateMigration"].read_text(encoding="utf-8"))
    causality = json.loads(paths["causalityPolicy"].read_text(encoding="utf-8"))

    assert migration["status"] == "active"
    assert migration["replacementFields"] == list(PUBLIC_GATE_FIELDS)
    assert migration["deprecatedFields"] == [
        "basePassed",
        "formalPassed",
        "oosMetrics",
        "fullBacktestExecuted",
    ]
    assert causality["nextBarExecution"] is True
    assert causality["boundaryCrossingEvents"] == "drop_not_truncate"
    assert causality["requiredObservationTimestamps"] == [
        "eventTimestamp",
        "observedAt",
        "publishedAt",
        "availableAt",
        "sourceTimestamp",
        "ageSeconds",
        "publicationLagSeconds",
    ]
