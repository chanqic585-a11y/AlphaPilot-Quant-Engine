# Strategy: AlphaPilot Volume Rebound V0.1

## Positioning

AlphaPilot Volume Rebound V0.1 is a long-only research strategy for historical
backtesting. It looks for rebound attempts after a pullback with stronger
volume. It is not a live signal and not trading advice.

## Indicators

The strategy computes:

- EMA20
- EMA200
- RSI14
- MACD
- MACD signal
- MACD histogram
- 20-candle rolling volume mean
- volumeRatio
- Bollinger Bands 20 / 2

Informative data:

- Current pair 4h close / EMA20 / EMA200
- BTC/USDT:USDT 15m close and 3-candle return

## Entry Conditions

All conditions must be true:

1. BTC 3-candle 15m return is greater than -1%.
2. 4h close is at least `EMA200 * 0.98`.
3. RSI14 is between 30 and 55.
4. volumeRatio is at least 1.5.
5. MACD histogram is higher than the previous candle.
6. close is at least `EMA20 * 0.995`.
7. close is no higher than `Bollinger middle * 1.01`.

If BTC or 4h informative data is missing, V13.3 blocks entry rather than
silently ignoring the filter.

## Exit Conditions

- Fixed stoploss: -3%.
- Fixed take profit: +3% through `minimal_roi`.
- MACD histogram weakens for two consecutive candles.
- Time stop: after 12 x 15m candles if the trade is still not profitable.

## Skip Reasons

The strategy and report schema reserve the following skip reasons:

- `btc_crash_filter`
- `weak_4h_trend`
- `rsi_out_of_range`
- `volume_ratio_too_low`
- `macd_not_improving`
- `price_too_extended`
- `data_missing`

V13.3 records these as strategy columns and report schema placeholders. Later
versions can aggregate skipped signal counts from backtest internals.

## Cost Model

- Fee rate: 0.05% one-way via `--fee 0.0005` in the backtest wrapper.
- Slippage rate: 0.05% one-way is recorded in the report schema as planned,
  but it is not yet applied by the Freqtrade command.

The exporter does not pretend planned slippage has been applied.

## Safety

This strategy does not use real exchange credentials. It does not place orders,
does not read balances or positions, and does not run live trading.
