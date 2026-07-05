# Future Short Research Recommendations

V13.4.30 recommends pausing direct continuation of `AlphaPilotShortRejection1HV01`.

## Do Not Continue

Do not continue the V13.4.29 short rejection strategy as the active short mainline.

Reasons:

- Expanded total return was near-total loss.
- Max drawdown was near-total loss.
- Profit factor was below 1.
- Trade count was excessive.
- Stop-loss exits dominated losses.
- Slippage-adjusted metrics were worse.

## Better Short Research Requirements

Future short research should wait for stronger evidence:

- Public funding/open-interest data.
- Lower trade frequency.
- Stronger triggers such as failed breakout, lower-high confirmation, or relative weakness.
- Per-trade regime attribution.
- Exit reason loss attribution.
- Direction-separated metrics.

## Recommended Next Version

Default recommendation:

```text
V13.4.31 - Low-Frequency Mainstream Coin Research Plan
```

Why:

- Current 1h high-frequency research has repeatedly failed.
- BTC/ETH/SOL and 4h/1d research would reduce noise.
- A research specification should come before any new strategy code.

Alternative if short research remains the priority:

```text
V13.4.31 - Funding/OI Public Data Collector
```

This would improve short research inputs before writing another short strategy.
