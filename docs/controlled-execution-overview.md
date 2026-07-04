# Controlled Execution Overview

AlphaPilot controlled execution is a future design boundary, not a V13.2 implementation.

Rules:

- AI does not directly place orders.
- Strategies do not directly place orders.
- News systems do not directly place orders.
- Models do not directly place orders.
- Every trade idea must first become a Proposal.
- Every Proposal must pass the Risk Gate.
- Every future execution must have Preflight checks.
- Every opening action must have protective-order verification.
- Every action must write to the Audit Ledger.
- Every abnormal state must be stoppable through locks.

Future workflow:

```text
data -> research -> model analysis -> proposal -> risk gate -> human gate -> broker preflight -> controlled action -> reconciliation -> audit
```

V13.2 keeps `DEV_LOCK` and `TRADE_LOCK` enabled by default, so execution is rejected.
