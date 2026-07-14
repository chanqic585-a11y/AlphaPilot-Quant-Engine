# Negative Research Rules

The machine-readable rules live in
`reports/archived_failed_strategy_negative_rules.json`.

Core rules:

1. Do not promote profit factor below 1 or non-positive average net R.
2. Do not rescue structural failure with small threshold changes alone.
3. Review fees and slippage before interpreting raw return.
4. Treat high-frequency negative edge as noise amplification, not
   diversification.
5. Never turn missing evidence into zero or passing evidence.
6. Require signal and account/risk layers to pass independently.
7. Reject Martingale and inverse-averaging risk designs.
8. Require a new version and fresh evidence before any archived idea is
   reconsidered.

These rules narrow future research. They do not generate a trade signal or
change an execution release.
