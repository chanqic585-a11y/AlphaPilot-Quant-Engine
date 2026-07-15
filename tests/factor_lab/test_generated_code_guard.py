from __future__ import annotations

from alphapilot.factor_lab.generated_code_guard import inspect_generated_source


def test_generated_code_guard_rejects_execution_and_io_capabilities() -> None:
    errors = inspect_generated_source("import os\nvalue = eval('1 + 1')\n")

    assert "dynamic_import_or_import_statement" in errors
    assert "dynamic_execution" in errors


def test_generated_code_guard_accepts_plain_formula_assignment() -> None:
    assert inspect_generated_source("factor = safe_div(delta(close, 1), delay(close, 1))") == []
