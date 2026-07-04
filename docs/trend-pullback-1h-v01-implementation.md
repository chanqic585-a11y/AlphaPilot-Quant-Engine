# AlphaPilot Trend Pullback 1H V0.1 Implementation

This document records the V13.4.8 implementation of the V13.4.7 V03A+D
selection.

## Strategy File

```text
user_data/strategies/AlphaPilotTrendPullback1HV01.py
```

The strategy is independent from the old Volume Rebound V0.1/V0.2 classes. The
old strategies remain unchanged and archived for research comparison.

## Base Parameters

```text
timeframe = 1h
can_short = False
stoploss = -0.025
minimal_roi = {"0": 0.05}
startup_candle_count = 260
```

ExitProfileA is implemented first. ExitProfileB, the ATR stop plus 2R take
profit profile, is deferred.

## Indicators

The strategy calculates these 1h indicators:

```text
EMA20
EMA50
EMA200
RSI14
MACD
MACD signal
MACD histogram
volume mean 20
volumeRatio
Bollinger Bands 20 / 2
ATR14
ATR percent
```

## Informative Data

The strategy uses:

```text
current pair 4h data
BTC/USDT:USDT 1h data
BTC/USDT:USDT 4h data
```

4h data is merged through Freqtrade informative pair helpers so closed higher
timeframe context is used without future leakage.

## Entry Filters

Final entry requires:

```text
4h trend filter
AND BTC market safety filter
AND 1h pullback location
AND reclaim / confirmation
AND volume quality
AND no-chase filter
AND volume > 0
```

4h trend filter:

```text
close_4h > ema200_4h
ema20_4h >= ema50_4h
ema20_4h >= ema20_4h.shift(1)
```

BTC safety:

```text
btc_1h_return_3 > -0.015
btc_4h_close >= btc_4h_ema200
BTC 1h MACD histogram is not worsening for two consecutive candles
```

Pullback location:

```text
close >= ema50
close >= ema20 * 0.985
close <= ema20 * 1.015
```

Reclaim / confirmation:

```text
close > ema20
macd_histogram > macd_histogram.shift(1)
```

Volume quality:

```text
volumeRatio >= 1.2
```

No-chase and risk quality:

```text
close <= ema20 * 1.02
rsi14 <= 65
atr_pct <= 0.08
```

The simple ATR percent risk quality filter is included in V13.4.8.

## Exit Logic

The strategy implements:

```text
stoploss = -2.5%
ROI = +5%
time stop = 8h if not profitable
profit-only momentum exit = two-candle MACD histogram weakness while current_profit > 0
```

The old V0.1/V0.2 behavior of exiting on MACD weakness while losing is not used
in V03.

## Audit Columns

Audit columns use the `ap_v03_audit_` prefix:

```text
ap_v03_audit_pass_4h_trend
ap_v03_audit_pass_btc_safety
ap_v03_audit_pass_pullback_location
ap_v03_audit_pass_reclaim_confirmation
ap_v03_audit_pass_volume_quality
ap_v03_audit_pass_no_chase
ap_v03_audit_final_entry
ap_v03_audit_skip_reason
```

Skip reasons:

```text
data_missing
weak_4h_trend
btc_not_safe
not_in_pullback_zone
reclaim_not_confirmed
volume_quality_low
price_too_extended
entry_signal_passed
unknown
```

## Safety Boundary

This strategy is research-backtest-only. It does not use real API keys, does not
call Trade API or Withdraw API, does not read accounts or positions, does not
create real orders, does not auto trade, and is not approved for Dry-run.
