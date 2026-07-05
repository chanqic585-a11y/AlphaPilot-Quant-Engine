# Rejected Strategy Hypotheses

V13.4.25 keeps rejected strategy ideas visible so the project does not keep
recycling weak or unsafe mechanisms.

Rejected entries are research artifacts. They are not strategy code and not
trading permissions.

## HYP-R01 Martingale Rejected

Martingale, inverse averaging, and recovery-size escalation are rejected because
they create unacceptable tail risk and conflict with AlphaPilot risk-first
principles.

Status:

```text
rejected
```

## HYP-R02 RSI Only Rejected

RSI-only mean reversion is rejected as a standalone strategy idea.

The V13.4.24 benchmark review showed that simple RSI mean reversion failed as a
benchmark and was cost sensitive. RSI may still be studied as context inside a
multi-factor validation dataset.

Status:

```text
rejected
```

## HYP-R03 Simple EMA Cross Rejected

Simple EMA cross or plain EMA trend entries are rejected as standalone strategy
hypotheses.

EMA context may still be useful for regime or pullback distance, but tuning EMA
lengths on the failed simple benchmark is not a valid next step.

Status:

```text
rejected
```

## HYP-R04 MACD Volume Only Rejected

MACD plus volume alone is rejected as a standalone strategy hypothesis.

Momentum and volume can remain contextual factors, but the simple benchmark did
not provide usable evidence.

Status:

```text
rejected
```

## Safety Boundary

Rejected means:

- do not implement as a strategy
- do not run as Dry-run
- do not use as live logic
- do not convert into an order mechanism

Rejected does not mean the input indicators are banned from future contextual
research.
