from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_ID = "advisory_r_v18_2_s01_formal_evidence_chain_correction_84807fc882f257e1"
CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"


def test_aborted_preregistration_did_not_consume_formal_budget() -> None:
    leaf = ROOT / "reports" / "formal_validation" / CAMPAIGN_ID / CANDIDATE_ID
    attempt = json.loads(
        (leaf / "operational_attempt_ledger.json").read_text(encoding="utf-8")
    )
    route = json.loads((leaf / "route_decision.json").read_text(encoding="utf-8"))

    for key in (
        "formalRunClaimCount",
        "formalRunAttemptCount",
        "formalResultRunCount",
        "resultReadCount",
        "formalResultArtifactCount",
        "releaseCount",
        "orderCount",
    ):
        assert attempt[key] == 0
        assert route[key] == 0
    assert route["route"] == "implementation_invalid_requires_new_campaign"
    assert not (leaf / "formal_run_ledger.json").exists()
