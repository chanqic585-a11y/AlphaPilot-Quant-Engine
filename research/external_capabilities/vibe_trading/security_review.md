# Vibe-Trading Selective Security Review

## Adopted with stricter AlphaPilot boundaries

- Strategy acquisition is an index/projection over the existing Program and
  Campaign Ledger, never a second authority.
- Generated candidate code is parsed as a complete AST. Dangerous imports,
  calls, file access, network access, environment access, and hidden unreachable
  helpers fail closed before execution.
- Accepted generated code runs in a separate Python process with a minimal
  environment, deterministic hash seed, bounded input/output, and a hard wall
  clock timeout.
- Factor results remain research-only. They cannot create Formal Pass, Release,
  Demo ARM, orders, or Live permission.

## Explicit limitations

The local generated-code runner is a research execution guard, not an OS-grade
security boundary. On Windows its declared memory budget is audit metadata;
wall-clock, process count through the AST policy, input, and output limits are
enforced. Untrusted third-party code must not be treated as safe merely because
it passes this runner.

## Rejected

- Vibe broker and live connectors.
- Generic strategy gates or cross-exchange Formal fallback.
- In-place mutation of an approved candidate or immutable Release.
- Unbounded autonomous strategy generation.
- Runtime dependency on the Vibe-Trading repository or package.
