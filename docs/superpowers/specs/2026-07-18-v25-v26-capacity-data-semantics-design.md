# V25-V26 Capacity Data Semantics Design

## Decision

V25 repairs the evidence classification and data contract. V26 may replay the
single frozen candidate only when every Formal input has preregistered,
machine-verifiable semantics.

The V19-V24 result remains immutable. A sidecar clarifies that the previous
zero-trade outcome was caused by an incompatible capacity-data contract, not a
valid economic failure and not an implementation failure.

## Layered readiness

- Signal-ready: all fields needed to create candidate events are available.
- Formal-ready: ranking, exit, capital, cost, benchmark, and statistical fields
  are semantically verified for the frozen window.
- Demo-ready: Formal readiness plus instrument, lot-size, tick-size, and Demo
  runtime fields.

Missing mandatory fields block before a Formal claim. A blocked data check does
not consume Claim, Attempt, Result, or Read budget.

## Volume semantics

The provenance audit binds each selected field to its raw source, source hash,
canonical reader mapping, unit, availability clock, exchange identity, and
market type. `close * volume` is never labeled exact turnover. Contract-volume
conversion fails closed unless contract metadata is complete.

The verified V25 route uses direct quote turnover from
`volume_quote_currency`. All 24 required instrument/timeframe datasets are
exactly verified; no conservative lower bound is needed.

## Capacity certification

The frozen candidate is evaluated only for real signal creation and capacity
computability inside the formal time window. The certification must not read
PnL, exits, statistical results, benchmark outcomes, or Locked OOS.

The certified data-only universe contains ADA, BCH, BTC, ETC, ETH, LINK, LTC,
and XRP USDT swaps. It is selected only from semantic readiness and coverage,
never from candidate performance.

## Frozen identity

V26 is prohibited from changing the candidate definition, direction,
timeframe, entry, stop, exit policy, maximum hold, capital-policy values,
costs, split, gates, benchmark, or statistical policy. Only the data profile,
data snapshot, campaign identity, preregistration hash, and future-OOS identity
may change.

## Current route

Capacity Profile `ohlcv_verified_capacity_v2` is ready and real-signal capacity
certification passes. The frozen generated candidate does not preregister the
definitions required to derive `eventExtremeResidualZ` and `recoverySizeZ`.
Borrowing S01 defaults would mutate or guess the frozen contract.

Therefore the mechanical route is
`formal_data_blocked_capacity_semantics`. V26 is not started, no Formal budget
is consumed, and no Release, approval, Demo ARM, Live path, or order is created.
