from __future__ import annotations

import json
from pathlib import Path

from alphapilot.mechanism_breakthrough.program import write_successor_program_evidence


def test_successor_program_keeps_research_and_demo_ledgers_isolated(tmp_path: Path) -> None:
    result = write_successor_program_evidence(
        output_root=tmp_path,
        frozen_at="2026-07-20T00:00:00Z",
        quant_merge_commit="quant-merge",
        console_merge_commit="console-merge",
        docs_merge_commit="docs-merge",
        inherited_full_backtests=91,
        demo_credentials_injected=False,
    )

    assert result["researchTrackStatus"] == "ready"
    assert result["productTrackStatus"] == "blocked_demo_credentials_not_injected"
    assert (tmp_path / "program_ledger.jsonl").is_file()
    assert (tmp_path / "product_engineering_ledger.jsonl").is_file()
    assert (tmp_path / "research_evidence_ledger.jsonl").is_file()
    spec = json.loads((tmp_path / "program_spec.json").read_text(encoding="utf-8"))
    assert spec["trackIsolation"]["engineeringSmokeQualifiesStrategy"] is False
    assert spec["liveEnabled"] is False
    assert spec["withdrawEnabled"] is False

