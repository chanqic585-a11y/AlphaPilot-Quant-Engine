from __future__ import annotations

import hashlib
import json
from pathlib import Path

from alphapilot.portfolio_oos.evidence import generate_v47_v49_evidence


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _v46_fixture(root: Path) -> Path:
    report = root / "v46"
    sleeve = {
        "candidate_id": "short_1h",
        "family": "short_rejection",
        "direction": "short",
        "timeframe": "1h",
        "sleeve_hash": "sleeve_short_hash",
    }
    long_sleeve = {
        "candidate_id": "long_1d",
        "family": "mean_reversion",
        "direction": "long",
        "timeframe": "1d",
        "sleeve_hash": "sleeve_long_hash",
    }
    third = {
        "candidate_id": "breakout_1d",
        "family": "squeeze_breakout",
        "direction": "long",
        "timeframe": "1d",
        "sleeve_hash": "sleeve_breakout_hash",
    }
    preregistration = {
        "campaignHash": "v46_campaign_hash",
        "campaignId": "v46_campaign",
        "contract": {"sleeves": [sleeve, long_sleeve, third]},
        "ledgers": [
            {"candidateId": "short_1h", "sha256": "ledger_short_hash"},
            {"candidateId": "long_1d", "sha256": "ledger_long_hash"},
            {"candidateId": "breakout_1d", "sha256": "ledger_breakout_hash"},
        ],
    }
    policy_results = [
        {
            "policy": {
                "policy_id": "raw_baseline",
                "policy_hash": "raw_hash",
                "pair_cooldown_days": 0,
                "maximum_concurrent_positions": 99,
                "same_direction_cap": 99,
                "losing_pair_cooldown_days": 0,
                "additional_cost_stress_r": [0.05, 0.1],
                "version": "v13.27.1.46",
            },
            "metrics": {"profitFactor": 1.2, "expectancyR": 0.1},
        },
        {
            "policy": {
                "policy_id": "pair_14d_cooldown",
                "policy_hash": "selected_hash",
                "pair_cooldown_days": 14,
                "maximum_concurrent_positions": 99,
                "same_direction_cap": 99,
                "losing_pair_cooldown_days": 0,
                "additional_cost_stress_r": [0.05, 0.1],
                "version": "v13.27.1.46",
            },
            "metrics": {"profitFactor": 1.6, "expectancyR": 0.3},
        },
    ]
    _write_json(report / "preregistration.json", preregistration)
    _write_json(report / "policy_results.json", policy_results)
    _write_json(report / "campaign_summary.json", {"bestPolicyId": "pair_14d_cooldown"})
    artifacts = []
    for name in ("preregistration.json", "policy_results.json", "campaign_summary.json"):
        path = report / name
        artifacts.append({"path": name, "bytes": path.stat().st_size, "sha256": _sha(path)})
    _write_json(report / "artifact_manifest.json", {"artifactCount": 3, "artifacts": artifacts})
    return report


def test_generate_freezes_exact_selected_portfolio_without_claiming_oos(tmp_path: Path) -> None:
    v46 = _v46_fixture(tmp_path)
    output = tmp_path / "out"

    result = generate_v47_v49_evidence(
        v46_report_dir=v46,
        output_dir=output,
        publish_receipt={
            "commit": "f7e87e3",
            "remoteBranch": "origin/feature/v46",
            "remoteCommit": "f7e87e3",
            "pushed": True,
        },
        generated_at="2026-07-20T00:00:00Z",
    )

    assert result["status"] == "frozen_pre_result_read"
    spec = json.loads((output / "v49_portfolio_candidate_spec.json").read_text())
    assert spec["candidateId"] == "v49_three_mechanism_same_symbol_14d_cooldown_portfolio_v1"
    assert [row["candidateId"] for row in spec["sleeves"]] == [
        "short_1h",
        "long_1d",
        "breakout_1d",
    ]
    assert spec["selectedPolicy"]["policy_id"] == "pair_14d_cooldown"
    assert spec["selectedPolicy"]["policy_hash"] == "selected_hash"
    assert spec["resultReadCount"] == 0
    assert spec["formalStatisticalPassAllowed"] is False

    identity = json.loads((output / "v49_portfolio_oos_identity.json").read_text())
    assert identity["validationRoute"] == "forward_only"
    assert identity["historicalUnreadIntervalAvailable"] is False
    assert identity["resultReadCount"] == 0
    assert identity["status"] == "frozen_pre_result_read"


def test_selection_ledger_discloses_observed_policy_trials_and_unknown_upstream_history(
    tmp_path: Path,
) -> None:
    output = tmp_path / "out"
    generate_v47_v49_evidence(
        v46_report_dir=_v46_fixture(tmp_path),
        output_dir=output,
        publish_receipt={"commit": "abc", "remoteCommit": "abc", "pushed": True},
        generated_at="2026-07-20T00:00:00Z",
    )

    ledger = json.loads((output / "v46_portfolio_selection_trial_ledger.json").read_text())
    assert ledger["observedPolicyTrialCount"] == 2
    assert ledger["selectedPolicyId"] == "pair_14d_cooldown"
    assert len(ledger["policyTrials"]) == 2

    audit = json.loads((output / "v46_portfolio_selection_bias_audit.json").read_text())
    assert audit["selectionTrialCount"] == "unavailable"
    assert audit["upstreamStrategySelectionHistoryAvailable"] is False
    assert audit["policySelectionResultReadBeforeChoice"] is True
    assert audit["formalStatisticalPassAllowed"] is False
    assert audit["provisionalResearchDemoAllowed"] is True


def test_manifest_verification_fails_closed_on_modified_v46_artifact(tmp_path: Path) -> None:
    v46 = _v46_fixture(tmp_path)
    (v46 / "campaign_summary.json").write_text("{}\n", encoding="utf-8")

    try:
        generate_v47_v49_evidence(
            v46_report_dir=v46,
            output_dir=tmp_path / "out",
            publish_receipt={"commit": "abc", "remoteCommit": "abc", "pushed": True},
            generated_at="2026-07-20T00:00:00Z",
        )
    except ValueError as error:
        assert str(error) == "v46_artifact_manifest_verification_failed"
    else:  # pragma: no cover
        raise AssertionError("modified evidence must fail closed")
