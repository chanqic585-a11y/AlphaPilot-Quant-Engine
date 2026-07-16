import subprocess
import sys


def test_cleanup_planner_module_has_no_eager_import_warning() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alphapilot.storage_governance.cleanup_planner", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert "RuntimeWarning" not in result.stderr
