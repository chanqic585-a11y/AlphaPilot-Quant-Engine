# Probability Gate Research vs Trading Boundary

V13.4.19 defines three gate layers and keeps them separate.

## Current Gate

The current validation gate remains:

```text
sampleCount >= 50
hitTpBeforeSlProbability >= 0.45
profitFactor >= 1.2
expectancy > 0
```

V13.4.19 does not loosen this default gate and does not wire coarsened buckets to
strategy entry.

## Research Gate

The research gate is used to identify broad buckets worth investigating:

```text
sampleCount >= 50
profitFactor >= 1.1
expectancy > 0
```

This is not used for trading.

## Exploratory Gate

The exploratory gate is used only to find weak signals for manual review:

```text
sampleCount >= 30
profitFactor > 1.0
```

This is for analysis only and must not be connected to strategy entry.

## Safety Boundary

Coarsened probability tables are research artifacts. They are not strategy
approval, not a Dry-run approval, not live trading approval, and not execution
commands.
