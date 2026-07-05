# Low-Frequency Directional Score Framework

V13.4.33 defines a simple explanatory score layer for future low-frequency candidates.

Scores:

- `longScore`: 0-5
- `shortScore`: 0-5
- `avoidScore`: 0-5

The scores are not trading signals. They are future report fields for explaining why a candidate looked long-biased, short-biased, or no-trade.

Long score inputs:

- trend up
- pullback quality
- reclaim of EMA20 or EMA50
- volume health
- regime supportive

Short score inputs:

- trend down or rejection
- failed bounce
- momentum weakening
- no chase after large drop
- regime supportive

Avoid score inputs:

- crash or extreme volatility
- technical direction conflict
- data quality issue
- liquidity or spread unavailable
- entry extended beyond risk concept

Regime remains context, not a single hard entry switch.
