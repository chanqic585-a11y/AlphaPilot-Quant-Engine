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

V13.4.32 is a data and baseline preparation step only.
