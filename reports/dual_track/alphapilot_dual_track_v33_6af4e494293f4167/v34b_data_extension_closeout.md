# V34B Public Data Extension Closeout

V34B completed as a data-only extension of the frozen V34A OKX public-data snapshot.

## Result

- Extension snapshot: `okx_official_v1_v34b_snapshot_e80523c6c48c15abbbf69f082240c3efe034ef05ee6e596a33c3af83b228cc51`
- Manifest SHA-256: `d4b6050ffe6b617d9ad019117e0be363ce7731d144dcea51671358009a5c5e75`
- Program result hash: `v34b_data_extension_result_b1ae934e595c33936d7b3e0b534caa95985240dc8b75e4566ab63e4733545611`
- Warehouse: `D:\Codex-Workspace\回测数据\okx_official_v1`
- Observed at: `2026-07-18T18:43:56+00:00`

## Data Added

- 427 point-in-time OKX SWAP instrument/product metadata records.
- 861 funding-history records: 287 each for BTC, ETH, and SOL USDT swaps.
- Funding range: `2026-04-14T08:00:00+00:00` through `2026-07-18T16:00:00+00:00`.
- Seven append-only forward streams for BTC, ETH, and SOL: instrument state, current funding, open interest, mark price, index price, ticker spread, and order-book summary.
- Funding audit found zero duplicate timestamps and zero missing causal-availability timestamps.

## Integrity And Resume Checks

- All 11 V34A frozen artifacts were re-hashed; mismatch count was zero.
- Replaying the same collection completed from checkpoint in 545 ms.
- Replay did not add duplicate rows to the three program ledgers.
- The extension manifest hash remained unchanged.

## Safety Boundary

Candidate, Formal run, result read, Release, approval, Demo ARM, and order counts all remained zero. Trade API, Withdraw API, private-account reads, historical mutation, and locked-OOS reads were not used.

## Verification

- `pytest tests -q --import-mode=importlib`: 1096 passed, 157 subtests passed.
- `python -m compileall -q alphapilot`: passed.
- `python -m alphapilot.scripts.validate_config`: passed with live, trade, and withdraw disabled.
- Repository and targeted V34B safety scans: passed; V34B uses only OKX public/market endpoints.

## Limitations

- OKX funding history is recent-history only; this snapshot covers approximately three months.
- PIT product history starts now; no earlier instrument state was fabricated.
- This is a resumable one-shot collection primitive, not a permanent scheduler.
- No strategy research result, Demo order, or live-trading evidence was produced.
