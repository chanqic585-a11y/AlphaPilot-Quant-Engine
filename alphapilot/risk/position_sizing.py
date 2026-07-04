"""Risk-based position sizing helpers."""


def calculate_effective_stop_distance(
    stop_loss_pct: float,
    fee_rate: float,
    slippage_rate: float,
) -> float:
    """Return stop distance including round-trip fees and slippage.

    Example:
        stop=3%, fee=0.05%, slippage=0.05% -> 0.032
    """
    if stop_loss_pct <= 0:
        raise ValueError("stop_loss_pct must be > 0")
    if fee_rate < 0:
        raise ValueError("fee_rate must be >= 0")
    if slippage_rate < 0:
        raise ValueError("slippage_rate must be >= 0")
    return stop_loss_pct + fee_rate * 2 + slippage_rate * 2


def calculate_position_notional(
    account_equity: float,
    risk_per_trade_pct: float,
    stop_loss_pct: float,
    fee_rate: float,
    slippage_rate: float,
) -> float:
    """Calculate notional exposure from risk budget.

    Example:
        account=1000, risk=1%, stop=3%, fee=0.05%, slippage=0.05%
        risk_amount = 10
        effective_stop_distance = 0.032
        position_notional = 312.5
    """
    if account_equity <= 0:
        raise ValueError("account_equity must be > 0")
    if risk_per_trade_pct <= 0:
        raise ValueError("risk_per_trade_pct must be > 0")
    effective_stop_distance = calculate_effective_stop_distance(
        stop_loss_pct,
        fee_rate,
        slippage_rate,
    )
    risk_amount = account_equity * risk_per_trade_pct
    return risk_amount / effective_stop_distance


def calculate_required_margin(position_notional: float, leverage: float) -> float:
    """Calculate required margin.

    Example:
        position_notional=312.5, leverage=5 -> required_margin=62.5
    """
    if position_notional <= 0:
        raise ValueError("position_notional must be > 0")
    if leverage <= 0:
        raise ValueError("leverage must be > 0")
    return position_notional / leverage
