# Short Rejection 1H Strategy Rules

`AlphaPilotShortRejection1HV01` is a simple short-only research strategy. It
does not use market regime as a hard gate and does not invert a long strategy.

## Indicators

The strategy computes:

- EMA20
- EMA50
- EMA200
- RSI14
- MACD
- MACD signal
- MACD histogram
- volume rolling mean 20
- volumeRatio
- Bollinger Bands 20 / 2
- ATR14
- recentReturn12h

## Short Score

Each candle starts with `shortScore = 0`.

The following conditions each add 1 point:

- high reaches near EMA20 or EMA50
- close returns below EMA20
- MACD histogram weakens versus the previous candle
- RSI is below 55 and falling
- volumeRatio is at least 1.0

Final entry:

```text
enter_short = 1
when shortScore >= 4
and recentReturn12h > -8%
and atr_pct <= 10%
and required data exists
and volume > 0
```

No long entries are produced.

## Hard Blockers

- missing required indicator data
- recent 12h return <= -8%, to avoid chasing after a large drop
- ATR percentage > 10%, to avoid extreme volatility entries
- zero or invalid volume

## Exit Rules

Stoploss:

```text
stoploss = -0.025
```

Take profit:

```text
minimal_roi = {"0": 0.05}
```

Custom exits:

- `short_time_stop_8h_not_profitable`
- `profitable_short_momentum_exit`

The momentum exit only runs when the position is already profitable and MACD
histogram rises for two consecutive candles, indicating short-side momentum may
be fading.

## Audit Columns

The strategy emits `ap_short_audit_` columns, including:

- rejection area
- close below EMA20
- MACD weakening
- RSI weak
- volume confirmation
- short score
- no chase
- final short entry
- skip reason

Skip reasons include:

```text
data_missing
score_too_low
chase_after_large_drop
extreme_atr
entry_signal_passed
unknown
```
