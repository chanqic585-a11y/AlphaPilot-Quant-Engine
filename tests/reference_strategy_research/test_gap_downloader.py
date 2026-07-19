from __future__ import annotations

from pathlib import Path

from alphapilot.reference_strategy_research.gap_downloader import execute_gap_plan


def test_empty_gap_plan_never_calls_fetcher(tmp_path: Path) -> None:
    calls = []

    result = execute_gap_plan(
        gaps=[],
        checkpoint_path=tmp_path / "checkpoint.json",
        fetcher=lambda gap: calls.append(gap),
        dry_run=False,
    )

    assert result["status"] == "complete"
    assert result["completedCount"] == 0
    assert calls == []


def test_dry_run_records_gap_without_network_call(tmp_path: Path) -> None:
    calls = []
    gap = {"instrumentId": "ETH-USDT-SWAP", "timeframe": "1h"}

    result = execute_gap_plan(
        gaps=[gap],
        checkpoint_path=tmp_path / "checkpoint.json",
        fetcher=lambda row: calls.append(row),
        dry_run=True,
    )

    assert result["status"] == "planned"
    assert result["pending"] == [gap]
    assert calls == []
