# Low-Frequency Directional 4H Strategy Rules

These rules describe the V13.4.34 research strategy. They are not trading advice and not execution instructions.

## Long Research Entry

The long candidate requires a score of at least 4 from:

- close above EMA200 and EMA20 above EMA50
- pullback near EMA20 or EMA50 with close reclaiming EMA20
- MACD histogram improving
- RSI14 below 65
- volumeRatio at least 0.8

Additional blockers:

- required indicators must be present
- volume must be positive
- recent 3-bar return must be below +10%

## Short Research Entry

The short candidate requires a score of at least 4 from:

- close below EMA200 and EMA20 below EMA50
- failed bounce near EMA20 or EMA50 with close below EMA20
- MACD histogram weakening
- RSI14 above 35
- volumeRatio at least 0.8

Additional blockers:

- required indicators must be present
- volume must be positive
- recent 3-bar return must be above -10%

## Exits

The strategy uses:

- fixed stoploss: -3%
- fixed ROI: +6%
- time stop after 40 hours if not profitable
- profitable momentum exit if MACD histogram turns against the position

## Audit Columns

The strategy creates `ap_lf_audit_*` columns for local review, including:

- trend state
- pullback or rejection state
- momentum state
- RSI state
- volume state
- long score
- short score
- final long entry
- final short entry
- skip reason

## Boundary

The rules only support historical research backtests. They do not approve Dry-run, live trading, private exchange API use, account access, order creation, or auto trading.

