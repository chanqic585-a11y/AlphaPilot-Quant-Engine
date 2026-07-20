"""Data-only readiness gates for the preregistered funding-carry family."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Any, Mapping

import pandas as pd

from alphapilot.evolution.registry.hashing import stable_hash

from .funding_carry_data import FundingCarryDataPolicy, MILLISECONDS_PER_DAY


@dataclass(frozen=True)
class DualLegCostStressPolicy:
    """Preregistered stress values; these are not account fee observations."""

    schema_version: str
    round_trip_cost_bps: tuple[float, ...]
    includes_spot_fees: bool
    includes_perpetual_fees: bool
    includes_dual_leg_slippage: bool
    account_fee_claim: bool

    @classmethod
    def default(cls) -> "DualLegCostStressPolicy":
        return cls(
            schema_version="v37a_dual_leg_cost_stress_policy_v1",
            round_trip_cost_bps=(20.0, 40.0, 60.0),
            includes_spot_fees=True,
            includes_perpetual_fees=True,
            includes_dual_leg_slippage=True,
            account_fee_claim=False,
        )

    @property
    def policy_hash(self) -> str:
        return stable_hash(asdict(self), prefix="v37a_dual_leg_cost_stress")


def _asset_readiness(
    asset: str,
    panel: pd.DataFrame | None,
    policy: FundingCarryDataPolicy,
) -> tuple[dict[str, Any], list[str]]:
    blockers: list[str] = []
    if panel is None or panel.empty:
        blockers.append(f"missing_aligned_panel:{asset}")
        return {
            "asset": asset,
            "rowCount": 0,
            "coverageDays": 0.0,
            "staleFraction": None,
            "dualLegQuoteTurnoverAvailable": False,
            "status": "blocked",
        }, blockers

    required = {
        "decisionTimestampMs",
        "fundingRate",
        "dualLegQuoteTurnoverProxy",
        "stale",
    }
    missing = sorted(required - set(panel.columns))
    if missing:
        blockers.append(f"panel_columns_missing:{asset}:{','.join(missing)}")
        return {
            "asset": asset,
            "rowCount": int(len(panel)),
            "coverageDays": 0.0,
            "staleFraction": None,
            "dualLegQuoteTurnoverAvailable": False,
            "status": "blocked",
        }, blockers

    timestamps = pd.to_numeric(panel["decisionTimestampMs"], errors="coerce")
    funding = pd.to_numeric(panel["fundingRate"], errors="coerce")
    turnover = pd.to_numeric(panel["dualLegQuoteTurnoverProxy"], errors="coerce")
    stale = panel["stale"].astype(bool)
    coverage_days = (
        float(timestamps.max() - timestamps.min()) / MILLISECONDS_PER_DAY
        if len(panel) > 1 and timestamps.notna().all()
        else 0.0
    )
    stale_fraction = float(stale.mean())
    turnover_available = bool(
        turnover.notna().all()
        and all(math.isfinite(float(value)) for value in turnover)
        and (turnover >= 0).all()
    )
    zero_turnover_row_count = int((turnover == 0).sum())
    if len(panel) < policy.minimum_aligned_rows:
        blockers.append(
            f"insufficient_aligned_rows:{asset}:{len(panel)}/{policy.minimum_aligned_rows}"
        )
    if coverage_days < policy.minimum_coverage_days:
        blockers.append(
            f"insufficient_coverage_days:{asset}:{coverage_days:.3f}/{policy.minimum_coverage_days}"
        )
    if funding.isna().any() or not all(math.isfinite(float(value)) for value in funding):
        blockers.append(f"invalid_actual_funding:{asset}")
    if not turnover_available:
        blockers.append(f"missing_dual_leg_quote_turnover:{asset}")
    if stale_fraction > policy.maximum_stale_fraction:
        blockers.append(
            f"stale_alignment_fraction:{asset}:{stale_fraction:.6f}"
        )
    return {
        "asset": asset,
        "rowCount": int(len(panel)),
        "coverageDays": round(coverage_days, 6),
        "staleFraction": round(stale_fraction, 9),
        "dualLegQuoteTurnoverAvailable": turnover_available,
        "zeroTurnoverRowCount": zero_turnover_row_count,
        "medianDualLegQuoteTurnover": (
            float(turnover.median()) if turnover.notna().any() else None
        ),
        "status": "ready" if not blockers else "blocked",
    }, blockers


def evaluate_funding_carry_readiness(
    *,
    policy: FundingCarryDataPolicy,
    cost_policy: DualLegCostStressPolicy,
    panels: Mapping[str, pd.DataFrame],
    forward_order_book_evidence: Mapping[str, bool],
    additional_historical_blockers: tuple[str, ...] = (),
) -> dict[str, Any]:
    per_asset: list[dict[str, Any]] = []
    historical_blockers: list[str] = []
    for asset in policy.assets:
        row, blockers = _asset_readiness(asset, panels.get(asset), policy)
        per_asset.append(row)
        historical_blockers.extend(blockers)
    historical_blockers.extend(additional_historical_blockers)

    formal_blockers = list(historical_blockers)
    forward_blockers = [
        f"missing_forward_order_book:{asset}"
        for asset in policy.assets
        if not bool(forward_order_book_evidence.get(asset))
    ]
    result = {
        "schemaVersion": "v37a_funding_carry_data_readiness_v1",
        "familyId": "crypto_funding_carry_v1",
        "dataPolicyHash": policy.policy_hash,
        "costPolicyHash": cost_policy.policy_hash,
        "historicalResearchReady": not historical_blockers,
        "formalResearchDataReady": not formal_blockers,
        "forwardExecutionEvidenceReady": not forward_blockers,
        "historicalBlockers": historical_blockers,
        "formalBlockers": formal_blockers,
        "forwardBlockers": forward_blockers,
        "perAsset": per_asset,
        "costEvidence": {
            "classification": "preregistered_stress_assumption",
            "roundTripCostBps": list(cost_policy.round_trip_cost_bps),
            "includesSpotFees": cost_policy.includes_spot_fees,
            "includesPerpetualFees": cost_policy.includes_perpetual_fees,
            "includesDualLegSlippage": cost_policy.includes_dual_leg_slippage,
            "notAccountFeeClaim": not cost_policy.account_fee_claim,
        },
        "capacityEvidence": {
            "historicalProxy": "minimum_spot_perpetual_quote_turnover",
            "historicalOrderBookClaim": False,
            "forwardOrderBookByAsset": {
                asset: bool(forward_order_book_evidence.get(asset))
                for asset in policy.assets
            },
        },
        "zeroFillUsed": False,
        "crossExchangeSubstitution": False,
        "sideEffects": {
            "candidateCount": 0,
            "formalRunCount": 0,
            "resultReadCount": 0,
            "releaseCount": 0,
            "demoArmCount": 0,
            "orderCount": 0,
        },
    }
    result["readinessHash"] = stable_hash(result, prefix="v37a_funding_readiness")
    return result
