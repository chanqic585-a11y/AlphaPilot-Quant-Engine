from __future__ import annotations

import json
from pathlib import Path

from alphapilot.portfolio_provisional_demo.evidence import generate_patch_evidence


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def test_generator_writes_complete_unapproved_sidecar_bundle(tmp_path: Path) -> None:
    v46 = tmp_path / "v46"
    v49 = tmp_path / "v49"
    contracts = tmp_path / "contracts"
    output = tmp_path / "output"
    components = [
        ("short_1h", "short", "1h", "short_rejection", "short_hash"),
        ("long_1d", "long", "1d", "mean_reversion", "long_hash"),
        ("breakout_1d", "long", "1d", "squeeze_breakout", "breakout_hash"),
    ]
    _write(
        v49 / "v49_portfolio_candidate_spec.json",
        {
            "candidateId": "portfolio_candidate",
            "candidateHash": "portfolio_candidate_hash",
            "sourceCampaignHash": "campaign_hash",
            "allocationSemantics": "source_trade_ledger_native_risk_no_posthoc_weighting",
            "selectedPolicy": {
                "policy_id": "pair_14d_cooldown",
                "policy_hash": "policy_hash",
                "pair_cooldown_days": 14,
            },
            "sleeves": [
                {
                    "candidateId": candidate_id,
                    "direction": direction,
                    "timeframe": timeframe,
                    "family": family,
                    "ledgerSha256": f"ledger_{candidate_id}",
                    "sleeveHash": f"sleeve_{candidate_id}",
                }
                for candidate_id, direction, timeframe, family, _ in components
            ],
        },
    )
    _write(
        v46 / "campaign_summary.json",
        {
            "bestPolicyChecks": {"stressProfitFactor1_05": True},
            "bestPolicyMetrics": {"profitFactor": 1.6, "expectancyR": 0.3},
            "formalCandidateCount": 0,
            "releaseCount": 0,
            "status": "development_only",
        },
    )
    _write(
        v46 / "policy_results.json",
        [
            {
                "policy": {"policy_id": "pair_14d_cooldown"},
                "stressMetrics": {"plus_0.10R": {"profitFactor": 1.36}},
            }
        ],
    )
    for candidate_id, direction, timeframe, family, definition_hash in components:
        _write(
            contracts / f"{candidate_id}.json",
            {
                "strategyCandidateId": candidate_id,
                "strategy": {
                    "strategyContentHash": definition_hash,
                    "familyKey": family,
                    "forwardSignalPolicy": {"direction": direction, "parameters": {}},
                    "marketDefinition": {"timeframe": timeframe},
                },
                "riskEnvelope": {
                    "riskPerTradePercent": 0.25,
                    "maxOpenRiskPercent": 1.0,
                    "maxConcurrentPositions": 3,
                },
                "releaseMode": "experimental_override",
            },
        )

    result = generate_patch_evidence(
        v46_report_dir=v46,
        v49_identity_dir=v49,
        component_contract_dir=contracts,
        output_dir=output,
        research_instruments=["BTC-USDT-SWAP", "ADA-USDT-SWAP"],
        public_snapshot_hash="public_hash",
        public_count=20,
        authenticated_hash="authenticated_hash",
        authenticated_count=116,
        authenticated_exact_list_retained=False,
        runtime_snapshot_hash="runtime_hash",
        runtime_instruments=["BTC-USDT-SWAP"],
        v46_evidence_zip_sha256="v46_zip_hash",
        v46_evidence_verification={
            "status": "verified",
            "artifactCount": 15,
            "verifiedArtifacts": [{"verified": True}],
        },
        replay_implementation_path="alphapilot/portfolio_rescue/replay.py",
        replay_implementation_sha256="replay_source_hash",
        replay_parity_percent=100.0,
        replay_parity_audit={"status": "passed", "parityPercent": 100.0},
        generated_at="2026-07-20T00:00:00Z",
        implementation_receipt={
            "patchCommit": "source_commit",
            "unresolvedImplementationBlockers": [],
        },
        test_summary={"status": "passed"},
    )

    required = {
        "v46_portfolio_component_manifest.json",
        "v46_portfolio_cooldown_semantics_audit.json",
        "v46_portfolio_definition_hash.json",
        "v46_portfolio_replay_parity_audit.json",
        "provisional_release_policy.json",
        "provisional_release.json",
        "provisional_release_hash_audit.json",
        "provisional_portfolio_risk_overlay.json",
        "demo_execution_universe_audit.json",
        "cooldown_rejected_signal_ledger.jsonl",
        "demo_approval_request.json",
        "demo_approval_request.md",
        "patch_implementation_receipt.json",
        "patch_test_summary.json",
        "patch_artifact_manifest.json",
    }
    assert required <= {path.name for path in output.iterdir()}
    release = json.loads((output / "provisional_release.json").read_text(encoding="utf-8"))
    component_manifest = json.loads(
        (output / "v46_portfolio_component_manifest.json").read_text(encoding="utf-8")
    )
    assert [row["sourcePath"] for row in component_manifest["components"]] == [
        "short_1h.json",
        "long_1d.json",
        "breakout_1d.json",
    ]
    assert release["route"] == "blocked_waiting_exact_release_approval"
    assert release["approved"] is False
    assert release["demoArm"] is False
    assert result["route"] == "blocked_waiting_exact_release_approval"
