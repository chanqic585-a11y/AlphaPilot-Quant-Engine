# V36 TSMOM Formal data readiness

- Status: `ready`
- Snapshot: `okx_official_v1_snapshot_12e78e3946f5a9eb19cf693936b8e9a9e510c05ab12d464f4e47662efd04b240`
- Formal start: `2025-01-01T00:00:00+00:00`
- Ready candidates: `1` / `1`
- Missing funding is never zero-filled and mixed-exchange funding is not used.

## Candidate audit

| Candidate | Timeframe | Status | OHLCV bars | Required bars | Funding window | Blockers |
| --- | --- | --- | ---: | ---: | --- | --- |
| v35_tsmom_crypto_adaptation | 4h | ready | 3382 | 900 | complete | none |

### v35_tsmom_crypto_adaptation

- Selected trial: `v36_trial_43b2c0f5804b1f0596bc6d5691d79013699a5e1b3db0a07e7a3332ac3f6f0599`
- Strategy definition hash: `v36_replay_definition_500e95aa9039039462514ee499bbb4548246b6b479b656e13a407967885d312e`
- Exit policy hash: `v36_tsmom_exit_policy_d608e75474fae769bb44d038d46e254f1cdee1b3de8bd259337adf4e3fc3f347`
- Funding `BTC-USDT-SWAP`: `2025-01-01T00:00:00+00:00` to `2026-07-18T08:00:00+00:00`, rows `1691`, full window `True`, provenance `True`.
- Funding `ETH-USDT-SWAP`: `2025-01-01T00:00:00+00:00` to `2026-07-18T08:00:00+00:00`, rows `1691`, full window `True`, provenance `True`.
- Funding `SOL-USDT-SWAP`: `2025-01-01T00:00:00+00:00` to `2026-07-18T08:00:00+00:00`, rows `1691`, full window `True`, provenance `True`.

## Safety counters

| Counter | Value |
| --- | ---: |
| Formal runs | 0 |
| Formal input reads | 0 |
| Result reads | 0 |
| Locked OOS access | 0 |
| Releases | 0 |
| Orders | 0 |
