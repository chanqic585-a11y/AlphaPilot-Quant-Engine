"""Print AlphaPilot Quant Engine V13.2 skeleton status."""

from alphapilot.core.locks import explain_active_locks
from alphapilot.universe.top30_usdt_swap import get_top30_usdt_swap_pairs


def main() -> int:
    print("AlphaPilot Quant Engine V13.2")
    print("mode: skeleton")
    print("liveTradingEnabled: false")
    print("tradeApiEnabled: false")
    print("withdrawApiEnabled: false")
    print("strategy: AlphaPilotVolumeReboundV01")
    print("universe: fixed top30")
    print(f"universeSize: {len(get_top30_usdt_swap_pairs())}")
    print("proposalSystem: ready skeleton")
    print("riskGate: ready skeleton")
    print("auditLedger: ready skeleton")
    print(f"activeLocks: {', '.join(explain_active_locks())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
