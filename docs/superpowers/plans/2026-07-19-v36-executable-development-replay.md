# V36 Executable Development Replay Plan

## Goal

Turn the existing V36 preregistration, evidence projection, and routing skeleton
into a real Development-only replay over the frozen OKX public snapshot.

## Boundaries

- Read only the preregistered Development interval.
- Verify the snapshot identity and every consumed Parquet hash.
- Keep `lockedOosReadCount = 0`.
- Do not run Formal, create a Release, approve, ARM, access a private account,
  or place an order.
- Preserve the existing inline-evidence path for contract tests and imported
  evidence.

## Implementation

1. Add a snapshot loader that normalizes causal OHLCV columns and rejects
   snapshot, hash, coverage, or confirmation mismatches.
2. Add deterministic replay implementations for the three executable V35
   families:
   - time-series momentum / Turtle trend;
   - BTC/ETH relative value;
   - conditional market-residual mean reversion.
3. Generate all preregistered trial evidence from the frozen comparison panel.
4. Persist a replay audit alongside the existing V36 artifacts.
5. Run unit tests first, then one bounded real-data campaign.

## Acceptance

- All 18 eligible preregistered trials receive real Development evidence or a
  fail-closed data audit reason.
- Evidence is deterministic for the same snapshot, panel, registry, and trial
  identity.
- The campaign reports zero Formal reads/runs, zero Locked OOS reads, zero
  Releases, zero approvals, zero ARM, and zero orders.
- Existing V35/V36 contract tests remain green.
