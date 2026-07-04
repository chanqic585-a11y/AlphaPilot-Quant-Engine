"""Global lock skeleton.

V13.2 defaults to research-only mode. Execution is rejected while DEV_LOCK or
TRADE_LOCK is enabled.
"""

STOP = False
DEV_LOCK = True
TRADE_LOCK = True
DATA_LOCK = False
NEWS_LOCK = False
MODEL_LOCK = False
SYMBOL_LOCK = False
STRATEGY_LOCK = False


def explain_active_locks() -> list[str]:
    active = []
    for name, value in {
        "STOP": STOP,
        "DEV_LOCK": DEV_LOCK,
        "TRADE_LOCK": TRADE_LOCK,
        "DATA_LOCK": DATA_LOCK,
        "NEWS_LOCK": NEWS_LOCK,
        "MODEL_LOCK": MODEL_LOCK,
        "SYMBOL_LOCK": SYMBOL_LOCK,
        "STRATEGY_LOCK": STRATEGY_LOCK,
    }.items():
        if value:
            active.append(name)
    return active


def is_execution_allowed() -> bool:
    return len(explain_active_locks()) == 0
