# V13.5.7 External Alpha Overlay Report

This report references public GitHub projects as research inspiration only. It stores URL, license, summary, and citation metadata, and does not copy external code or long text.

## Decision

- External references reviewed: `True`
- Alpha101-style overlay computed: `True`
- Target R multiple unchanged: `True`
- Local paper watch approved: `True`
- Local paper watch pool: `4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24`
- New formal paper candidate approved: `False`
- Exchange Dry-run approved: `False`
- Live trading approved: `False`
- Reason: `alpha_overlay_local_paper_watch_only`

## External References

- `yydhYYDH/alpha101`: url=`https://github.com/yydhYYDH/alpha101`, license=`unknown_from_raw_license_fetch`, usage=`Concept reference only: cross-sectional ranks, time-series ranks, rolling correlation, decay-style factors, and explicit research-only boundaries.`
- `ryckli/CryptoAgentPro.beta`: url=`https://github.com/ryckli/CryptoAgentPro.beta`, license=`MIT`, usage=`Concept reference only: strict mode separation, risk gateway thinking, and public-data-first research workflows. No execution integration was adopted.`

## Overlay Summary

- Total overlay pools: `35`
- Local paper watch approved count: `2`

## Timeframe Coverage

- `1h`: pairs=`28`, panelRows=`797589`, range=`2023-01-02T00:00:00+00:00` to `2026-07-05T15:00:00+00:00`, overlayPools=`15`
- `4h`: pairs=`28`, panelRows=`198635`, range=`2023-01-05T00:00:00+00:00` to `2026-07-04T12:00:00+00:00`, overlayPools=`20`

## Top Alpha Overlay Pools

- `4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24`: trades=`145`, winRate=`58.6207`, RR=`1.8207`, PF=`2.5793`, maxDD=`38.3157`, recentPF=`3.2286`, 2Rclose=`0.956639`, watch=`True`, fail=`none`
- `4h:alpha_short_exhaustion_pressure_watch:sl0.04:h12`: trades=`145`, winRate=`48.9655`, RR=`1.6553`, PF=`1.5882`, maxDD=`33.2694`, recentPF=`1.4209`, 2Rclose=`0.891315`, watch=`True`, fail=`none`
- `1h:alpha_long_rebound_pressure_watch:sl0.02:h24`: trades=`6`, winRate=`66.6667`, RR=`1.5605`, PF=`3.121`, maxDD=`4.3516`, recentPF=`1.7273`, 2Rclose=`0.903447`, watch=`False`, fail=`trade_count_below_80, pair_coverage_below_12, month_coverage_below_8, recent_holdout_sample_below_16`
- `1h:alpha_long_rebound_pressure_watch:sl0.025:h30`: trades=`6`, winRate=`66.6667`, RR=`1.1887`, PF=`2.3775`, maxDD=`5.3271`, recentPF=`1.7778`, 2Rclose=`0.668644`, watch=`False`, fail=`trade_count_below_80, pair_coverage_below_12, month_coverage_below_8, recent_holdout_sample_below_16, observed_rr_not_close_to_cost_adjusted_2r`
- `4h:alpha_short_exhaustion_pressure_watch:sl0.08:h30`: trades=`145`, winRate=`57.931`, RR=`1.7059`, PF=`2.349`, maxDD=`60.0778`, recentPF=`3.4844`, 2Rclose=`0.885341`, watch=`False`, fail=`max_drawdown_above_45`
- `4h:alpha_sideways_rejection_control:sl0.05:h18`: trades=`49`, winRate=`63.2653`, RR=`1.3048`, PF=`2.2471`, maxDD=`28.9028`, recentPF=`4.5688`, 2Rclose=`0.692343`, watch=`False`, fail=`trade_count_below_80, recent_holdout_sample_below_16, observed_rr_not_close_to_cost_adjusted_2r`
- `1h:alpha_long_rebound_pressure_watch:sl0.03:h36`: trades=`6`, winRate=`66.6667`, RR=`1.0999`, PF=`2.1997`, maxDD=`6.2976`, recentPF=`1.8125`, 2Rclose=`0.606841`, watch=`False`, fail=`trade_count_below_80, pair_coverage_below_12, month_coverage_below_8, recent_holdout_sample_below_16, observed_rr_not_close_to_cost_adjusted_2r`
- `4h:alpha_sideways_rejection_control:sl0.06:h24`: trades=`49`, winRate=`57.1429`, RR=`1.5331`, PF=`2.0441`, maxDD=`31.9329`, recentPF=`1.2361`, 2Rclose=`0.805527`, watch=`False`, fail=`trade_count_below_80, recent_holdout_sample_below_16`
- `4h:alpha_short_exhaustion_pressure_watch:sl0.05:h18`: trades=`145`, winRate=`53.1034`, RR=`1.7207`, PF=`1.9484`, maxDD=`45.0587`, recentPF=`2.6318`, 2Rclose=`0.913024`, watch=`False`, fail=`max_drawdown_above_45`
- `4h:alpha_sideways_rejection_control:sl0.08:h30`: trades=`49`, winRate=`55.102`, RR=`1.5789`, PF=`1.9378`, maxDD=`26.8845`, recentPF=`0.8941`, 2Rclose=`0.819429`, watch=`False`, fail=`trade_count_below_80, recent_holdout_sample_below_16`
- `4h:alpha_sideways_rejection_control:sl0.04:h12`: trades=`49`, winRate=`57.1429`, RR=`1.2803`, PF=`1.707`, maxDD=`28.8149`, recentPF=`5.7075`, 2Rclose=`0.689392`, watch=`False`, fail=`trade_count_below_80, recent_holdout_sample_below_16, observed_rr_not_close_to_cost_adjusted_2r`
- `1h:alpha_sideways_rejection_control:sl0.02:h24`: trades=`138`, winRate=`47.1014`, RR=`1.5122`, PF=`1.3464`, maxDD=`30.878`, recentPF=`0.753`, 2Rclose=`0.875484`, watch=`False`, fail=`profit_factor_below_1_5, recent_profit_factor_below_0_9`

## Recommendations

- Keep the existing 2R barrier unchanged and start local paper watch for the best Alpha101-style overlay only.
- Do not promote this to exchange Dry-run until a fresh forward sample confirms the same behavior.
- Best overlay 4h:alpha_short_exhaustion_pressure_watch:sl0.06:h24: trades=145, winRate=58.6207, PF=2.5793, RR=1.8207, maxDD=38.3157.

## Safety Boundary

- Public local data only.
- No Trade API.
- No Withdraw API.
- No API key storage.
- No real account or position reads.
- No order creation.
- No automatic trading.
