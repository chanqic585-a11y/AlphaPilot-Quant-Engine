from __future__ import annotations

import json
from pathlib import Path

from alphapilot.formal_validation.v18_2_evidence_chain import (
    validate_evidence_chain_configuration,
)


ROOT = Path(__file__).resolve().parents[2]
CERTIFICATION_ROOT = (
    ROOT / "reports" / "formal_validation" / "v18_2_pre_result_certification"
)


def test_certified_runtime_binding_passes_execution_entry_gate() -> None:
    runtime = json.loads(
        (CERTIFICATION_ROOT / "freqtrade_runtime_binding.json").read_text(
            encoding="utf-8"
        )
    )
    certification = json.loads(
        (CERTIFICATION_ROOT / "formal_evidence_chain_certification.json").read_text(
            encoding="utf-8"
        )
    )

    validated_runtime, validated_certification = (
        validate_evidence_chain_configuration(
            {
                "enabled": True,
                "runtimeBinding": runtime,
                "certification": certification,
            }
        )
    )

    assert validated_runtime["runtimeRequested"] is True
    assert validated_runtime["runtimeLoaded"] is True
    assert validated_certification["status"] == "certified"
