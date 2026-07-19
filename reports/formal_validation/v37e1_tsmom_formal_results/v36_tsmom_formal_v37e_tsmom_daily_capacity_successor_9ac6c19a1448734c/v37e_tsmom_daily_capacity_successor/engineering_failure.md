# V37E.1 Formal Artifact Publication Failure

- Status: remediated by a new frozen successor; this campaign is terminal and is not retried.
- Failure stage: atomic Formal artifact publication.
- Root cause: the staging path retained the long campaign directory and exceeded the Windows path limit.
- Attempt count: 1.
- Published result artifacts: none.
- Result artifacts inspected: none.
- Release / Demo ARM / orders: 0 / false / 0.
- Strategy conclusion: none. This is an engineering publication failure, not a strategy-performance result.

The repair moves the atomic staging directory to the shorter Formal output root and uses a bounded temporary name. The original freeze tag and failed ledger remain immutable for audit.
