"""Fail-closed loader for the digest-pinned formal Freqtrade runtime."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import re
import subprocess
from typing import Any, Callable

from alphapilot.evolution.registry.hashing import stable_hash

from .freqtrade_runtime import PINNED_FREQTRADE_IMAGE, parse_json_line


EXACT_RUNTIME_VERSIONS = {
    "pythonVersion": "3.14.6",
    "freqtradeVersion": "2026.6",
    "ccxtVersion": "4.5.61",
    "pandasVersion": "3.0.3",
    "numpyVersion": "2.4.6",
    "pyarrowVersion": "24.0.0",
}


class FreqtradeRuntimeUnavailable(RuntimeError):
    """Raised when the exact formal runtime cannot be proven."""


@dataclass(frozen=True)
class FreqtradeRuntimeRequest:
    image_reference: str
    strategy_module: str
    strategy_class: str
    config_path: Path
    data_root: Path
    timerange: str
    timezone: str = "UTC"


def _probe_script(request: FreqtradeRuntimeRequest) -> str:
    return "\n".join(
        (
            "import importlib, json, platform",
            "import ccxt, freqtrade, numpy, pandas, pyarrow",
            f"module = importlib.import_module({request.strategy_module!r})",
            f"strategy = getattr(module, {request.strategy_class!r})",
            "base = strategy.__mro__[1]",
            "print(json.dumps({",
            "  'pythonVersion': platform.python_version(),",
            "  'freqtradeVersion': freqtrade.__version__,",
            "  'ccxtVersion': ccxt.__version__,",
            "  'pandasVersion': pandas.__version__,",
            "  'numpyVersion': numpy.__version__,",
            "  'pyarrowVersion': pyarrow.__version__,",
            "  'strategyClass': strategy.__name__,",
            "  'strategyBase': base.__module__,",
            "  'exitHooksLoaded': all(hasattr(strategy, name) for name in "
            "('populate_exit_trend', 'custom_stoploss', 'adjust_trade_position')),",
            "}, sort_keys=True))",
        )
    )


def _default_runner(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
    return subprocess.run(*args, **kwargs)


def load_freqtrade_runtime(
    request: FreqtradeRuntimeRequest,
    *,
    repo_root: Path,
    runner: Callable[..., Any] = _default_runner,
) -> dict[str, Any]:
    """Load and attest the exact runtime; no static or host fallback is allowed."""

    try:
        repo_root = Path(repo_root).resolve(strict=True)
        config_path = Path(request.config_path).resolve(strict=True)
        data_root = Path(request.data_root).resolve(strict=True)
        if request.image_reference != PINNED_FREQTRADE_IMAGE:
            raise ValueError("image_reference_not_pinned")
        if request.timezone != "UTC":
            raise ValueError("timezone_not_utc")
        if not re.fullmatch(r"\d{8}-\d{8}", request.timerange):
            raise ValueError("timerange_not_frozen")
        if not config_path.is_file() or not data_root.is_dir():
            raise ValueError("config_or_data_missing")
        json.loads(config_path.read_text(encoding="utf-8"))

        command = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--mount",
            f"type=bind,source={repo_root},target=/workspace,readonly",
            "--mount",
            f"type=bind,source={config_path},target=/formal/config.json,readonly",
            "--mount",
            f"type=bind,source={data_root},target=/formal/data,readonly",
            "-e",
            "PYTHONPATH=/workspace",
            "--entrypoint",
            "python",
            request.image_reference,
            "-c",
            _probe_script(request),
        ]
        completed = runner(
            command,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
        if int(completed.returncode) != 0:
            raise RuntimeError(str(completed.stderr or "container probe failed")[:500])
        observed = parse_json_line(str(completed.stdout or ""))
        mismatch = {
            field: {"expected": expected, "observed": observed.get(field)}
            for field, expected in EXACT_RUNTIME_VERSIONS.items()
            if str(observed.get(field)) != expected
        }
        if mismatch:
            raise ValueError(f"runtime_version_mismatch:{mismatch}")
        if observed.get("strategyClass") != request.strategy_class:
            raise ValueError("strategy_class_mismatch")
        if not str(observed.get("strategyBase") or "").startswith("freqtrade."):
            raise ValueError("strategy_not_loaded_by_freqtrade")
        if observed.get("exitHooksLoaded") is not True:
            raise ValueError("exit_hooks_not_loaded")

        binding = {
            "schemaVersion": "freqtrade_runtime_binding_v2",
            "imageReference": request.image_reference,
            "strategyModule": request.strategy_module,
            "strategyClass": request.strategy_class,
            "configPath": config_path.as_posix(),
            "dataRoot": data_root.as_posix(),
            "timerange": request.timerange,
            "timezone": request.timezone,
            **observed,
            "runtimeRequested": True,
            "runtimeLoaded": True,
            "strategyLoaded": True,
            "configLoaded": True,
            "dataRootValidated": True,
            "timerangeValidated": True,
            "networkAccessCount": 0,
            "lockedOosReadCount": 0,
            "fallbackUsed": False,
        }
        binding["runtimeHash"] = stable_hash(binding, prefix="freqtrade_runtime")
        return binding
    except Exception as exc:
        if isinstance(exc, FreqtradeRuntimeUnavailable):
            raise
        raise FreqtradeRuntimeUnavailable(
            f"blocked_freqtrade_runtime:{type(exc).__name__}:{exc}"
        ) from exc
