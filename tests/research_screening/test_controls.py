from alphapilot.research_screening.controls import run_evaluator_controls


def test_positive_control_passes_and_negative_controls_fail() -> None:
    report = run_evaluator_controls(seed=17)

    assert report["positiveControl"]["passed"]
    assert all(not item["passed"] for item in report["negativeControls"])
