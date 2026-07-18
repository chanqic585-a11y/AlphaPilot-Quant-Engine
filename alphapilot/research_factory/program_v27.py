"""V27 bounded directional-event candidate research contracts.

This module creates candidate identities only after point-in-time data and
capacity semantics have passed their preregistered readiness gate. It does not
read economic outcomes, formal results, or Locked OOS data.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.formal_validation.candidate_ranking_contract import (
    build_candidate_ranking_contract,
)
from alphapilot.formal_validation.candidate_ranking_evidence import (
    materialize_candidate_ranking_evidence,
)

from .automatic_prefilter import build_prefilter_route, evaluate_prefilter_events
from .capacity_profile_certification import certify_real_signal_capacity
from .generated_candidate_adapter import GeneratedDirectionalEventAdapter
from .generated_freqtrade_strategy import translated_load_signals
from .program_v21 import _benchmark_events


_REQUIRED_FIELDS = ("open", "high", "low", "close")
_FAMILY_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "familyId": "range_expansion_close_followthrough",
        "displayNameZh": "区间扩张收盘延续",
        "timeframe": "4h",
        "mechanism": "异常区间扩张后，收盘仍靠近冲击方向一侧，测试次根延续。",
        "falsification": "扣除成本后延续不稳定，或表现集中于单一币种和月份。",
        "primary": "true_range / prior_atr14",
        "confirmation": "directional_close_location_within_event_bar",
    },
    {
        "familyId": "liquidity_gap_reentry",
        "displayNameZh": "流动性缺口再进入",
        "timeframe": "1h",
        "mechanism": "开盘流动性缺口被同一根闭合 K 线重新吸收，测试回归延续。",
        "falsification": "缺口再进入在压力成本下没有正期望，或只来自不可交易尾部币种。",
        "primary": "absolute_open_gap / prior_atr14",
        "confirmation": "directional_gap_reentry_fraction",
    },
    {
        "familyId": "cross_section_dispersion_leader_followthrough",
        "displayNameZh": "横截面离散领涨延续",
        "timeframe": "4h",
        "mechanism": "同周期横截面收益显著偏离时，测试领涨或领跌资产的短期延续。",
        "falsification": "横截面领先在 PIT 排名、容量和成本约束下不能保持。",
        "primary": "cross_section_return_zscore",
        "confirmation": "directional_cross_section_breadth_alignment",
    },
    {
        "familyId": "opening_range_failure_reversal",
        "displayNameZh": "开盘区间失败反转",
        "timeframe": "1h",
        "mechanism": "前一根突破近期边界后，本根收回区间，测试失败突破反转。",
        "falsification": "收回事件在独立窗口没有正期望，或回撤和成本不可接受。",
        "primary": "failed_boundary_excursion / prior_atr14",
        "confirmation": "directional_reentry_depth / prior_atr14",
    },
)


def _receipt_hash(payload: Mapping[str, Any]) -> str:
    return stable_hash(
        {key: value for key, value in dict(payload).items() if key != "receiptHash"},
        prefix="v27_data_readiness_receipt",
    )


def build_v27_fixed_universe_semantics_matrix(
    *,
    timeframe: str,
    source_matrix: Sequence[Mapping[str, Any]],
    frames: Mapping[str, pd.DataFrame],
    start: str,
    end_exclusive: str,
) -> list[dict[str, Any]]:
    """Certify closed-candle PIT semantics for a preregistered fixed universe.

    The source matrix PIT flag is preserved separately because it describes
    historical dynamic-universe membership, which this fixed-universe campaign
    neither needs nor claims to reconstruct.
    """

    timeframe = str(timeframe)
    start_at = pd.Timestamp(start)
    end_at = pd.Timestamp(end_exclusive)
    if start_at.tzinfo is None:
        start_at = start_at.tz_localize("UTC")
    else:
        start_at = start_at.tz_convert("UTC")
    if end_at.tzinfo is None:
        end_at = end_at.tz_localize("UTC")
    else:
        end_at = end_at.tz_convert("UTC")
    interval = {"1h": pd.Timedelta(hours=1), "4h": pd.Timedelta(hours=4)}.get(
        timeframe
    )
    if interval is None:
        raise ValueError(f"unsupported_v27_timeframe:{timeframe}")
    expected_rows = max(1, int((end_at - start_at) / interval))
    source_index = {
        (str(row.get("instrumentId") or ""), str(row.get("field") or "")): dict(row)
        for row in source_matrix
        if str(row.get("timeframe") or "") == timeframe
    }
    rows: list[dict[str, Any]] = []
    for instrument, raw in sorted(frames.items()):
        frame = _normalise_frame(raw)
        bounded = frame[(frame["date"] >= start_at) & (frame["date"] < end_at)]
        coverage = min(100.0, 100.0 * len(bounded) / expected_rows)
        maximum = bounded["date"].max() if len(bounded) else None
        for field in _REQUIRED_FIELDS:
            source = source_index.get((instrument, field), {})
            causal = bool(source.get("causal") is True)
            available_at = str(source.get("availableAtRule") or "")
            source_hash = str(source.get("hash") or "")
            ready = bool(
                len(bounded)
                and field in bounded
                and coverage >= 95.0
                and causal
                and available_at == "candle_close_timestamp"
                and source_hash
                and maximum is not None
                and maximum < end_at
            )
            row: dict[str, Any] = {
                "schemaVersion": "v27_fixed_universe_field_semantics_v1",
                "instrumentId": instrument,
                "timeframe": timeframe,
                "field": field,
                "status": "ready_fixed_universe_pit" if ready else "blocked",
                "coveragePct": round(coverage, 6),
                "rowCount": int(len(bounded)),
                "causal": causal,
                "pointInTime": bool(ready),
                "sourcePointInTime": bool(source.get("pointInTime") is True),
                "pointInTimeScope": "closed_candle_availability_only",
                "universeMembershipPIT": "not_applicable_fixed_universe",
                "availableAtRule": available_at,
                "sourceHash": source_hash,
                "window": {
                    "start": start_at.isoformat(),
                    "endExclusive": end_at.isoformat(),
                },
                "knownLimitations": [
                    "source exchange provenance remains unverified",
                    "historical dynamic-universe membership is not reconstructed",
                ],
            }
            row["hash"] = stable_hash(row, prefix="v27_fixed_universe_semantics")
            rows.append(row)
    return rows


def build_v27_data_readiness_receipt(
    *,
    timeframe: str,
    matrix: Sequence[Mapping[str, Any]],
    capacity_profile: Mapping[str, Any],
) -> dict[str, Any]:
    """Certify data semantics before any V27 candidate identity is created."""

    timeframe = str(timeframe)
    relevant = [dict(row) for row in matrix if str(row.get("timeframe")) == timeframe]
    instruments = sorted(
        {str(row.get("instrumentId") or "") for row in relevant if row.get("instrumentId")}
    )
    blockers: list[str] = []
    semantic_checks = 0
    passing_checks = 0
    for instrument in instruments:
        for field in _REQUIRED_FIELDS:
            semantic_checks += 1
            row = next(
                (
                    item
                    for item in relevant
                    if str(item.get("instrumentId")) == instrument
                    and str(item.get("field")) == field
                ),
                None,
            )
            passed = bool(
                row
                and str(row.get("status") or "").startswith("ready")
                and float(row.get("coveragePct") or 0.0) >= 95.0
                and int(row.get("rowCount") or 0) > 0
                and row.get("causal") is True
                and row.get("pointInTime") is True
                and str(row.get("availableAtRule") or "")
                and str(row.get("hash") or "")
            )
            passing_checks += int(passed)
            if not passed:
                blockers.append(f"semantic_coverage_failed:{instrument}:{field}")

    eligible = sorted(
        str(value) for value in capacity_profile.get("eligibleInstruments", []) if str(value)
    )
    profile_instruments = sorted(
        str(value) for value in capacity_profile.get("instrumentSet", []) if str(value)
    )
    capacity_ready = bool(
        capacity_profile.get("status") == "ready"
        and profile_instruments
        and eligible == profile_instruments
        and set(instruments).issubset(set(eligible))
        and str(capacity_profile.get("profileHash") or "")
    )
    if not capacity_ready:
        blockers.append("capacity_coverage_below_100_pct")
    if not instruments:
        blockers.append("semantic_matrix_empty")

    ready = not blockers and semantic_checks > 0 and passing_checks == semantic_checks
    payload: dict[str, Any] = {
        "schemaVersion": "v27_data_readiness_receipt_v1",
        "timeframe": timeframe,
        "status": "ready" if ready else "data_blocked_before_candidate_creation",
        "requiredFields": list(_REQUIRED_FIELDS),
        "instrumentCount": len(instruments),
        "eligibleInstrumentCount": len(eligible),
        "semanticCheckCount": semantic_checks,
        "semanticPassCount": passing_checks,
        "semanticCoveragePct": round(100.0 * passing_checks / semantic_checks, 6)
        if semantic_checks
        else 0.0,
        "capacityCoveragePct": 100.0 if capacity_ready else 0.0,
        "dataProfileHash": str(capacity_profile.get("profileHash") or ""),
        "blockers": sorted(set(blockers)),
        "candidateIdCreationCount": 0,
        "candidateTrialBudgetConsumed": 0,
        "formalBudgetConsumed": 0,
        "economicReadCount": 0,
        "exitResultReadCount": 0,
        "statisticalResultReadCount": 0,
        "lockedOosReadCount": 0,
    }
    payload["receiptHash"] = _receipt_hash(payload)
    return payload


def build_v27_hypothesis_specs(
    *, source_references: Iterable[str]
) -> list[dict[str, Any]]:
    references = sorted({str(value) for value in source_references if str(value)})
    rows: list[dict[str, Any]] = []
    for index, definition in enumerate(_FAMILY_DEFINITIONS, start=1):
        row: dict[str, Any] = {
            "schemaVersion": "v27_directional_event_hypothesis_v1",
            "hypothesisId": f"v27-hyp-{index:02d}-{definition['familyId']}",
            "familyId": definition["familyId"],
            "displayNameZh": definition["displayNameZh"],
            "marketMechanism": definition["mechanism"],
            "falsificationCondition": definition["falsification"],
            "strategyType": "directional_event",
            "timeframe": definition["timeframe"],
            "directions": ["long", "short"],
            "requiredFields": list(_REQUIRED_FIELDS),
            "optionalFields": ["reported_volume"],
            "primaryRankingSemantic": definition["primary"],
            "confirmationRankingSemantic": definition["confirmation"],
            "sourceReferences": references,
            "resultDrivenFormulaSearchAllowed": False,
        }
        row["hypothesisHash"] = stable_hash(row, prefix="v27_hypothesis")
        rows.append(row)
    return rows


def _ranking_contract(
    *, candidate_id: str, hypothesis: Mapping[str, Any], receipt: Mapping[str, Any]
) -> dict[str, Any]:
    timeframe = str(hypothesis["timeframe"])
    lookback = "30d/180_closed_bars" if timeframe == "4h" else "30d/720_closed_bars"
    return build_candidate_ranking_contract(
        candidate_id=candidate_id,
        family_id=str(hypothesis["familyId"]),
        primary_event_severity={
            "semanticDefinition": hypothesis["primaryRankingSemantic"],
            "sourceVariables": ["open", "high", "low", "close", "atr14"],
            "formula": hypothesis["primaryRankingSemantic"],
            "normalization": "dimensionless_at_signal_close",
            "lookback": lookback,
            "order": "descending",
            "availableAt": "signal_candle_close",
            "pointInTimeRule": "closed_bars_at_or_before_signal_only",
            "missingPolicy": "reject_signal",
        },
        confirmation_strength={
            "semanticDefinition": hypothesis["confirmationRankingSemantic"],
            "sourceVariables": ["open", "high", "low", "close"],
            "formula": hypothesis["confirmationRankingSemantic"],
            "normalization": "dimensionless_at_signal_close",
            "lookback": "event_bar_and_prior_closed_bars",
            "order": "descending",
            "availableAt": "signal_candle_close",
            "pointInTimeRule": "closed_bars_at_or_before_signal_only",
            "missingPolicy": "reject_signal",
        },
        liquidity_30d={
            "dataProfileHash": receipt["dataProfileHash"],
            "formula": "sum(close * reported_volume) over trailing 30d closed bars",
            "lookback": lookback,
            "order": "descending",
            "availableAt": "signal_candle_close",
            "missingPolicy": "reject_signal",
        },
        instrument_id={"order": "ascending", "exactCanonicalIdentity": True},
    )


def build_v27_candidate_specs(
    hypotheses: Iterable[Mapping[str, Any]],
    receipts: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    hypotheses = [dict(row) for row in hypotheses]
    required_timeframes = {str(row["timeframe"]) for row in hypotheses}
    for timeframe in sorted(required_timeframes):
        receipt = dict(receipts.get(timeframe) or {})
        if receipt.get("status") != "ready" or receipt.get("receiptHash") != _receipt_hash(receipt):
            raise ValueError(f"data_blocked_before_candidate_creation:{timeframe}")

    candidates: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        timeframe = str(hypothesis["timeframe"])
        receipt = dict(receipts[timeframe])
        for variant, direction in enumerate(("long", "short"), start=1):
            candidate_id = (
                f"v27-{hypothesis['familyId']}-{timeframe}-{direction}-v{variant}"
            )
            exit_policy = {
                "policyId": "advisory_r_time_stop_v2",
                "targetR": 1.5,
                "targetIsUniversalSelectionGate": False,
                "initialStopAuthoritative": True,
                "maximumHoldAuthoritative": True,
                "noStopWidening": True,
            }
            candidate: dict[str, Any] = {
                "schemaVersion": "v27_directional_event_candidate_v1",
                "candidateId": candidate_id,
                "hypothesisId": hypothesis["hypothesisId"],
                "familyId": hypothesis["familyId"],
                "strategyType": "directional_event",
                "direction": direction,
                "timeframe": timeframe,
                "entryDefinition": {
                    "setupId": hypothesis["familyId"],
                    "setupVersion": "1",
                    "signalAtClosedBarOnly": True,
                    "entryAtNextBarOpen": True,
                    "confirmationRoles": ["filter", "veto", "ranking"],
                },
                "initialStop": {"type": "atr", "atrPeriod": 14, "atrMultiple": 1.25},
                "exitPolicy": exit_policy,
                "maximumHoldBars": 18 if timeframe == "4h" else 36,
                "rankingLookbackBars": 180 if timeframe == "4h" else 720,
                "requiredDataProfile": "ohlcv_core_directional_v1",
                "dataReadinessReceiptHash": receipt["receiptHash"],
                "capitalPolicyProfile": "v18_frozen_capital_policy",
                "GatePolicy": {
                    "policyId": "v18_3_economic_gate_with_advisory_r",
                    "universalTwoRHardGate": False,
                    "economicGatesRemainHard": True,
                    "resultDrivenRelaxationForbidden": True,
                },
                "coreSetupCount": 1,
                "coreEngineChangedForCandidate": False,
                "adapterType": "generated_directional_event_adapter",
                "freqtradeAdapterType": "generated_directional_event_freqtrade_adapter",
            }
            candidate["candidateRankingContract"] = _ranking_contract(
                candidate_id=candidate_id, hypothesis=hypothesis, receipt=receipt
            )
            candidate["candidateSpecHash"] = stable_hash(
                candidate, prefix="v27_candidate_spec"
            )
            candidates.append(candidate)
    if len(candidates) > 16:
        raise ValueError("v27_candidate_budget_exceeded")
    return candidates


def _normalise_frame(value: pd.DataFrame) -> pd.DataFrame:
    frame = value.copy()
    if "date" not in frame:
        frame["date"] = frame.index
    frame["date"] = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    frame = frame.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame.get(column, 0.0), errors="coerce")
    return frame


def _atr(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    previous = frame["close"].shift(1)
    ranges = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous).abs(),
            (frame["low"] - previous).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return ranges.rolling(window, min_periods=window).mean()


def materialize_v27_ranking_rows(
    *,
    candidate: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame],
    signals: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Materialize only signal-time ranking values from closed bars."""

    normalized = {symbol: _normalise_frame(frame) for symbol, frame in frames.items()}
    return_panel = pd.DataFrame(
        {
            symbol: frame.set_index("date")["close"].pct_change()
            for symbol, frame in normalized.items()
        }
    ).sort_index()
    rows: list[dict[str, Any]] = []
    family = str(candidate["familyId"])
    direction = str(candidate["direction"])
    sign = 1.0 if direction == "long" else -1.0
    lookback = int(candidate.get("rankingLookbackBars") or 1)
    for source in signals:
        signal = dict(source)
        symbol = str(signal["symbol"])
        frame = normalized[symbol]
        index = int(signal["signalBarIndex"])
        atr = _atr(frame)
        prior_atr = float(atr.shift(1).iloc[index])
        if not np.isfinite(prior_atr) or prior_atr <= 0:
            continue
        open_value = float(frame.at[index, "open"])
        high = float(frame.at[index, "high"])
        low = float(frame.at[index, "low"])
        close = float(frame.at[index, "close"])
        bar_range = max(high - low, 1e-12)
        close_location = (close - low) / bar_range
        primary = 0.0
        confirmation = close_location if direction == "long" else 1.0 - close_location
        if family == "range_expansion_close_followthrough":
            primary = bar_range / prior_atr
        elif family == "liquidity_gap_reentry":
            previous_close = float(frame.at[index - 1, "close"])
            gap = open_value - previous_close
            primary = abs(gap) / prior_atr
            confirmation = max(0.0, sign * (close - open_value) / max(abs(gap), 1e-12))
        elif family == "cross_section_dispersion_leader_followthrough":
            timestamp = frame.at[index, "date"]
            cross_section = return_panel.loc[timestamp].dropna()
            local_return = float(cross_section.get(symbol, 0.0))
            std = float(cross_section.std(ddof=0))
            mean = float(cross_section.mean())
            z_score = (local_return - mean) / std if std > 0 else 0.0
            primary = sign * z_score
            confirmation = float((sign * cross_section > 0).mean())
        elif family == "opening_range_failure_reversal":
            prior_high = float(frame["high"].rolling(12, min_periods=12).max().shift(2).iloc[index])
            prior_low = float(frame["low"].rolling(12, min_periods=12).min().shift(2).iloc[index])
            if direction == "long":
                primary = max(0.0, prior_low - float(frame.at[index - 1, "low"])) / prior_atr
                confirmation = max(0.0, close - prior_low) / prior_atr
            else:
                primary = max(0.0, float(frame.at[index - 1, "high"]) - prior_high) / prior_atr
                confirmation = max(0.0, prior_high - close) / prior_atr
        else:
            raise ValueError(f"unknown_v27_ranking_family:{family}")
        start = max(0, index - lookback + 1)
        turnover = (frame["close"] * frame["volume"]).iloc[start : index + 1]
        liquidity = float(turnover.sum())
        values = (primary, confirmation, liquidity)
        if not all(np.isfinite(value) for value in values):
            continue
        row: dict[str, Any] = {
            "candidateId": candidate["candidateId"],
            "signalId": signal["signalId"],
            "instrumentId": signal.get("instrumentId") or symbol,
            "primaryEventSeverity": float(primary),
            "confirmationStrength": float(confirmation),
            "liquidity30d": liquidity,
            "availableAt": signal["signalTimestamp"],
            "sourceHash": stable_hash(
                {
                    "candidateId": candidate["candidateId"],
                    "signalId": signal["signalId"],
                    "values": values,
                    "availableAt": signal["signalTimestamp"],
                },
                prefix="v27_ranking_source",
            ),
        }
        rows.append(row)
    return rows


