from __future__ import annotations

from alphapilot.derivatives_data.environment_manifest import build_environment_manifest


def test_environment_manifest_records_reproducibility_contract(tmp_path) -> None:
    lock = tmp_path / "requirements-data.txt"
    lock.write_text("pandas==3.0.1\npyarrow==24.0.0\n", encoding="utf-8")

    manifest = build_environment_manifest(
        repo_paths={"quant": tmp_path},
        dependency_lock_path=lock,
        command_output=lambda command, _cwd=None: {
            "git rev-parse HEAD": "abc123",
            "docker --version": "Docker version 29.6.1",
            "docker image inspect freqtradeorg/freqtrade:stable --format {{.Id}}": "sha256:image",
            "python -m pip freeze --all": "numpy==2.3.5\npandas==3.0.1\npyarrow==24.0.0",
            "python -m freqtrade --version": "freqtrade 2026.6",
        }[command],
        python_executable="python",
        docker_image_tag="freqtradeorg/freqtrade:stable",
        random_seeds=[13, 27, 111],
    )

    assert manifest["schemaVersion"] == "reproducibility_environment_manifest_v2"
    assert manifest["storageTimezone"] == "UTC"
    assert manifest["displayTimezone"] == "Asia/Shanghai"
    assert manifest["dependencies"]["pyarrow"] == "24.0.0"
    assert manifest["dependencyLockHash"]
    assert manifest["pipFreezeHash"]
    assert manifest["gitCommits"] == {"quant": "abc123"}
    assert manifest["randomSeeds"] == [13, 27, 111]


def test_environment_manifest_uses_the_selected_python_executable(tmp_path) -> None:
    lock = tmp_path / "requirements-data.txt"
    lock.write_text("pyarrow==24.0.0\n", encoding="utf-8")
    commands: list[str] = []

    def command_output(command: str, _cwd=None) -> str:
        commands.append(command)
        if command == "git rev-parse HEAD":
            return "abc123"
        return ""

    build_environment_manifest(
        repo_paths={"quant": tmp_path},
        dependency_lock_path=lock,
        command_output=command_output,
        python_executable=r"D:\venv path\python.exe",
    )

    assert '"D:\\venv path\\python.exe" -m pip freeze --all' in commands
    assert '"D:\\venv path\\python.exe" -m freqtrade --version' in commands
