from __future__ import annotations

import hashlib
import json
from pathlib import Path

from alphapilot.scripts.run_v37d_source_fidelity_audit import (
    run_v37d_source_fidelity_audit,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _source_audit() -> dict:
    return {
        "archiveSha256": "",
        "manifestHash": "b" * 64,
        "sourceArchiveSha256": "c" * 64,
        "candidates": [
            {
                "candidateId": "ref-mql",
                "equivalenceStatus": "not_source_equivalent",
                "translationClass": "clean_room_research_variant",
                "materialGaps": ["pending order semantics missing"],
                "sources": [
                    {"path": "source.mq4", "sha256": "d" * 64, "sizeBytes": 10}
                ],
            },
            {
                "candidateId": "ref-doc",
                "equivalenceStatus": "deterministic_normalization_only",
                "translationClass": "documentation_normalization",
                "materialGaps": ["qualitative source"],
                "sources": [
                    {"path": "source.txt", "sha256": "e" * 64, "sizeBytes": 10}
                ],
            },
        ],
    }


def test_v37d_runner_builds_deterministic_fail_closed_bundle(
    tmp_path: Path,
    monkeypatch,
) -> None:
    repo = tmp_path / "repo"
    package = tmp_path / "reference.zip"
    package.write_bytes(b"frozen-reference-package")
    package_hash = hashlib.sha256(package.read_bytes()).hexdigest()

    v36 = repo / "v36"
    _write_json(
        v36 / "campaign_summary.json",
        {
            "eligibleCandidateCount": 6,
            "stableSelectionCount": 2,
            "formalRunCount": 0,
            "releaseCount": 0,
        },
    )
    _write_json(
        v36 / "neighborhood_selection.json",
        {
            "selections": [
                {"candidateId": "stable-b", "eligible": True},
                {"candidateId": "stable-a", "eligible": True},
            ]
        },
    )

    v37b = repo / "v37b"
    _write_json(
        v37b / "source_verification.json",
        {"archiveSha256": package_hash, "candidateCount": 18},
    )
    _write_json(
        v37b / "closeout.json",
        {"directionalCandidateCount": 4, "demoReleaseCount": 0},
    )

    source_audit = _source_audit()
    source_audit["archiveSha256"] = package_hash
    v37c = repo / "v37c"
    _write_json(v37c / "source_lineage_audit.json", source_audit)
    _write_json(
        v37c / "v37b_reassessment.json",
        {
            "candidates": [
                {"candidateId": f"ref-{index}", "formalPassed": False}
                for index in range(4)
            ]
        },
    )

    monkeypatch.setattr(
        "alphapilot.scripts.run_v37d_source_fidelity_audit.audit_source_semantics",
        lambda _: source_audit,
    )

    first = run_v37d_source_fidelity_audit(
        repo_root=repo,
        package_path=package,
        v36_run_dir=v36,
        v37b_run_dir=v37b,
        v37c_run_dir=v37c,
    )
    second = run_v37d_source_fidelity_audit(
        repo_root=repo,
        package_path=package,
        v36_run_dir=v36,
        v37b_run_dir=v37b,
        v37c_run_dir=v37c,
    )

    output = Path(first["output"])
    admission = json.loads((output / "source_admission.json").read_text("utf-8"))
    inventory = json.loads((output / "candidate_status_inventory.json").read_text("utf-8"))
    manifest = json.loads((output / "artifact_manifest.json").read_text("utf-8"))

    assert first == second
    assert first["status"] == "completed_no_source_faithful_candidates"
    assert first["runId"].startswith("v37d-source-fidelity-")
    assert admission["sourceFaithfulReadyCount"] == 0
    assert admission["normalizationOnlyCount"] == 1
    assert admission["insufficientSourceEvidenceCount"] == 1
    assert inventory["researchEligibleCount"] == 6
    assert inventory["developmentStableCount"] == 2
    assert inventory["formalPassCount"] == 0
    assert inventory["demoReadyCount"] == 0
    assert inventory["strictlyUsableStrategyCount"] == 0
    assert manifest["safety"]["networkDownloads"] == 0
    assert manifest["safety"]["ordersCreated"] == 0
    for row in manifest["artifacts"]:
        assert hashlib.sha256((output / row["path"]).read_bytes()).hexdigest() == row["sha256"]


def test_v37d_runner_rejects_source_audit_drift(tmp_path: Path, monkeypatch) -> None:
    package = tmp_path / "reference.zip"
    package.write_bytes(b"frozen-reference-package")
    package_hash = hashlib.sha256(package.read_bytes()).hexdigest()
    for folder in ("v36", "v37b", "v37c"):
        (tmp_path / folder).mkdir()
    _write_json(
        tmp_path / "v36/campaign_summary.json",
        {"eligibleCandidateCount": 0, "formalRunCount": 0, "releaseCount": 0},
    )
    _write_json(tmp_path / "v36/neighborhood_selection.json", {"selections": []})
    _write_json(tmp_path / "v37b/source_verification.json", {"archiveSha256": package_hash})
    _write_json(tmp_path / "v37b/closeout.json", {"directionalCandidateCount": 0})
    _write_json(tmp_path / "v37c/source_lineage_audit.json", {"candidates": []})
    _write_json(tmp_path / "v37c/v37b_reassessment.json", {"candidates": []})
    monkeypatch.setattr(
        "alphapilot.scripts.run_v37d_source_fidelity_audit.audit_source_semantics",
        lambda _: {"candidates": [{"candidateId": "drift"}]},
    )

    try:
        run_v37d_source_fidelity_audit(
            repo_root=tmp_path,
            package_path=package,
            v36_run_dir=tmp_path / "v36",
            v37b_run_dir=tmp_path / "v37b",
            v37c_run_dir=tmp_path / "v37c",
        )
    except RuntimeError as error:
        assert "source audit drift" in str(error)
    else:
        raise AssertionError("source audit drift must fail closed")
