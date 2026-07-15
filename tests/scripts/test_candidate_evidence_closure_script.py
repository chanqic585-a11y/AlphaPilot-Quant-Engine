from pathlib import Path


def test_candidate_evidence_closure_script_exposes_safe_switch_interface() -> None:
    script = (
        Path(__file__).resolve().parents[2]
        / "scripts"
        / "run_candidate_evidence_closure.ps1"
    ).read_text(encoding="utf-8")

    for switch in (
        "[switch]$PreRegister",
        "[switch]$RunSignalValidation",
        "[switch]$RunLockedValidation",
        "[switch]$RunRiskModels",
        "[switch]$RunAll",
        "[string]$CandidateTier",
    ):
        assert switch in script

    assert "PLAN ONLY" in script
    assert "Only -RunAll executes the complete locked validation" in script
