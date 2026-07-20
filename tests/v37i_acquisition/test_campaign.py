from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from alphapilot.v37i_acquisition import (
    V37IBudget,
    build_candidate_catalog,
    run_bounded_acquisition,
)


def _write_panel(path: Path, asset: str, funding_rate: float) -> None:
    rows = 240
    frame = pd.DataFrame(
        {
            "decisionTimestampMs": [1_700_000_000_000 + index * 28_800_000 for index in range(rows)],
            "decisionAvailableAtMs": [1_700_000_000_000 + index * 28_800_000 for index in range(rows)],
            "fundingRate": [funding_rate] * rows,
            "spotPrice": [100.0 + index * 0.05 for index in range(rows)],
            "perpetualPrice": [100.0 + index * 0.05 for index in range(rows)],
            "basisPct": [0.0] * rows,
            "dualLegQuoteTurnoverProxy": [10_000_000.0] * rows,
            "stale": [False] * rows,
            "zeroFillUsed": [False] * rows,
            "crossExchangeSubstitution": [False] * rows,
            "asset": [asset] * rows,
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(path, index=False)


def _manifest(tmp_path: Path) -> Path:
    artifacts = []
    for asset, rate in (("BTC", 0.0004), ("ETH", 0.00035), ("SOL", 0.0003)):
        panel = tmp_path / f"{asset}.parquet"
        _write_panel(panel, asset, rate)
        artifacts.append({"asset": asset, "path": str(panel), "sha256": "fixture"})
    path = tmp_path / "manifest.json"
    path.write_text(
        json.dumps({"panelArtifacts": artifacts}, sort_keys=True), encoding="utf-8"
    )
    return path


def test_catalog_is_bounded_and_does_not_revive_archived_tsmom() -> None:
    catalog = build_candidate_catalog()

    assert len(catalog) == 5
    assert len({candidate.campaign_id for candidate in catalog}) == 2
    assert len({candidate.family_id for candidate in catalog}) == 4
    assert all(3 <= len(candidate.parameter_trials) <= 8 for candidate in catalog)
    assert all(
        candidate.candidate_id
        not in {"v35_tsmom_crypto_adaptation", "v37e_tsmom_daily_capacity_successor"}
        for candidate in catalog
    )
    turtle = next(candidate for candidate in catalog if "turtle" in candidate.candidate_id)
    assert turtle.similarity_classification == "exact_duplicate"
    assert turtle.prefilter_blocker == "duplicate_archived_identity"


def test_budget_rejects_any_scope_expansion() -> None:
    budget = V37IBudget.default()

    with pytest.raises(ValueError, match="maximumCampaigns"):
        budget.validate(campaigns=3, families=4, candidates=5, variants_by_family={})
    with pytest.raises(ValueError, match="maximumVariantsPerFamily"):
        budget.validate(
            campaigns=2,
            families=4,
            candidates=5,
            variants_by_family={"funding": 3},
        )


def test_campaign_writes_bounded_evidence_without_execution_side_effects(
    tmp_path: Path,
) -> None:
    output = tmp_path / "reports"
    result = run_bounded_acquisition(
        panel_manifest_path=_manifest(tmp_path),
        inherited_budget_path=Path("reports/integration/v37f/budget_reconciliation.json"),
        output_root=output,
        frozen_at="2026-07-20T00:00:00Z",
    )

    assert result["campaignCount"] == 2
    assert result["candidateCount"] == 5
    assert result["lockedOosReadCount"] == 0
    assert result["formalRunCount"] == 0
    assert result["releaseCount"] == 0
    assert result["demoArm"] is False
    assert result["orderCount"] == 0
    assert (output / "campaign_inventory.json").is_file()
    assert (output / "candidate_inventory.json").is_file()
    assert (output / "prefilter_matrix.csv").is_file()
    assert (output / "candidate_results.parquet").is_file()
    assert (output / "failure_attribution.json").is_file()
    assert (output / "artifact_manifest.json").is_file()
