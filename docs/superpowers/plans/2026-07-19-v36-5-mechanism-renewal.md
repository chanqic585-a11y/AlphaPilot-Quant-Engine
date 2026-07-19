# AlphaPilot V36.5 - Independent Mechanism Renewal

## Status

- Branch: `feature/v13.27.1.36.5-mechanism-renewal`
- Scope: Research and Development evidence only
- Live / Demo / Release: disabled unless a candidate independently passes every frozen gate
- Locked OOS reads before Formal: `0`

## Why no usable strategy has survived

The current result is not primarily caused by the former fixed `2R` rule. The archived evidence is dominated by signal-edge failure and cost amplification. The three executable V35 families are exhausted under the approved family budget:

1. Pair relative value failed Development stability and positive-expectancy checks.
2. Conditional mean reversion failed Development stability and positive-expectancy checks.
3. TSMOM produced a stable Development candidate, but its single Formal run failed after costs, stress, drawdown and benchmark comparison (`PF 0.4893`, average net `-0.3602R`).

Retuning those families again would be a third rescue attempt and would increase selection bias. Zero survivors is therefore a valid research result, not an engineering failure.

## Independent mechanism triage

### Executable now: intraday session predictability

Primary sources report systematic intraday periodicity and time-varying short-horizon predictability in cryptocurrency markets. They do not establish a permanent net-of-cost alpha, so AlphaPilot treats the mechanism as a falsifiable hypothesis:

- [Periodicity in Cryptocurrency Volatility and Liquidity](https://arxiv.org/abs/2109.12142)
- [Bitcoin at High Frequency](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=3309565)
- [Intraday Return Predictability in Cryptocurrency Markets](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4080253)

Frozen family ID: `crypto_intraday_session_predictability_v1`

Candidate budget:

- `v36_5_intraday_session_source_replication`
- `v36_5_intraday_session_crypto_adaptation`
- exactly three preregistered parameter scales per candidate: `0.9`, `1.0`, `1.1`
- no third variant and no post-result hour mining

The source replication uses three fixed UTC sessions and a lagged, training-only estimate of session direction. The crypto adaptation may add one preregistered lagged liquidity/volatility gate. All features must be available before entry.

### Data-readiness only: funding carry

Frozen family ID: `crypto_funding_carry_v1`

Funding carry is independent from the already-failed funding-crowding reversal family, but it requires aligned same-exchange spot, perpetual, funding, dual-leg costs and capacity evidence. It remains `data_blocked`; it must not produce executable candidates in this campaign.

Reference sources:

- [Fundamentals of Perpetual Futures](https://arxiv.org/abs/2212.06888)
- [Perpetual Futures and Basis Risk](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=5036933)

## Causal and budget constraints

1. Use `1h` closed bars only for the executable family.
2. Session estimates are fitted inside each Development training window only.
3. A signal may use only prior closed bars; no same-bar close entry.
4. Broad UTC sessions are fixed before results. No search across 24 individual hours.
5. Include fees, slippage and funding assumptions.
6. Cheap prefilter runs before full Development replay.
7. The prefilter must reject insufficient samples, negative net expectancy, excessive turnover, or unstable session signs.
8. Development selection requires a stable parameter neighborhood, not an isolated maximum.
9. No Locked OOS or Formal input is read during prefilter or Development.
10. Formal may run once only if a candidate passes every frozen Development gate.
11. Only `formal_pass` may create a Release. Otherwise Release, approval, Demo ARM and order counts remain zero.

## TDD implementation order

1. Add failing registry tests for the two new family records and variant budgets.
2. Add failing causal tests proving that future rows cannot change an earlier signal.
3. Add failing budget tests proving two executable candidates and three trials each.
4. Add failing tests proving funding carry remains data-blocked and produces no trial.
5. Implement the smallest intraday-session adapter and cheap prefilter.
6. Run targeted tests.
7. Run the bounded Development campaign.
8. Archive zero survivors, or freeze exactly one selected candidate for one Formal run.
9. Run the full test suite, safety checks and git checks before commit and push.

## Required outputs

- source registry and canonical plans
- preregistration and immutable hashes
- cheap prefilter evidence and rejection reasons
- Development trial ledger and stability matrix
- failure attribution or selected-candidate handoff
- zero-survivor closeout when applicable
- Formal evidence only when all prerequisites are met

## Non-goals

- no threshold fishing
- no forced pass
- no reuse of Locked OOS for tuning
- no third rescue of an exhausted family
- no private exchange API
- no API key storage
- no Trade or Withdraw API
- no Demo or Live execution from research artifacts

## Execution result

- V36.5 intraday-session predictability completed six bounded Development trials. Both executable candidates failed after-cost expectancy and stability gates. Funding carry remained data-blocked because the required same-exchange spot, perpetual, funding, dual-leg cost and capacity evidence was unavailable.
- V36.6 BTC downside-spillover completed six bounded Development trials on the hash-verified fixed-core 20-asset snapshot. No candidate had a stable positive neighborhood. One source-replication center point was marginally positive, but both adjacent scales and most subperiods were negative, so it was rejected as brittle.
- Across both campaigns: `formalRunCount = 0`, `resultReadCount = 0`, `lockedOosReadCount = 0`, `releaseCount = 0`, `demoReleaseCount = 0`, and `orderCount = 0`.
- The bounded OHLCV-only mechanism-renewal budget is therefore closed with zero qualified candidates. Further blind indicator mutation is not authorized by this plan.
