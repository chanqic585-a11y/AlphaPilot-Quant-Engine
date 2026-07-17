from __future__ import annotations

import json
from pathlib import Path

from alphapilot.formal_validation.formal_evidence_chain_fixture import (
    write_formal_evidence_chain_certification,
)


def _runtime() -> dict[str, object]:
    return {
        "runtimeHash": "runtime-hash",
        "runtimeLoaded": True,
        "strategyLoaded": True,
        "configLoaded": True,
        "dataRootValidated": True,
        "timerangeValidated": True,
        "networkAccessCount": 0,
        "lockedOosReadCount": 0,
        "fallbackUsed": False,
    }


def _fixture() -> dict[str, object]:
    return {
        "fixtureId": "formal_evidence_chain_fixture_v1",
        "fixtureHash": "fixture-hash",
        "fixtureCertified": True,
        "status": "certified",
        "certification": {
            "runtimeLoadedFixture": True,
            "identityMappingCompletenessPct": 100.0,
            "foldAssignmentFixtureCompletenessPct": 100.0,
            "rankingEvidenceFixtureParityPct": 100.0,
            "pitContextFixtureParityPct": 100.0,
            "capacitySemanticsImplementationComplete": True,
            "fundingContractComplete": True,
            "capitalAcceptanceFixtureParityPct": 100.0,
            "positionSizeFixtureParityPct": 100.0,
            "exitFixtureParityPct": 100.0,
        },
        "formalResultCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }


def test_writer_emits_runtime_fixture_and_certification(tmp_path: Path) -> None:
    output_root = tmp_path / "certification"
    written = write_formal_evidence_chain_certification(
        output_root=output_root,
        runtime_report=_runtime(),
        fixture_report=_fixture(),
    )

    assert {path.name for path in written} == {
        "freqtrade_runtime_binding.json",
        "formal_evidence_chain_fixture_v1.json",
        "formal_evidence_chain_certification.json",
    }
    certification = json.loads(
        (output_root / "formal_evidence_chain_certification.json").read_text(
            encoding="utf-8"
        )
    )
    assert certification["status"] == "certified"
    assert certification["runtimeHash"] == "runtime-hash"
    assert certification["fixtureHash"] == "fixture-hash"
    assert certification["formalResultCount"] == 0
    assert certification["releaseCount"] == 0
    assert certification["demoArm"] is False
    assert certification["orderCount"] == 0
    assert certification["formalEvidenceChainCertificationHash"].startswith(
        "formal_evidence_chain_certification_"
    )


def test_writer_fails_closed_when_fixture_is_not_certified(tmp_path: Path) -> None:
    output_root = tmp_path / "certification"
    fixture = _fixture()
    fixture["fixtureCertified"] = False
    fixture["status"] = "blocked"

    try:
        write_formal_evidence_chain_certification(
            output_root=output_root,
            runtime_report=_runtime(),
            fixture_report=fixture,
        )
    except ValueError as exc:
        assert str(exc) == "formal_evidence_chain_fixture_not_certified"
    else:
        raise AssertionError("uncertified fixture must fail closed")

    assert not output_root.exists()
