"""Fixed Top 30 OKX USDT swap universe for V13.2.

V13.2 intentionally uses a fixed universe to make the first backtest path
repeatable and avoid dynamic hot-list historical bias.
"""

TOP30_USDT_SWAP_PAIRS = [
    "BTC/USDT:USDT",
    "ETH/USDT:USDT",
    "SOL/USDT:USDT",
    "DOGE/USDT:USDT",
    "XRP/USDT:USDT",
    "ADA/USDT:USDT",
    "AVAX/USDT:USDT",
    "LINK/USDT:USDT",
    "SUI/USDT:USDT",
    "APT/USDT:USDT",
    "OP/USDT:USDT",
    "ARB/USDT:USDT",
    "LTC/USDT:USDT",
    "BCH/USDT:USDT",
    "DOT/USDT:USDT",
    "NEAR/USDT:USDT",
    "PEPE/USDT:USDT",
    "WIF/USDT:USDT",
    "ORDI/USDT:USDT",
    "TON/USDT:USDT",
    "INJ/USDT:USDT",
    "FIL/USDT:USDT",
    "ETC/USDT:USDT",
    "TRX/USDT:USDT",
    "UNI/USDT:USDT",
    "AAVE/USDT:USDT",
    "ATOM/USDT:USDT",
    "SEI/USDT:USDT",
    "TIA/USDT:USDT",
    "FET/USDT:USDT",
]


def get_top30_usdt_swap_pairs() -> list[str]:
    """Return a copy of the fixed V13.2 Top 30 pair list."""
    return TOP30_USDT_SWAP_PAIRS.copy()
