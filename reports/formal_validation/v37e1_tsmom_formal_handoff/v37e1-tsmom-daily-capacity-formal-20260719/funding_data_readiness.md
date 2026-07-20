# V36 TSMOM Formal data readiness

- Status: `ready`
- Snapshot: `okx_official_v1_snapshot_12e78e3946f5a9eb19cf693936b8e9a9e510c05ab12d464f4e47662efd04b240`
- Formal start: `2025-01-01T00:00:00+00:00`
- Ready candidates: `1` / `1`
- Missing funding is never zero-filled and mixed-exchange funding is not used.

## Candidate audit

| Candidate | Timeframe | Status | OHLCV bars | Required bars | Funding window | Blockers |
| --- | --- | --- | ---: | ---: | --- | --- |
| v37e_tsmom_daily_capacity_successor | 1dutc | ready | 563 | 510 | complete | none |

### v37e_tsmom_daily_capacity_successor

- Selected trial: `v37e_metadata_only_capacity_successor_20260719`
- Strategy definition hash: `v36_replay_definition_b3b445432f083f2563fc0db5f85cf124133aec5e5e4e435db856d6be3e2acaa2`
- Exit policy hash: `v36_tsmom_exit_policy_7100479392c259f87c19e1a3b10066417d772a6506fa4fb8115412f57e4409cd`
- Funding `BTC-USDT-SWAP`: `2025-01-01T00:00:00+00:00` to `2026-07-17T16:00:00+00:00`, rows `1689`, full window `True`, provenance `True`.
- Funding `ETH-USDT-SWAP`: `2025-01-01T00:00:00+00:00` to `2026-07-17T16:00:00+00:00`, rows `1689`, full window `True`, provenance `True`.
- Funding `SOL-USDT-SWAP`: `2025-01-01T00:00:00+00:00` to `2026-07-17T16:00:00+00:00`, rows `1689`, full window `True`, provenance `True`.

## Safety counters

| Counter | Value |
| --- | ---: |
| Formal runs | 0 |
| Formal input reads | 0 |
| Result reads | 0 |
| Locked OOS access | 0 |
| Releases | 0 |
| Orders | 0 |
