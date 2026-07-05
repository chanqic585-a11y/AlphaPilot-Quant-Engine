# Failed Strategy Archive Policy

AlphaPilot keeps failed research strategies as evidence.

Failure archives prevent repeated work and make future strategy research more disciplined. A failed strategy is not deleted unless it is technically broken or unsafe to keep.

## Archive Status

V13.4.30 uses:

```text
failed_research_current_sample
```

Meaning:

- The strategy failed the current research sample.
- The strategy is rejected for Dry-run.
- The strategy is rejected for live trading.
- The strategy may remain useful as a benchmark or negative reference.

## Archive Mode

```text
research_reference
```

This keeps the evidence, report paths, negative rules, and revival conditions.

## Revival Conditions

A failed short strategy can only be reconsidered if the thesis materially changes. For V13.4.29, revival requires:

- A new short thesis with stronger regime filter.
- Public funding/open-interest data support.
- Much lower trade frequency.
- Per-trade regime attribution.

Small parameter edits are not enough.

## Safety Boundary

Archiving a failed strategy does not approve Dry-run or live trading.
