from __future__ import annotations

from pathlib import Path

from alphapilot.scripts.generate_v13_27_1_11_data_readiness import main


def test_cli_forwards_explicit_roots_and_returns_success(tmp_path, capsys) -> None:
    repo = tmp_path / "repo"
    external = tmp_path / "external"
    captured: dict[str, object] = {}

    def generator(**kwargs):
        captured.update(kwargs)
        return {
            "status": "data_not_ready",
            "campaignMayRun": False,
            "formalReadyDirectionCount": 0,
            "reportRoot": str(repo / "reports" / "derivatives_data"),
        }

    exit_code = main(
        [
            "--repo-root",
            str(repo),
            "--external-data-root",
            str(external),
            "--checked-at",
            "2026-07-16T01:02:03Z",
        ],
        generator=generator,
    )

    assert exit_code == 0
    assert captured["repo_root"] == Path(repo).resolve()
    assert captured["external_data_root"] == Path(external).resolve()
    assert captured["checked_at"] == "2026-07-16T01:02:03Z"
    assert "data_not_ready" in capsys.readouterr().out
