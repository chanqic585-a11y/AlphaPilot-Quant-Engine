from __future__ import annotations

from pathlib import Path

from alphapilot.scripts.generate_v13_27_1_12_data_readiness import main


def test_powershell_entrypoint_keeps_default_data_path_ascii_safe() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    script = repo_root / "scripts" / "audit_derivatives_data_capabilities.ps1"
    source = script.read_text(encoding="utf-8")

    source.encode("ascii")
    for codepoint in ("0x56DE", "0x6D4B", "0x6570", "0x636E"):
        assert f"[char]{codepoint}" in source
    assert "[Console]::OutputEncoding = $utf8NoBom" in source
    assert "chcp.com 65001" in source
    assert '$env:PYTHONIOENCODING = "utf-8"' in source


def test_cli_is_plan_only_without_explicit_run(tmp_path, capsys) -> None:
    called = False

    def generator(**kwargs):
        nonlocal called
        called = True
        return {"status": "unexpected"}

    exit_code = main(
        [
            "--repo-root",
            str(tmp_path / "repo"),
            "--data-root",
            str(tmp_path / "data"),
        ],
        generator=generator,
    )

    assert exit_code == 0
    assert called is False
    assert "plan_only" in capsys.readouterr().out


def test_cli_run_forwards_explicit_inputs(tmp_path, capsys) -> None:
    repo = tmp_path / "repo"
    data = tmp_path / "data"
    captured: dict[str, object] = {}

    def generator(**kwargs):
        captured.update(kwargs)
        return {
            "status": "data_not_ready",
            "formalTopLevelDirectionCount": 0,
            "threeDirectionCampaignMayRun": False,
            "qlibCampaignMayRun": False,
        }

    exit_code = main(
        [
            "--repo-root",
            str(repo),
            "--data-root",
            str(data),
            "--checked-at",
            "2026-07-16T02:03:04Z",
            "--run",
        ],
        generator=generator,
    )

    assert exit_code == 0
    assert captured["repo_root"] == Path(repo).resolve()
    assert captured["data_root"] == Path(data).resolve()
    assert captured["checked_at"] == "2026-07-16T02:03:04Z"
    assert callable(captured["probe"])
    assert "data_not_ready" in capsys.readouterr().out
