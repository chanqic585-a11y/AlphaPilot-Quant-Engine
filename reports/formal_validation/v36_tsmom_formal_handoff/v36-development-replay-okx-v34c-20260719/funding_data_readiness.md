# V36 TSMOM Formal data readiness

- Status: `blocked`
- Snapshot: `okx_official_v1_snapshot_12e78e3946f5a9eb19cf693936b8e9a9e510c05ab12d464f4e47662efd04b240`
- Formal start: `2025-01-01T00:00:00+00:00`
- Ready candidates: `0` / `2`
- Missing funding is never zero-filled and mixed-exchange funding is not used.

## Candidate audit

| Candidate | Timeframe | Status | OHLCV bars | Required bars | Funding window | Blockers |
| --- | --- | --- | ---: | ---: | --- | --- |
| v35_tsmom_crypto_adaptation | 4h | blocked | 3382 | 900 | incomplete | funding_window_incomplete |

### v35_tsmom_crypto_adaptation

- Selected trial: `v36_trial_43b2c0f5804b1f0596bc6d5691d79013699a5e1b3db0a07e7a3332ac3f6f0599`
- Strategy definition hash: `v36_replay_definition_500e95aa9039039462514ee499bbb4548246b6b479b656e13a407967885d312e`
- Exit policy hash: `v36_tsmom_exit_policy_d608e75474fae769bb44d038d46e254f1cdee1b3de8bd259337adf4e3fc3f347`
- Funding `BTC-USDT-SWAP`: `2026-04-07T08:00:00+00:00` to `2026-07-14T08:00:00+00:00`, rows `295`, full window `False`, provenance `True`.
- Funding `ETH-USDT-SWAP`: `2026-04-07T08:00:00+00:00` to `2026-07-14T08:00:00+00:00`, rows `295`, full window `False`, provenance `True`.
- Funding `SOL-USDT-SWAP`: `2026-04-07T08:00:00+00:00` to `2026-07-14T08:00:00+00:00`, rows `295`, full window `False`, provenance `True`.
| v35_tsmom_source_replication | 1dutc | blocked | 563 | 840 | incomplete | funding_window_incomplete, purged_walk_forward_capacity_insufficient |

### v35_tsmom_source_replication

- Selected trial: `v36_trial_ec2562d73795444e90789e7f77a3e129030b7d92c0f3614cf3f33375fdaf41c0`
- Strategy definition hash: `v36_replay_definition_de5d64cd919032532992c30d51624e968c2d0e32e097c167040c8f494ae45727`
- Exit policy hash: `v36_tsmom_exit_policy_311993d65953bdc4cd6f134cefaaff8278c1144b0391e77e129253fb7c719781`
- Funding `BTC-USDT-SWAP`: `2026-04-07T08:00:00+00:00` to `2026-07-14T08:00:00+00:00`, rows `295`, full window `False`, provenance `True`.
- Funding `ETH-USDT-SWAP`: `2026-04-07T08:00:00+00:00` to `2026-07-14T08:00:00+00:00`, rows `295`, full window `False`, provenance `True`.
- Funding `SOL-USDT-SWAP`: `2026-04-07T08:00:00+00:00` to `2026-07-14T08:00:00+00:00`, rows `295`, full window `False`, provenance `True`.

## Safety counters

| Counter | Value |
| --- | ---: |
| Formal runs | 0 |
| Formal input reads | 0 |
| Result reads | 0 |
| Locked OOS access | 0 |
| Releases | 0 |
| Orders | 0 |
