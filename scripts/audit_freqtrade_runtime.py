from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from alphapilot.formal_validation.freqtrade_runtime import (  # noqa: E402
    PINNED_FREQTRADE_IMAGE,
    build_runtime_manifest,
    build_runtime_smoke,
    compact_command_detail,
    dependency_lock_text,
    parse_freqtrade_version_output,
    parse_json_line,
    write_runtime_evidence,
)


DEFAULT_OUTPUT = Path(
    "reports/formal_validation/v13_27_1_17_s01_phase2_readiness"
)


def _run(command: Sequence[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        list(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )


def _docker_base(docker: str) -> list[str]:
    return [docker, "run", "--rm", "--network", "none"]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit the pinned, network-disabled Freqtrade research runtime."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--docker", default="docker")
    args = parser.parse_args()

    repo_root = args.repo_root.resolve()
    output_root = (
        args.output_root
        if args.output_root.is_absolute()
        else repo_root / args.output_root
    ).resolve()

    version = _run(
        [*_docker_base(args.docker), PINNED_FREQTRADE_IMAGE, "--version"],
        cwd=repo_root,
    )
    if version.returncode != 0:
        print(version.stderr, file=sys.stderr)
        return 2
    observed = parse_freqtrade_version_output(version.stdout)

    dependency_code = (
        "import importlib.metadata as m,json,platform;"
        "names=['freqtrade','ccxt','pandas','numpy','TA-Lib','technical'];"
        "print(json.dumps({**{n:m.version(n) for n in names},"
        "'python':platform.python_version()},sort_keys=True))"
    )
    dependencies = _run(
        [
            *_docker_base(args.docker),
            "--entrypoint",
            "python",
            PINNED_FREQTRADE_IMAGE,
            "-c",
            dependency_code,
        ],
        cwd=repo_root,
    )
    if dependencies.returncode != 0:
        print(dependencies.stderr, file=sys.stderr)
        return 3
    lock_text = dependency_lock_text(parse_json_line(dependencies.stdout))

    docker_version = _run(
        [args.docker, "version", "--format", "{{.Server.Version}}"], cwd=repo_root
    )
    if docker_version.returncode != 0:
        print(docker_version.stderr, file=sys.stderr)
        return 4

    mount = f"type=bind,source={repo_root},target=/repo,readonly"
    config_code = (
        "import json;"
        "p=json.load(open('/repo/user_data/config/config.backtest.json',encoding='utf-8'));"
        "e=p.get('exchange',{});"
        "assert p.get('dry_run') is True;"
        "assert not e.get('key') and not e.get('secret') and not e.get('password');"
        "print('config parsed without credentials')"
    )
    config = _run(
        [
            *_docker_base(args.docker),
            "--mount",
            mount,
            "--entrypoint",
            "python",
            PINNED_FREQTRADE_IMAGE,
            "-c",
            config_code,
        ],
        cwd=repo_root,
    )

    strategy_code = (
        "import importlib.util,sys;sys.path.insert(0,'/repo');"
        "p='/repo/user_data/strategies/AlphaPilotS01BearRecovery4H.py';"
        "s=importlib.util.spec_from_file_location('s01',p);"
        "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
        "c=m.AlphaPilotS01BearRecovery4H;"
        "assert c.candidate_id=='s01_bear_idiosyncratic_selloff_recovery_4h';"
        "assert c.strategy_status=='formal_research_only';"
        "print(c.__name__)"
    )
    strategy = _run(
        [
            *_docker_base(args.docker),
            "--mount",
            mount,
            "--env",
            "PYTHONPATH=/repo",
            "--entrypoint",
            "python",
            PINNED_FREQTRADE_IMAGE,
            "-c",
            strategy_code,
        ],
        cwd=repo_root,
    )

    exits_code = strategy_code.rsplit("print(c.__name__)", 1)[0] + (
        "assert all(callable(getattr(c,n,None)) for n in "
        "['populate_exit_trend','custom_exit','adjust_trade_position','custom_stoploss']);"
        "print('exit hooks callable')"
    )
    exits = _run(
        [
            *_docker_base(args.docker),
            "--mount",
            mount,
            "--env",
            "PYTHONPATH=/repo",
            "--entrypoint",
            "python",
            PINNED_FREQTRADE_IMAGE,
            "-c",
            exits_code,
        ],
        cwd=repo_root,
    )

    command_results = {
        "cliStartup": {
            "returnCode": version.returncode,
            "detail": compact_command_detail(version.stdout, version.stderr),
        },
        "configParse": {
            "returnCode": config.returncode,
            "detail": compact_command_detail(config.stdout, config.stderr),
        },
        "strategyLoad": {
            "returnCode": strategy.returncode,
            "detail": compact_command_detail(strategy.stdout, strategy.stderr),
        },
        "exitHooks": {
            "returnCode": exits.returncode,
            "detail": compact_command_detail(exits.stdout, exits.stderr),
        },
    }
    manifest = build_runtime_manifest(
        image_reference=PINNED_FREQTRADE_IMAGE,
        observed_versions=observed,
        dependency_lock_text=lock_text,
        docker_server_version=docker_version.stdout.strip(),
    )
    smoke = build_runtime_smoke(
        image_reference=PINNED_FREQTRADE_IMAGE,
        command_results=command_results,
        network_mode="none",
    )
    paths = write_runtime_evidence(
        output_root=output_root,
        manifest=manifest,
        dependency_lock_text=lock_text,
        smoke=smoke,
    )
    print(
        json.dumps(
            {
                "status": smoke["status"],
                "imageReference": PINNED_FREQTRADE_IMAGE,
                "evidence": [str(path) for path in paths],
            },
            ensure_ascii=False,
        )
    )
    return 0 if smoke["status"] == "passed" else 5


if __name__ == "__main__":
    raise SystemExit(main())
