from __future__ import annotations

import json
from pathlib import Path

from alphapilot.scripts.run_s01_formal_walk_forward import run


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_runner_stops_before_market_data_or_result_reads(tmp_path: Path) -> None:
    route = run(REPO_ROOT, output_root=tmp_path)

    assert route["route"] == "implementation_invalid_requires_new_campaign"
    assert route["formalRunCount"] == 0
    assert route["resultReadCount"] == 0
    assert route["lockedOosAccessCount"] == 0
    assert route["releaseCount"] == 0
    assert route["demoArm"] is False
    assert route["orderCount"] == 0

    audit = json.loads(
        (tmp_path / "formal_execution_contract_audit.json").read_text("utf-8")
    )
    assert audit["marketDataReadCount"] == 0
    assert audit["resultReadCount"] == 0
    assert not any(path.suffix == ".parquet" for path in tmp_path.rglob("*"))
