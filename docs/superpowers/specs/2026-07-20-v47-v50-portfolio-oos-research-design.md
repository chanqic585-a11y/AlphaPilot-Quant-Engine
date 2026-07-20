# V47-V50 Portfolio OOS Research Design

## Decision

The V46 portfolio rescue result remains a development-selected result. V47 verifies its published evidence and records the policy-selection bias. V49 freezes a new, reusable three-sleeve portfolio identity before any new result is read. V50 prepares a bounded research inventory but does not mass-backtest hypotheses in this change.

## Frozen portfolio

- Candidate: `v49_three_mechanism_same_symbol_14d_cooldown_portfolio_v1`
- Sleeves: the three V46 sleeves, with their existing sleeve and ledger hashes.
- Policy: the exact V46 `pair_14d_cooldown` policy and hash.
- No weights, risk allocation, timeframe, direction, or cooldown semantics may be inferred or silently changed.

## Evidence semantics

- V46 policy trials are recorded as six observed development trials.
- The complete upstream strategy-selection history is unavailable, so `selectionTrialCount` is `unavailable`.
- Formal statistical promotion is therefore disallowed from V46 evidence.
- A provisional research-only Demo review may be prepared later, but requires a separate exact-hash approval and cannot count as OOS, forward, formal, or live evidence.
- If no genuinely unread historical interval can be proven, the V49 validation route is `forward_only`.

## Safety

- No exchange credential access.
- No order or release creation.
- No OOS result read while freezing the identity.
- Artifacts are deterministic apart from receipt timestamps and are covered by a SHA-256 manifest.
