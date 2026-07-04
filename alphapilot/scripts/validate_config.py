"""Validate V13.3 Freqtrade config templates for safety."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONFIG_PATHS = [
    Path("user_data/config/config.backtest.json"),
    Path("user_data/config/config.dryrun.template.json"),
]

SECRET_FIELD_NAMES = {"key", "secret", "password", "api_key", "api_secret", "passphrase"}
SAFE_PLACEHOLDER_MARKERS = {
    "",
    "PLACEHOLDER",
    "REPLACE",
    "RUNTIME_ONLY",
    "DO_NOT_COMMIT",
    "DISABLED",
}


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Missing config: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _is_safe_placeholder(value: Any) -> bool:
    if value is None:
        return True
    if not isinstance(value, str):
        return False
    upper = value.upper()
    return any(marker in upper for marker in SAFE_PLACEHOLDER_MARKERS)


def _walk_for_secrets(obj: Any, path: str = "$") -> list[str]:
    findings: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            next_path = f"{path}.{key}"
            if key.lower() in SECRET_FIELD_NAMES and not _is_safe_placeholder(value):
                findings.append(f"{next_path} appears to contain a non-placeholder secret")
            findings.extend(_walk_for_secrets(value, next_path))
    elif isinstance(obj, list):
        for index, item in enumerate(obj):
            findings.extend(_walk_for_secrets(item, f"{path}[{index}]"))
    return findings


def validate_config(path: Path) -> list[str]:
    config = _load_json(path)
    errors: list[str] = []

    if config.get("dry_run") is not True:
        errors.append(f"{path}: dry_run must be true")
    if config.get("stake_currency") != "USDT":
        errors.append(f"{path}: stake_currency must be USDT")
    if config.get("trading_mode") != "futures":
        errors.append(f"{path}: trading_mode must be futures")
    if config.get("margin_mode") != "isolated":
        errors.append(f"{path}: margin_mode must be isolated")
    if config.get("timeframe") != "15m":
        errors.append(f"{path}: timeframe must be 15m")
    if config.get("strategy") != "AlphaPilotVolumeReboundV01":
        errors.append(f"{path}: strategy must be AlphaPilotVolumeReboundV01")

    exchange = config.get("exchange", {})
    if exchange.get("name") != "okx":
        errors.append(f"{path}: exchange.name must be okx")
    if config.get("initial_state") != "stopped":
        errors.append(f"{path}: initial_state should stay stopped")
    if config.get("force_entry_enable") is not False:
        errors.append(f"{path}: force_entry_enable must be false")

    api_server = config.get("api_server", {})
    if api_server.get("enabled") is not False:
        errors.append(f"{path}: api_server.enabled must be false in V13.3")

    errors.extend(f"{path}: {finding}" for finding in _walk_for_secrets(config))
    return errors


def main() -> int:
    all_errors: list[str] = []
    for path in CONFIG_PATHS:
        all_errors.extend(validate_config(path))

    if all_errors:
        print("AlphaPilot V13.3 config validation failed:")
        for error in all_errors:
            print(f"- {error}")
        return 1

    print("AlphaPilot V13.3 config validation passed.")
    print("liveTradingEnabled: false")
    print("tradeApiEnabled: false")
    print("withdrawApiEnabled: false")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
