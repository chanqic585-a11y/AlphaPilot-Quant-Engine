"""In-memory bridge from immutable legacy fixed-target candidates."""

from __future__ import annotations

from typing import Any

import pandas as pd

from .engine import replay_exit_policy
from .exit_legs import ExitCosts, ExitExecutionResult
from .models import ExitPolicy, ExitPolicyMode


def legacy_fixed_r_policy(candidate: Any) -> ExitPolicy:
    return ExitPolicy(
        mode=ExitPolicyMode.FIXED_R,
        maximumHoldBars=int(candidate.maximumHoldBars),
        parameters={"targetR": float(candidate.targetR)},
    )


def replay_legacy_candidate_exit(
    *,
    frame: pd.DataFrame,
    signal_position: int,
    candidate: Any,
    atr_value: float,
    fee_bps_per_side: float,
    slippage_bps_per_side: float,
    spread_bps_per_side: float,
    funding_rate: pd.Series | None = None,
) -> ExitExecutionResult:
    return replay_exit_policy(
        frame=frame,
        signalPosition=signal_position,
        direction=str(candidate.direction),
        riskDistance=float(candidate.stopAtr) * float(atr_value),
        policy=legacy_fixed_r_policy(candidate),
        costs=ExitCosts(
            feeBpsPerSide=float(fee_bps_per_side),
            slippageBpsPerSide=float(slippage_bps_per_side),
            spreadBpsPerSide=float(spread_bps_per_side),
        ),
        fundingRate=funding_rate,
    )

