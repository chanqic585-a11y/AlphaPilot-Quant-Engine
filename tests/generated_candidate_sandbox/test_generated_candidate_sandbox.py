from __future__ import annotations

from pathlib import Path

import pytest

from alphapilot.generated_candidate_sandbox.ast_policy import inspect_candidate_source
from alphapilot.generated_candidate_sandbox.file_policy import validate_candidate_path
from alphapilot.generated_candidate_sandbox.resource_limits import ResourceLimits
from alphapilot.generated_candidate_sandbox.runtime import run_candidate


@pytest.mark.parametrize(
    "source,reason",
    [
        ("if False:\n    import requests", "forbidden_import:requests"),
        ("def helper():\n    return __import__('socket')", "forbidden_call:__import__"),
        ("def helper():\n    return eval('1 + 1')", "forbidden_call:eval"),
        ("def helper():\n    return os.getenv('TOKEN')", "forbidden_call:os.getenv"),
        ("def helper():\n    return subprocess.run(['cmd'])", "forbidden_call:subprocess.run"),
    ],
)
def test_ast_policy_rejects_dangerous_code_anywhere(source: str, reason: str) -> None:
    audit = inspect_candidate_source(source)

    assert audit.passed is False
    assert reason in audit.reasons


@pytest.mark.parametrize(
    "candidate_path",
    [
        Path("../escape.py"),
        Path("C:/Users/example/secret.py"),
        Path("credentials/api_key.py"),
    ],
)
def test_file_policy_rejects_path_escape(candidate_path: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        validate_candidate_path(candidate_path, run_directory=tmp_path / "run")


def test_runtime_executes_safe_candidate_in_isolated_process() -> None:
    source = """
def generate(context):
    close = context["close"]
    return {"signal": 1 if close[-1] > close[-2] else 0}
"""

    result = run_candidate(
        source,
        {"close": [100.0, 101.0]},
        limits=ResourceLimits(timeoutSeconds=2.0, memoryMb=128),
    )

    assert result.status == "passed"
    assert result.output == {"signal": 1}
    assert result.audit["offline"] is True
    assert result.audit["inheritedSecretEnvironmentKeys"] == []


def test_runtime_terminates_timeout() -> None:
    source = """
def generate(context):
    while True:
        pass
"""

    result = run_candidate(
        source,
        {},
        limits=ResourceLimits(timeoutSeconds=0.2, memoryMb=128),
    )

    assert result.status == "timeout"
    assert result.output is None
