from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CAMPAIGN_ID = "advisory_r_v18_2_s01_formal_evidence_chain_correction_9d02c18f878cc51a"
CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"


def test_failed_r1_attempt_is_terminal_without_result_exposure() -> None:
    leaf = ROOT / "reports" / "formal_validation" / CAMPAIGN_ID / CANDIDATE_ID
    ledger = json.loads((leaf / "formal_run_ledger.json").read_text(encoding="utf-8"))
    attempt = json.loads(
        (leaf / "operational_attempt_ledger.json").read_text(encoding="utf-8")
    )
    route = json.loads((leaf / "route_decision.json").read_text(encoding="utf-8"))

    assert ledger["state"] == "failed"
    assert ledger["attemptCount"] == 1
    assert attempt["formalRunClaimCount"] == 1
    assert attempt["formalRunAttemptCount"] == 1
    for key in (
        "formalResultRunCount",
        "resultReadCount",
        "formalResultArtifactCount",
        "formalEvidenceCount",
        "releaseCount",
        "orderCount",
    ):
        assert attempt[key] == 0
        assert route[key] == 0
    assert route["route"] == "implementation_invalid_requires_new_campaign"
