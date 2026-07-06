"""Generate V13.7.1 strategy runtime data contract files.

This command reads existing local research reports and writes standardized
runtime JSON files for the desktop and mobile consoles. It is file-only and
does not connect to exchanges, use API keys, create orders, or auto trade.
"""

from __future__ import annotations

import argparse
import json

from alphapilot.runtime.runtime_contract import generate_runtime_contract


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate V13.7.1 AlphaPilot runtime contract files.")
    parser.add_argument("--signal-limit", type=int, default=120)
    parser.add_argument("--observation-limit", type=int, default=120)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = generate_runtime_contract(signal_limit=args.signal_limit, observation_limit=args.observation_limit)
    runtime = payload["runtimeStatus"]
    print(
        json.dumps(
            {
                "version": runtime["version"],
                "activeStrategyId": (runtime.get("activeStrategy") or {}).get("strategyId"),
                "signalTapeCount": runtime.get("signalTapeCount"),
                "paperObservationCount": runtime.get("paperObservationCount"),
                "runtimeHealth": runtime.get("runtimeHealth"),
                "tradeApiUsed": runtime.get("safetyBoundary", {}).get("tradeApiUsed"),
                "createsOrders": runtime.get("safetyBoundary", {}).get("createsOrders"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

