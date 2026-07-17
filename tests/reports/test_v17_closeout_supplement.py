from __future__ import annotations

import json
from pathlib import Path

from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.reports.v17_closeout_supplement import (
    build_v17_closeout_supplement,
    write_v17_closeout_supplement,
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_v17_supplement_references_but_does_not_modify_frozen_evidence(
    tmp_path: Path,
) -> None:
    source = (
        REPO_ROOT
        / "reports"
        / "formal_validation"
        / "advisory_r_v17"
        / "campaign_summary.json"
    )
    before = source.read_bytes()

    payload = build_v17_closeout_supplement(
        REPO_ROOT,
        original_evidence_commit="02305adb00000000000000000000000000000000",
        final_closeout_commit="8b7f5aa01de9bf4240d8d4613973291ca19ab83c",
        local_tag="v13.27.1.17",
        tag_target="8b7f5aa01de9bf4240d8d4613973291ca19ab83c",
        upstream_commit="244b0f8f00000000000000000000000000000000",
        remote_tag_exists=False,
        branch_push_status="not_published",
        external_publication_review_status="pending_explicit_user_approval",
    )
    written = write_v17_closeout_supplement(payload, tmp_path)

    assert source.read_bytes() == before
    provenance = payload["provenance"]
    resolution = payload["issueResolution"]
    assert provenance["route"] == "implementation_invalid_requires_new_campaign"
    assert provenance["originalEvidenceCommit"].startswith("02305adb")
    assert provenance["finalCloseoutCommit"].startswith("8b7f5aa")
    assert provenance["localTag"] == "v13.27.1.17"
    assert provenance["tagTarget"] == provenance["finalCloseoutCommit"]
    assert provenance["remoteTagExists"] is False
    assert provenance["branchPushStatus"] == "not_published"
    assert provenance["externalPublicationReviewStatus"] == (
        "pending_explicit_user_approval"
    )
    assert provenance["formalRunCount"] == 0
    assert provenance["lockedOosAccessCount"] == 0
    assert provenance["releaseCount"] == 0
    assert provenance["demoArm"] is False
    assert provenance["orderCount"] == 0
    assert provenance["originalArtifactsModified"] is False
    assert len(provenance["evidenceZipHashes"]) == 3
    assert resolution["P2-02"] == "status_resolved_at_final_closeout"
    assert resolution["historicalLineEndingEvidence"] == "historical_preserved"
    assert resolution["originalLedgerModified"] is False
    source_row = next(
        row
        for row in provenance["artifactHashes"]
        if row["path"].endswith("campaign_summary.json")
    )
    assert source_row["sha256"] == sha256_file(source)
    assert json.loads(written["provenance"].read_text(encoding="utf-8")) == provenance
    assert json.loads(written["issueResolution"].read_text(encoding="utf-8")) == resolution
    manifest = json.loads(written["manifest"].read_text(encoding="utf-8"))
    assert {row["path"] for row in manifest["artifacts"]} == {
        "v17_closeout_provenance_sidecar.json",
        "v17_closeout_issue_resolution_sidecar.json",
    }
    assert written["readme"].is_file()
