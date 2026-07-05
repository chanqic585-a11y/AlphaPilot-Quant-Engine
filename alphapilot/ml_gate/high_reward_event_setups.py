"""High reward/risk research event definitions for V13.5.6.

These setups are static research hypotheses. They are designed to look for
structures that can naturally support a 2R target, not to optimize in-sample
win rate. The module reads feature-panel columns only and never requests
exchange data, uses API keys, creates orders, or auto trades.
"""

from __future__ import annotations

import pandas as pd


HIGH_REWARD_SETUP_NAMES = [
    "hr_long_failed_breakdown_reclaim",
    "hr_short_failed_breakout_rejection",
    "hr_long_capitulation_reversal",
    "hr_short_blowoff_reversal",
    "hr_long_trend_pullback_acceleration",
    "hr_short_trend_pullback_acceleration",
]


def add_high_reward_event_setups(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    funding_available = out["funding_rate"].notna()
    funding_low = out["funding_z_60"] <= -0.5
    funding_high = out["funding_z_60"] >= 0.5
    basis_low = out["mark_basis_pct"] <= -0.0005
    basis_high = out["mark_basis_pct"] >= 0.0005
    volume_active = out["volume_ratio"] >= 1.1
    volume_expansion = out["volume_ratio"] >= 1.35
    lower_reclaim = out["close_back_above_prior_low_48"].fillna(False)
    upper_rejection = out["close_back_below_prior_high_48"].fillna(False)
    lower_wick_active = (out["lower_wick_pct"] >= out["atr_pct"] * 0.25) | (out["close_location"] >= 0.62)
    upper_wick_active = (out["upper_wick_pct"] >= out["atr_pct"] * 0.25) | (out["close_location"] <= 0.38)
    meaningful_down_sweep = out["breakdown_below_48_pct"] >= out["atr_pct"].fillna(0) * 0.15
    meaningful_up_sweep = out["breakout_above_48_pct"] >= out["atr_pct"].fillna(0) * 0.15
    not_btc_crashing = out["btc_return_3"].fillna(0) > -0.045
    not_btc_meltup = out["btc_return_3"].fillna(0) < 0.045

    out["hr_long_failed_breakdown_reclaim"] = (
        meaningful_down_sweep
        & lower_reclaim
        & lower_wick_active
        & (out["rsi14"] <= 44)
        & volume_active
        & not_btc_crashing
        & ((funding_available & funding_low) | basis_low | (out["bollinger_z"] <= -0.9))
    )
    out["hr_short_failed_breakout_rejection"] = (
        meaningful_up_sweep
        & upper_rejection
        & upper_wick_active
        & (out["rsi14"] >= 56)
        & volume_active
        & not_btc_meltup
        & ((funding_available & funding_high) | basis_high | (out["bollinger_z"] >= 0.9))
    )
    out["hr_long_capitulation_reversal"] = (
        (out["return_12"] <= -0.055)
        & (out["bollinger_z"] <= -1.6)
        & (out["rsi14"] <= 38)
        & lower_wick_active
        & volume_expansion
        & not_btc_crashing
        & ((funding_available & funding_low) | basis_low | lower_reclaim)
    )
    out["hr_short_blowoff_reversal"] = (
        (out["return_12"] >= 0.055)
        & (out["bollinger_z"] >= 1.6)
        & (out["rsi14"] >= 62)
        & upper_wick_active
        & volume_expansion
        & not_btc_meltup
        & ((funding_available & funding_high) | basis_high | upper_rejection)
    )
    out["hr_long_trend_pullback_acceleration"] = (
        (out["ema200_gap"] > 0.015)
        & (out["ema20_slope_6"] > 0)
        & (out["return_12"] > 0.01)
        & (out["return_3"].between(-0.035, 0.005))
        & (out["rsi14"].between(42, 60))
        & (out["close"] >= out["ema50"])
        & (out["close"] <= out["ema20"] * 1.02)
        & (out["volume_ratio"].between(0.75, 2.3))
        & (out["btc_regime"] != "bear")
        & not_btc_crashing
    )
    out["hr_short_trend_pullback_acceleration"] = (
        (out["ema200_gap"] < -0.015)
        & (out["ema20_slope_6"] < 0)
        & (out["return_12"] < -0.01)
        & (out["return_3"].between(-0.005, 0.035))
        & (out["rsi14"].between(40, 58))
        & (out["close"] <= out["ema50"])
        & (out["close"] >= out["ema20"] * 0.98)
        & (out["volume_ratio"].between(0.75, 2.3))
        & (out["btc_regime"] != "bull")
        & not_btc_meltup
    )
    return out
