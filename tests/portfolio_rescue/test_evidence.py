from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from alphapilot.portfolio_rescue.contracts import build_default_campaign
from alphapilot.portfolio_rescue.evidence import (
    freeze_preregistration,
    run_and_write_portfolio_rescue,
)


def test_campaign_writes_development_only_evidence(tmp_path: Path) -> None:
    campaign = build_default_campaign()
    ledger_dir = tmp_path / "ledgers"
    ledger_dir.mkdir()
    for index, sleeve in enumerate(campaign.sleeves):
        pd.DataFrame(
            [
                {
                    "candidateId": sleeve.candidate_id,
                    "family": sleeve.family,
                    "pair": f"PAIR{index}",
                    "direction": sleeve.direction,
                    "entryDate": f"2025-0{index + 1}-01T00:00:00Z",
                    "exitDate": f"2025-0{index + 1}-02T00:00:00Z",
                    "netR": 0.5,
                    "grossR": 0.6,
                    "feeR": 0.1,
                    "exitReason": "target",
                }
            ]
        ).to_parquet(ledger_dir / f"{sleeve.candidate_id}.parquet", index=False)

    output_dir = tmp_path / "output"
    preregistration = freeze_preregistration(output_dir, campaign, ledger_dir)
    summary = run_and_write_portfolio_rescue(output_dir, campaign, ledger_dir)

    assert preregistration["frozenBeforeResultRead"] is True
    assert summary["status"] == "development_only"
    assert summary["formalCandidateCount"] == 0
    assert summary["releaseCount"] == 0
    assert summary["policyTrialCount"] == 6
    for name in (
        "campaign_summary.json",
        "campaign_summary.md",
        "policy_matrix.csv",
        "sleeve_attribution.csv",
        "monthly_consistency.csv",
        "failure_attribution.json",
        "experiment_budget.json",
        "preregistration.json",
        "artifact_manifest.json",
    ):
        assert (output_dir / name).exists(), name
    manifest = json.loads((output_dir / "artifact_manifest.json").read_text(encoding="utf-8"))
    assert manifest["artifactCount"] >= 8