def certify_v27_capacity_completeness(
    certification: Mapping[str, Any],
) -> dict[str, Any]:
    source = dict(certification)
    assigned = int(source.get("assignedEventCount") or 0)
    available = int(source.get("capacityInputAvailableCount") or 0)
    unavailable = int(source.get("capacityInputUnavailableCount") or 0)
    passed = bool(
        source.get("certificationStatus") == "passed"
        and assigned > 0
        and available == assigned
        and unavailable == 0
        and int(source.get("economicResultReadCount") or 0) == 0
    )
    payload: dict[str, Any] = {
        "schemaVersion": "v27_strict_capacity_completeness_v1",
        **source,
        "status": "passed" if passed else "failed",
        "strictCoveragePct": round(100.0 * available / assigned, 6) if assigned else 0.0,
        "requiresEveryAssignedEvent": True,
    }
    payload["certificationHash"] = stable_hash(
        payload, prefix="v27_strict_capacity_completeness"
    )
    return payload


def _write_markdown(path: Path, lines: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8", newline="\n")


def _artifact_manifest(root: Path, names: Sequence[str]) -> dict[str, Any]:
    artifacts: list[dict[str, Any]] = []
    for name in names:
        path = root / name
        artifacts.append(
            {
                "path": name.replace("\\", "/"),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "sizeBytes": path.stat().st_size,
            }
        )
    payload: dict[str, Any] = {
        "schemaVersion": "v27_artifact_manifest_v1",
        "artifactCount": len(artifacts),
        "artifacts": artifacts,
    }
    payload["manifestHash"] = stable_hash(payload, prefix="v27_artifact_manifest")
    return payload


def run_v27_candidate_research(
    *,
    reports_root: Path,
    program_id: str,
    generated_at: str,
    implementation_commit: str,
    frames: Mapping[str, Mapping[str, pd.DataFrame]],
    receipts: Mapping[str, Mapping[str, Any]],
    capacity_profiles: Mapping[str, Mapping[str, Any]],
    source_references: Iterable[str],
    data_access_report: Mapping[str, Any] | None = None,
    candidate_semantics_matrix: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run the bounded V27 prefilter without consuming formal or OOS results."""

    root = Path(reports_root) / "automatic_strategy_to_demo" / program_id / "v27"
    hypotheses = build_v27_hypothesis_specs(source_references=source_references)
    candidates = build_v27_candidate_specs(hypotheses, receipts)
    structural_certificates: list[dict[str, Any]] = []
    ranking_certificates: list[dict[str, Any]] = []
    capacity_certificates: list[dict[str, Any]] = []
    ranking_records: dict[str, list[dict[str, Any]]] = {}
    prefilter_results: list[dict[str, Any]] = []

    for candidate in candidates:
        candidate_id = str(candidate["candidateId"])
        timeframe = str(candidate["timeframe"])
        candidate_frames = dict(frames.get(timeframe) or {})
        adapter = GeneratedDirectionalEventAdapter(candidate_id=candidate_id)
        signals = [
            dict(row)
            for row in adapter.load_signals(candidate=candidate, frames=candidate_frames)
        ]
        translated = translated_load_signals(
            candidate=candidate,
            frames=candidate_frames,
        )
        fixture_parity, fixture_reference, fixture_translated = adapter.run_fixture_parity(
            candidate=candidate
        )
        signal_ids = [str(row.get("signalId") or "") for row in signals]
        structural_passed = bool(
            candidate_frames
            and signals
            and len(signal_ids) == len(set(signal_ids))
            and all(row.get("instrumentId") for row in signals)
            and signals == translated
            and fixture_reference == fixture_translated
            and fixture_parity.get("status") == "passed"
        )
        structural: dict[str, Any] = {
            "schemaVersion": "v27_candidate_structural_certification_v1",
            "candidateId": candidate_id,
            "status": "passed" if structural_passed else "failed",
            "actualSignalCount": len(signals),
            "uniqueSignalIdentityCount": len(set(signal_ids)),
            "actualTranslationParity": signals == translated,
            "fixtureParity": fixture_parity,
            "candidateNeutralCore": True,
            "candidateSpecificCoreImportCount": 0,
            "economicResultReadCount": 0,
            "lockedOosReadCount": 0,
        }
        structural["certificationHash"] = stable_hash(
            structural, prefix="v27_structural_certification"
        )
        structural_certificates.append(structural)

        ranking_rows = materialize_v27_ranking_rows(
            candidate=candidate,
            frames=candidate_frames,
            signals=signals,
        )
        records, ranking = materialize_candidate_ranking_evidence(
            signals=signals,
            ranking_rows=ranking_rows,
            contract=candidate["candidateRankingContract"],
        )
        ranking_records[candidate_id] = records
        ranking_certificates.append(ranking)

        raw_capacity = certify_real_signal_capacity(
            adapter=adapter,
            candidate=candidate,
            frames=candidate_frames,
            capacity_profile=dict(capacity_profiles.get(timeframe) or {}),
            current_equity=10_000.0,
        )
        capacity = certify_v27_capacity_completeness(raw_capacity)
        capacity_certificates.append(capacity)

        if not (
            structural.get("status") == "passed"
            and ranking.get("status") == "passed"
            and capacity.get("status") == "passed"
        ):
            prefilter_results.append(
                {
                    "schemaVersion": "automatic_prefilter_candidate_result_v1",
                    "candidateId": candidate_id,
                    "familyId": candidate["familyId"],
                    "passed": False,
                    "metrics": {},
                    "gates": {},
                    "failedGates": [
                        name
                        for name, passed in (
                            ("structuralCertification", structural.get("status") == "passed"),
                            ("rankingCertification", ranking.get("status") == "passed"),
                            ("capacityCertification", capacity.get("status") == "passed"),
                        )
                        if not passed
                    ],
                    "formalPassClaimCount": 0,
                    "lockedOosAccessCount": 0,
                }
            )
            continue

        base_events = [
            dict(row)
            for row in adapter.replay(
                candidate=candidate,
                frames=candidate_frames,
                round_trip_cost_rate=0.0012,
            )
        ]
        stress_events = [
            dict(row)
            for row in adapter.replay(
                candidate=candidate,
                frames=candidate_frames,
                round_trip_cost_rate=0.0018,
            )
        ]
        benchmark_events = _benchmark_events(
            candidate=candidate,
            candidate_frames=candidate_frames,
            base_events=base_events,
            round_trip_cost_rate=0.0012,
        )
        prefilter_results.append(
            evaluate_prefilter_events(
                candidate_id=candidate_id,
                family_id=str(candidate["familyId"]),
                base_events=base_events,
                stress_events=stress_events,
                benchmark_events=benchmark_events,
            )
        )

    route = build_prefilter_route(prefilter_results)
    next_stage = (
        "v28_formal_validation"
        if route["formalCandidateIds"]
        else "completed_zero_qualified_candidates"
    )
    summary: dict[str, Any] = {
        "schemaVersion": "v27_candidate_research_summary_v1",
        "programId": program_id,
        "stage": "v27_completed",
        "generatedAt": generated_at,
        "implementationCommit": implementation_commit,
        "hypothesisFamilyCount": len(hypotheses),
        "candidateCount": len(candidates),
        "candidateTrialCount": len(candidates),
        "structuralPassCount": sum(
            row["status"] == "passed" for row in structural_certificates
        ),
        "rankingPassCount": sum(
            row["status"] == "passed" for row in ranking_certificates
        ),
        "capacityPassCount": sum(
            row["status"] == "passed" for row in capacity_certificates
        ),
        "prefilterPassCount": sum(bool(row.get("passed")) for row in prefilter_results),
        "formalCandidateCount": len(route["formalCandidateIds"]),
        "formalCandidateIds": route["formalCandidateIds"],
        "nextStage": next_stage,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "exitResultReadCount": 0,
        "statisticalResultReadCount": 0,
        "lockedOosReadCount": 0,
        "releaseCount": 0,
        "demoApprovalCount": 0,
        "demoArm": False,
        "orderCount": 0,
    }
    summary["summaryHash"] = stable_hash(summary, prefix="v27_candidate_research")

    artifacts: dict[str, Any] = {
        "data_readiness_receipts.json": dict(receipts),
        "data_access_report.json": dict(data_access_report or {}),
        "candidate_semantics_matrix.json": [
            dict(row) for row in (candidate_semantics_matrix or [])
        ],
        "capacity_profiles.json": dict(capacity_profiles),
        "hypothesis_inventory.json": hypotheses,
        "candidate_inventory.json": candidates,
        "candidate_structural_certification.json": structural_certificates,
        "candidate_ranking_certification.json": ranking_certificates,
        "candidate_ranking_evidence.json": ranking_records,
        "candidate_capacity_certification.json": capacity_certificates,
        "prefilter_results.json": prefilter_results,
        "prefilter_route.json": route,
        "v27_summary.json": summary,
    }
    for name, value in artifacts.items():
        write_json_atomic(root / name, value)
    _write_markdown(
        root / "v27_summary.md",
        [
            "# V27 New Candidate Research",
            "",
            f"- Program: `{program_id}`",
            f"- Hypothesis families: {len(hypotheses)}",
            f"- Candidate trials: {len(candidates)} / 16",
            f"- Prefilter passes: {summary['prefilterPassCount']}",
            f"- Formal candidates: {summary['formalCandidateCount']} / 6",
            f"- Next stage: `{next_stage}`",
            "- Formal runs: 0",
            "- Locked OOS reads: 0",
            "- Releases / Demo approvals / orders: 0 / 0 / 0",
        ],
    )
    manifest_names = [*artifacts, "v27_summary.md"]
    write_json_atomic(root / "artifact_manifest.json", _artifact_manifest(root, manifest_names))
    return summary


__all__ = [
    "build_v27_candidate_specs",
    "build_v27_data_readiness_receipt",
    "build_v27_fixed_universe_semantics_matrix",
    "build_v27_hypothesis_specs",
    "certify_v27_capacity_completeness",
    "materialize_v27_ranking_rows",
    "run_v27_candidate_research",
]
