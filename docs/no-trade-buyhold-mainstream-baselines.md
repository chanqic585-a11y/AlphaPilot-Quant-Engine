# NoTrade and Mainstream BuyHold Baselines

V13.4.32 creates report-only baseline references:

- NoTrade: 0 percent return and 0 percent drawdown, used as an opportunity-cost anchor.
- BuyHold BTC/ETH/SOL: passive historical exposure for each mainstream pair and timeframe.
- EqualWeight BTC/ETH/SOL: simple passive basket exposure.

These baselines are not strategy signals. They only define the historical hurdle a future strategy must clear.

Future strategies should be compared against:

- NoTrade
- same-pair BuyHold
- EqualWeight BTC/ETH/SOL
- drawdown
- volatility
- exposure time
- regime-aware breakdown

V13.4.32 does not run a strategy backtest and does not approve Dry-run or live trading.
