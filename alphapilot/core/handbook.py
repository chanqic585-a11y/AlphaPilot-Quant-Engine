"""AlphaPilot default safety handbook policies."""

HANDBOOK_POLICIES = [
    "默认不允许实盘。",
    "默认不允许自动交易。",
    "默认禁止 Withdraw API。",
    "默认 API Key 不进手机 App。",
    "默认所有新策略先观察。",
    "默认所有回测结论不能直接进入实盘。",
    "默认回测盈利不代表实盘可行。",
    "默认所有策略进入 Dry-run 前必须通过执行真实性检查。",
    "默认所有策略进入受控实盘前必须通过 Shadow Trading。",
    "默认所有实盘前必须检查流动性和滑点。",
    "默认所有订单规模必须经过 Liquidity Gate。",
    "默认风控可以否决模型。",
    "默认执行必须写审计记录。",
]


def print_handbook() -> str:
    return "\n".join(f"- {policy}" for policy in HANDBOOK_POLICIES)
