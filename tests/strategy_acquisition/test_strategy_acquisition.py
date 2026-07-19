from __future__ import annotations

from pathlib import Path

import pytest

from alphapilot.evolution.registry.database import connect_registry
from alphapilot.strategy_acquisition.lifecycle import InvalidLifecycleTransition
from alphapilot.strategy_acquisition.mechanism_extract import (
    FormulaHallucinationBlocked,
    build_extracted_artifact,
)
from alphapilot.strategy_acquisition.models import SourceEvidence, StrategyArtifact
from alphapilot.strategy_acquisition.source_ingest import ingest_source
from alphapilot.strategy_acquisition.store import StrategyArtifactStore


def _artifact() -> StrategyArtifact:
    evidence = SourceEvidence(
        sourceId="source-vibe-pinned",
        sourcePath="agent/src/skills/strategy-dev-manager/SKILL.md",
        locator="lines 30-110",
        sourceHash="a" * 64,
        extractionConfidence=0.95,
    )
    return build_extracted_artifact(
        artifactId="artifact-funding-carry",
        artifactType="strategy",
        name="Positive funding delta-neutral carry",
        familyId="funding-carry",
        authorityRef="campaign:v37i-funding-carry",
        sourceIds=(evidence.sourceId,),
        sourceHashes=(evidence.sourceHash,),
        licenseClass="MIT",
        sourceEquivalenceClass="mechanism_only",
        marketMechanism="Capture positive perpetual funding while hedging delta.",
        formula="funding_income - fees - slippage - basis_risk",
        requiredFields=("funding_rate", "spot_mid", "perp_mid"),
        universe=("BTC-USDT", "ETH-USDT", "SOL-USDT"),
        timeframe="8h_event",
        entryRules=("funding_rate > preregistered_threshold",),
        exitRules=("funding_rate <= exit_threshold",),
        positionSizing="matched spot/perpetual notional",
        riskManagement="one-leg failure and basis risk kill switches",
        dataProfile={"pointInTime": True, "fundingAvailableAtRequired": True},
        evidence=(evidence,),
    )


def test_store_is_projection_with_append_only_lifecycle_history(tmp_path: Path) -> None:
    connection = connect_registry(tmp_path / "registry.sqlite")
    store = StrategyArtifactStore(connection)
    try:
        registered = store.register(_artifact())
        transitioned = store.transition(
            registered.artifactId,
            "mechanism_extracted",
            reason_code="source_evidence_verified",
            evidence={"sourceHash": "a" * 64},
        )
        history = store.lifecycle_history(registered.artifactId)
    finally:
        connection.close()

    assert registered.authorityRef == "campaign:v37i-funding-carry"
    assert transitioned.status == "mechanism_extracted"
    assert [row["nextStatus"] for row in history] == [
        "source_ingested",
        "mechanism_extracted",
    ]
    assert history[0]["eventHash"] != history[1]["eventHash"]


def test_store_rejects_skipped_lifecycle_transition(tmp_path: Path) -> None:
    connection = connect_registry(tmp_path / "registry.sqlite")
    store = StrategyArtifactStore(connection)
    try:
        artifact = store.register(_artifact())
        with pytest.raises(InvalidLifecycleTransition):
            store.transition(
                artifact.artifactId,
                "formal_pass",
                reason_code="cannot_skip_evidence",
                evidence={},
            )
    finally:
        connection.close()


def test_formula_without_locator_evidence_is_blocked() -> None:
    with pytest.raises(FormulaHallucinationBlocked, match="formula_hallucination_blocked"):
        build_extracted_artifact(
            artifactId="artifact-no-evidence",
            artifactType="factor",
            name="Unsupported factor",
            familyId="unsupported",
            authorityRef="campaign:test",
            sourceIds=("source-1",),
            sourceHashes=("b" * 64,),
            licenseClass="unknown",
            sourceEquivalenceClass="insufficient_source_evidence",
            marketMechanism="Unknown",
            formula="rank(close)",
            requiredFields=("close",),
            universe=("BTC-USDT-SWAP",),
            timeframe="1h",
            entryRules=(),
            exitRules=(),
            positionSizing="none",
            riskManagement="none",
            dataProfile={"pointInTime": True},
            evidence=(),
        )


def test_compiled_black_box_is_metadata_only(tmp_path: Path) -> None:
    source = tmp_path / "opaque.ex4"
    source.write_bytes(b"compiled-binary-placeholder")

    result = ingest_source(source)

    assert result.sourceType == "compiled_black_box"
    assert result.metadataOnly is True
    assert result.formulaExtractionAllowed is False
    assert result.sourceHash
