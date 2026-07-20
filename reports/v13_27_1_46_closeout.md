# AlphaPilot V13.27.1.46 Demo Replay And Portfolio Rescue Closeout

## Conclusion

The ten active 1h/1d OKX Demo strategy identities were replayed offline from their frozen parameters against the same local public-data engines used by the source reports. All ten reproduced the original trade count and profit factor exactly. This confirms implementation reproducibility; it is not fresh out-of-sample evidence.

All ten source candidates passed their historical research gates. Their later Console admission was nevertheless an `experimental_override`: `user_manual` bypassed `local_forward_samples` for every contract. The replay did not modify those contracts and created no new Release.

## Exact Replay

| Candidate | TF | Family | Trades | PF | Average net R | Total R |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| v13_7_20_lf_research_candidate_089 | 1d | breakout | 319 | 1.5035 | 0.251605 | 80.2621 |
| v13_7_20_lf_research_candidate_090 | 1d | squeeze_breakout | 207 | 1.3856 | 0.196571 | 40.6901 |
| v13_7_20_lf_research_candidate_108 | 1d | squeeze_breakout | 220 | 1.3152 | 0.165760 | 36.4672 |
| v13_7_20_lf_research_candidate_115 | 1d | mean_reversion | 38 | 2.2125 | 0.554302 | 21.0635 |
| v13_7_20_lf_research_candidate_117 | 1d | mean_reversion | 36 | 2.4289 | 0.605504 | 21.7981 |
| v13_7_40_1h_short_rejection_2021_asset_filter_top10 | 1h | short_rejection | 131 | 1.6850 | 0.262404 | 34.3749 |
| v13_7_40_1h_short_rejection_2077_asset_filter_top8 | 1h | short_rejection | 175 | 1.5545 | 0.299841 | 52.4722 |
| v13_7_40_1h_short_rejection_2148_asset_filter_top10 | 1h | short_rejection | 219 | 1.4348 | 0.227261 | 49.7702 |
| v13_7_40_1h_short_rejection_2149_asset_filter_top10 | 1h | short_rejection | 219 | 1.5170 | 0.281784 | 61.7107 |
| v13_7_40_1h_short_rejection_2150_asset_filter_top10 | 1h | short_rejection | 219 | 1.5112 | 0.290469 | 63.6127 |

## Bounded Portfolio Rescue

Sleeves were frozen before reading the new replay results, using only pre-existing source rank and mechanism distinctness:

- `v13_7_40_1h_short_rejection_2149_asset_filter_top10`
- `v13_7_20_lf_research_candidate_117`
- `v13_7_20_lf_research_candidate_090`

Six fixed development policies were evaluated. The best policy was `pair_14d_cooldown`:

- Trades: 382
- Profit factor: 1.6046
- Expectancy: 0.304485R
- Total: 116.3131R
- Maximum drawdown: 12.9224R
- Positive months: 44 / 73 (60.27%)
- Additional 0.10R cost stress: PF 1.3687, expectancy 0.204485R

All three sleeves remained positive after the portfolio filter. The frozen development checks therefore recommend a future fresh preregistered OOS campaign. They do not create a Formal candidate, immutable Demo Release, or live approval.

## Safety And Evidence Boundary

- Public local OHLCV only; no download and no exchange private endpoint.
- No API key, account, balance, position, order, Withdraw, Demo order, or live order access.
- Existing Console contracts and databases were not modified.
- Formal candidate count: 0.
- Locked OOS read count: 0.
- Release count: 0.
- Status: `development_only` / `research_replay_only`.

## Recommended Next Step

Create a new immutable preregistration for only the three-sleeve `pair_14d_cooldown` portfolio, define a genuinely unread OOS interval or forward collection window, and evaluate it once. Do not reuse this development result as OOS and do not promote the current Demo contracts on the strength of this replay alone.

## Verification

- Targeted replay and portfolio-rescue tests: 15 passed.
- `python -m compileall -q alphapilot`: passed.
- `python -m alphapilot.scripts.validate_config`: passed; live trading, Trade API, and Withdraw API remain disabled.
- `scripts/check_safety.ps1`: passed; matches are existing safety terms, fixtures, and negative boundary descriptions.
- `git diff --check`: passed before packaging.
