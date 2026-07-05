# Future Low-Frequency Strategy Requirements

Future low-frequency strategy versions must not proceed only because a raw return is positive.

Minimum requirements:

- use BTC/ETH/SOL 4h/1d data with explicit data quality status
- compare against NoTrade, BuyHold, and EqualWeight baselines
- separate long and short logic
- include BTC regime context where available
- report max drawdown, volatility, exposure time, and regime breakdown
- avoid claiming historical baseline results as future performance
- keep Dry-run and live trading disabled until a later explicit approval version
- start from V13.4.33 candidate specs and baseline hurdles before writing any strategy code
- keep first candidate implementations limited to 4-6 core conditions

V13.4.32 is a data and baseline preparation step only. V13.4.33 is a candidate specification and baseline hurdle step only.
