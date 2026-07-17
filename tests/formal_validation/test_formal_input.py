from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from alphapilot.advisory_r_campaign.candidates import build_candidate_inventory
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.formal_validation.formal_input import FormalInputError, load_formal_input


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    repo_root = tmp_path / "repo"
    data_root = tmp_path / "data"
    candidate = next(
        row
        for row in build_candidate_inventory()
        if row["candidateId"] == "s01_bear_idiosyncratic_selloff_recovery_4h"
    )
    dates = pd.date_range("2025-01-01", periods=8, freq="4h", tz="UTC")
    references = []
    for offset, symbol in enumerate(("BTC-USDT-SWAP", "ETH-USDT-SWAP")):
        relative = Path("canonical") / symbol / "4h" / "part.parquet"
        path = data_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        base = 100.0 + offset * 10.0
        pd.DataFrame(
            {
                "date": dates,
                "open": [base + value for value in range(8)],
                "high": [base + value + 1.0 for value in range(8)],
                "low": [base + value - 1.0 for value in range(8)],
                "close": [base + value + 0.5 for value in range(8)],
                "volume": [1000.0 + value for value in range(8)],
                "confirmed": [1] * 8,
            }
        ).to_parquet(path, index=False)
        references.append(
            {
                "instrumentId": symbol,
                "timeframe": "4h",
                "path": relative.as_posix(),
                "provider": "fixture",
                "rowCount": 8,
                "sha256": sha256_file(path),
                "effectiveBacktestStart": dates[0].isoformat(),
                "latestConfirmed": dates[-1].isoformat(),
            }
        )

    snapshot = {
        "snapshotId": "snapshot_fixture",
        "snapshotHash": "snapshot_hash_fixture",
        "coreUniverseHash": "core_universe_hash_fixture",
        "datasetReferences": references,
    }
    snapshot_path = repo_root / "research" / "data_snapshots" / "snapshot_fixture.json"
    _write_json(snapshot_path, snapshot)

    preregistration = {
        "schemaVersion": "s01_formal_walk_forward_preregistration_v1",
        "campaignId": "advisory_r_v17_fixture",
        "sourceCampaignId": "advisory_r_v16_fixture",
        "sourceCandidateId": candidate["candidateId"],
        "strategyDefinitionHash": candidate["strategyDefinitionHash"],
        "exitPolicyHash": candidate["exitPolicyHash"],
        "implementationConformanceHash": "implementation_fixture",
        "dataSnapshotId": snapshot["snapshotId"],
        "dataSnapshotHash": snapshot["snapshotHash"],
        "coreUniverseHash": snapshot["coreUniverseHash"],
        "coreUniverse": {
            "instrumentCount": 2,
            "instrumentIds": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
            "selection": "fixture",
            "fixedCohortLimitation": True,
        },
        "splitPolicy": {
            "timeframe": "4h",
            "commonStart": dates[0].isoformat(),
            "commonCutoffExclusive": (dates[-1] + pd.Timedelta(hours=4)).isoformat(),
            "sampleCount": 8,
        },
        "lockedOosPolicy": {
            "cleanLockedOosAvailable": False,
            "contentRead": False,
            "accessCount": 0,
        },
        "candidateCount": 1,
        "parameterChanges": 0,
        "exitPolicyChanges": 0,
        "universeChanges": 0,
        "costChanges": 0,
    }
    preregistration["preregistrationHash"] = stable_hash(
        preregistration, prefix="s01_formal_walk_forward_preregistration"
    )
    preregistration_path = (
        repo_root
        / "research"
        / "preregistrations"
        / "advisory_r_v17_fixture.json"
    )
    _write_json(preregistration_path, preregistration)
    return repo_root, data_root, preregistration_path


def test_load_formal_input_verifies_identity_hashes_and_common_index(
    tmp_path: Path,
) -> None:
    repo_root, data_root, preregistration_path = _fixture(tmp_path)

    bundle = load_formal_input(
        repo_root=repo_root,
        data_root=data_root,
        preregistration_path=preregistration_path,
    )

    assert bundle.candidate["candidateId"] == (
        "s01_bear_idiosyncratic_selloff_recovery_4h"
    )
    assert list(bundle.frames) == ["BTC-USDT-SWAP", "ETH-USDT-SWAP"]
    assert len(bundle.commonIndex) == 8
    assert all(len(frame) == 8 for frame in bundle.frames.values())
    assert bundle.inputMapping["verifiedPartitionCount"] == 2
    assert bundle.inputMapping["snapshotHashValid"] is True
    assert bundle.inputMapping["candidateIdentityValid"] is True
    assert bundle.holdoutLineage["lockedOosAccessCount"] == 0
    assert bundle.holdoutLineage["contentRead"] is False


def test_load_formal_input_rejects_partition_hash_drift(tmp_path: Path) -> None:
    repo_root, data_root, preregistration_path = _fixture(tmp_path)
    partition = data_root / "canonical" / "ETH-USDT-SWAP" / "4h" / "part.parquet"
    with partition.open("ab") as handle:
        handle.write(b"drift")

    with pytest.raises(FormalInputError, match="partition_hash_mismatch"):
        load_formal_input(
            repo_root=repo_root,
            data_root=data_root,
            preregistration_path=preregistration_path,
        )


def test_load_formal_input_rejects_candidate_identity_drift(tmp_path: Path) -> None:
    repo_root, data_root, preregistration_path = _fixture(tmp_path)
    payload = json.loads(preregistration_path.read_text(encoding="utf-8"))
    payload["strategyDefinitionHash"] = "changed"
    core = {key: value for key, value in payload.items() if key != "preregistrationHash"}
    payload["preregistrationHash"] = stable_hash(
        core, prefix="s01_formal_walk_forward_preregistration"
    )
    _write_json(preregistration_path, payload)

    with pytest.raises(FormalInputError, match="candidate_identity_mismatch"):
        load_formal_input(
            repo_root=repo_root,
            data_root=data_root,
            preregistration_path=preregistration_path,
        )
