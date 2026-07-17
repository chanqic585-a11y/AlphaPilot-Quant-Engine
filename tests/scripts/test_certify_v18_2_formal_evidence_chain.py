from __future__ import annotations

import json
from pathlib import Path

from alphapilot.scripts.certify_v18_2_formal_evidence_chain import certify


def test_certify_binds_runtime_and_writes_certification(tmp_path: Path) -> None:
    repo_root = tmp_path / "repo"
    config_path = repo_root / "config.json"
    data_root = tmp_path / "data"
    output_root = repo_root / "reports" / "v18_2_certification"
    repo_root.mkdir()
    data_root.mkdir()
    config_path.write_text("{}", encoding="utf-8")

    captured: dict[str, object] = {}

    def fake_loader(request, *, repo_root: Path):
        captured["request"] = request
        captured["repo_root"] = repo_root
        return {
            "runtimeHash": "runtime-hash",
            "pythonVersion": "3.14.6",
            "freqtradeVersion": "2026.6",
            "ccxtVersion": "4.5.61",
            "pandasVersion": "3.0.3",
            "numpyVersion": "2.4.6",
            "pyarrowVersion": "24.0.0",
            "timezone": "UTC",
            "runtimeLoaded": True,
            "strategyLoaded": True,
            "configLoaded": True,
            "dataRootValidated": True,
            "timerangeValidated": True,
            "networkAccessCount": 0,
            "lockedOosReadCount": 0,
            "fallbackUsed": False,
        }

    result = certify(
        repo_root=repo_root,
        config_path=config_path,
        data_root=data_root,
        timerange="20210122-20260515",
        output_root=output_root,
        runtime_loader=fake_loader,
    )

    assert result["status"] == "certified"
    assert result["formalResultCount"] == 0
    request = captured["request"]
    assert request.strategy_class == "AlphaPilotS01BearRecovery4H"
    assert request.timerange == "20210122-20260515"
    assert captured["repo_root"] == repo_root
    certification = json.loads(
        (output_root / "formal_evidence_chain_certification.json").read_text(
            encoding="utf-8"
        )
    )
    assert certification["status"] == "certified"
