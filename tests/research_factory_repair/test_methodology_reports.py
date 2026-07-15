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
    parity = json.loads(paths["translationParity"].read_text(encoding="utf-8"))
    benchmarks = json.loads(paths["benchmarkRegistry"].read_text(encoding="utf-8"))
    bootstrap = json.loads(paths["bootstrapPolicy"].read_text(encoding="utf-8"))
    holdout = json.loads(paths["holdoutPolicy"].read_text(encoding="utf-8"))
    exits = json.loads(paths["exitGeometry"].read_text(encoding="utf-8"))

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
    assert parity["identityMatchRequired"] == 1.0
    assert parity["minimumNumericMatchRate"] == 0.99
    assert benchmarks["eventBaselineMatching"]["sameExitGeometry"] is True
    assert benchmarks["portfolioMomentumBaseline"]["samePitUniverse"] is True
    assert bootstrap["minimumDraws"] == 5000
    assert bootstrap["clusterKeys"] == ["symbol", "eventMonth"]
    assert holdout["allowedAccessTransition"] == "0_to_1_once"
    assert holdout["failedCampaignAction"] == "close_permanently"
    assert exits["initialStopMayWiden"] is False
    assert exits["eventRemainingTargetMinimumR"] == 2.0
    assert exits["portfolioPerSymbolRTarget"] is None
    assert (tmp_path / "translation_parity_report.json").exists()
    assert (tmp_path / "holdout_unlock_policy.json").exists()
