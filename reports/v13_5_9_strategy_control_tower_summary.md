# V13.5.9 Strategy Control Tower Report

This report coordinates existing research candidates into a local-paper-only control tower.
It does not create exchange orders, use API keys, enter exchange Dry-run, or auto trade.

## Decision

- Control tower computed: `True`
- Active local paper strategies: `1`
- Primary active strategy: `v13_5_7_alpha_overlay_fixed_watch`
- Continue local paper monitoring: `True`
- Paper trial approved: `False`
- Exchange Dry-run review ready: `False`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `continue_local_paper_watch_only`

## Strategy States

- `v13_5_7_alpha_overlay_fixed_watch`
  - stage: `local_paper_watch`
  - routeAction: `continue_local_paper_watch`
  - pool: `4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24`
  - winRate: `58.6207`
  - rewardRisk: `1.8207`
  - profitFactor: `2.5793`
  - maxDrawdown: `38.3157`
  - warnings: `approved_signal_to_fill_lag_above_5_days, closed_fill_not_fresh, paper_closed_fill_not_fresh, recent_20_reward_risk_below_1_5, recent_20_win_rate_below_55, some_approved_signals_skipped_by_concurrency`
  - blockers: `none`
- `v13_5_8_adaptive_ml_observer`
  - stage: `research_candidate`
  - routeAction: `observe_only`
  - pool: `1h:adaptive_ml_all_high_reward:sl0.025:h30`
  - winRate: `36.7059`
  - rewardRisk: `1.6143`
  - profitFactor: `0.9362`
  - maxDrawdown: `98.3195`
  - warnings: `adaptive_ml_no_local_paper_approval`
  - blockers: `none`

## Local Paper Router Intents

- `router-v13-5-9-0001`: strategy=`v13_5_7_alpha_overlay_fixed_watch`, action=`continue_local_paper_watch`, isOrder=`False`
- `router-v13-5-9-0002`: strategy=`v13_5_8_adaptive_ml_observer`, action=`observe_only`, isOrder=`False`

## Ledger Summary

- Trades: `41`
- Win rate: `60.9756`
- Reward/risk: `1.6922`
- Profit factor: `2.644`
- Total return: `14.9788`
- Max drawdown: `3.242758`

## External References

- `yydhYYDH/alpha101`: url=`https://github.com/yydhYYDH/alpha101`, license=`unknown_from_raw_license_fetch`, localReference=`docs/future-factor-research-reference-alpha101.md`
- `ryckli/CryptoAgentPro.beta`: url=`https://github.com/ryckli/CryptoAgentPro.beta`, license=`MIT`, localReference=`docs/future-live-trading-reference-cryptoagentpro-beta.md`

## Recommendations

- Keep V13.5.7 as the only active local paper watch strategy.
- Keep V13.5.8 adaptive ML as observer-only until it passes independent validation.
- Do not move to exchange Dry-run because monitoring still has freshness and decay warnings.
- Use future paper/manual outcomes as strategy evolution samples; do not fabricate actual trade outcomes.

## Safety Boundary

- Local paper only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account reads.
- No real position reads.
- No real orders.
- No emergency close implementation.
- No testnet execution implementation.
- No automatic trading.
