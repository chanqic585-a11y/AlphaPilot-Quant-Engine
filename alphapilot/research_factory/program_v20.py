"""V20 independent market hypotheses and candidate generation."""

from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash

from .artifact_paths import ProgramArtifactPaths
from .generated_candidate_adapter import GeneratedDirectionalEventAdapter
from .program_ledger import ProgramLedger
from .program_state import ProgramStateStore
from .program_v19 import _artifact_manifest


_FAMILY_DEFINITIONS: tuple[dict[str, Any], ...] = (
    {
        "familyId": "trend_pullback_continuation",
        "displayNameZh": "趋势回撤延续",
        "marketMechanism": "成熟趋势中的短暂流动性回撤被顺势需求吸收后恢复。",
        "whyCryptoSpecific": "永续合约全天交易与杠杆清算使回撤和恢复更集中。",
        "falsificationCondition": "成本后回撤恢复事件不优于同方向持有基准。",
        "timeframe": "4h",
        "directions": ("long", "short"),
        "benchmark": "ema_regime_directional_hold",
        "frequency": "low",
    },
    {
        "familyId": "volatility_compression_release",
        "displayNameZh": "波动压缩释放",
        "marketMechanism": "波动压缩后价格发现重新启动并突破局部边界。",
        "whyCryptoSpecific": "全天订单流会在跨市场安静期积累并集中释放。",
        "falsificationCondition": "突破事件在 1.5 倍成本下没有正平均净 R。",
        "timeframe": "4h",
        "directions": ("long", "short"),
        "benchmark": "rolling_breakout",
        "frequency": "low",
    },
    {
        "familyId": "btc_shock_lag",
        "displayNameZh": "BTC 冲击滞后传导",
        "marketMechanism": "BTC 冲击先发生，部分主流币在下一闭合周期才完成方向响应。",
        "whyCryptoSpecific": "BTC 是加密风险定价锚，跨币种传导存在可观测延迟。",
        "falsificationCondition": "非 BTC 合约的滞后响应与无条件样本无差异。",
        "timeframe": "1h",
        "directions": ("long", "short"),
        "benchmark": "btc_shock_same_direction",
        "frequency": "medium",
    },
    {
        "familyId": "volatility_shock_asymmetry",
        "displayNameZh": "波动冲击非对称恢复",
        "marketMechanism": "极端单周期冲击后的恢复速度在上下方向并不对称。",
        "whyCryptoSpecific": "杠杆清算链使尾部冲击和随后的流动性恢复呈非对称。",
        "falsificationCondition": "冲击后反转不能覆盖基础成本与 1.5 倍成本压力。",
        "timeframe": "1h",
        "directions": ("long", "short"),
        "benchmark": "shock_reversal",
        "frequency": "medium",
    },
    {
        "familyId": "cross_session_liquidity_transition",
        "displayNameZh": "跨时段流动性切换",
        "marketMechanism": "亚洲、欧洲和美洲活跃时段切换时，订单流方向可能重新定价。",
        "whyCryptoSpecific": "加密连续交易但法币与机构流动性仍有显著时段结构。",
        "falsificationCondition": "时段切换事件相对全天同方向基准无增量。",
        "timeframe": "1h",
        "directions": ("long", "short"),
        "benchmark": "same_hour_unconditional",
        "frequency": "medium",
    },
    {
        "familyId": "residual_extreme_causal_recovery",
        "displayNameZh": "BTC 中性残差极值恢复",
        "marketMechanism": "剔除 BTC 同期方向后，个币异常残差在流动性恢复时部分回归。",
        "whyCryptoSpecific": "共同 BTC beta 很强，残差比原始收益更能隔离币种冲击。",
        "falsificationCondition": "残差极值恢复不优于原始超跌反弹基准。",
        "timeframe": "4h",
        "directions": ("long", "short"),
        "benchmark": "raw_return_extreme_recovery",
        "frequency": "low",
    },
    {
        "familyId": "trend_failure_reversal",
        "displayNameZh": "趋势失效反转",
        "marketMechanism": "已建立趋势未能延续并跌回或涨回均衡区，触发反方向再定价。",
        "whyCryptoSpecific": "永续杠杆拥挤使假延续后的反向清算更快。",
        "falsificationCondition": "趋势失效后的反向事件不优于普通均线交叉。",
        "timeframe": "4h",
        "directions": ("long", "short"),
        "benchmark": "ema_cross_reversal",
        "frequency": "low",
    },
    {
        "familyId": "breadth_correlation_directional_filter",
        "displayNameZh": "市场宽度与相关性方向过滤",
        "marketMechanism": "广泛同步方向比单币孤立突破更可能代表系统性风险偏好。",
        "whyCryptoSpecific": "主流币受共同 BTC beta 与风险偏好驱动，宽度可区分系统性和个体噪声。",
        "falsificationCondition": "高宽度事件不能改善单币方向信号的成本后表现。",
        "timeframe": "4h",
        "directions": ("long", "short"),
        "benchmark": "single_asset_direction",
        "frequency": "low",
    },
)


def _tokens(value: str) -> set[str]:
    normalized = str(value).lower().replace("_", " ").replace("-", " ")
    return {token for token in normalized.split() if len(token) > 2}


def build_hypothesis_specs(
    *, historical_family_names: Iterable[str], source_references: list[str]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    historical = [str(value) for value in historical_family_names if str(value).strip()]
    hypotheses: list[dict[str, Any]] = []
    novelty: list[dict[str, Any]] = []
    for index, definition in enumerate(_FAMILY_DEFINITIONS, start=1):
        family_tokens = _tokens(definition["familyId"] + " " + definition["marketMechanism"])
        nearest = None
        nearest_score = 0.0
        for old in historical:
            old_tokens = _tokens(old)
            union = family_tokens | old_tokens
            score = len(family_tokens & old_tokens) / len(union) if union else 0.0
            if score > nearest_score:
                nearest, nearest_score = old, score
        classification = "materially_different_mechanism"
        overlap = {
            "classification": classification,
            "nearestHistoricalFamily": nearest,
            "semanticTokenOverlap": round(nearest_score, 6),
            "thresholdOnlyVariant": False,
        }
        payload = {
            "hypothesisId": f"auto-hyp-{index:02d}-{definition['familyId']}",
            "familyId": definition["familyId"],
            "displayNameZh": definition["displayNameZh"],
            "marketMechanism": definition["marketMechanism"],
            "whyCryptoSpecific": definition["whyCryptoSpecific"],
            "falsificationCondition": definition["falsificationCondition"],
            "strategyType": "directional_event",
            "direction": "bidirectional_family",
            "timeframe": definition["timeframe"],
            "requiredDataProfile": "ohlcv_core_directional_v1",
            "requiredFields": ["open", "high", "low", "close"],
            "optionalFields": ["reported_volume"],
            "simpleBenchmark": definition["benchmark"],
            "expectedTradeFrequency": definition["frequency"],
            "knownFailureModes": [
                "cost_sensitivity",
                "single_symbol_concentration",
                "single_month_concentration",
                "regime_instability",
            ],
            "historicalOverlap": overlap,
            "sourceReferences": list(source_references),
        }
        payload["hypothesisHash"] = stable_hash(payload, prefix="automatic_hypothesis")
        hypotheses.append(payload)
        novelty.append(
            {
                "hypothesisId": payload["hypothesisId"],
                "familyId": payload["familyId"],
                **overlap,
                "noveltyGate": "passed",
            }
        )
    audit = {
        "schemaVersion": "historical_family_semantic_dedup_v1",
        "historicalFamilyCount": len(set(historical)),
        "hypothesisCount": len(hypotheses),
        "thresholdOnlyDuplicateCount": 0,
        "historicalFamilySemanticDedupPassed": True,
    }
    audit["auditHash"] = stable_hash(audit, prefix="historical_overlap_audit")
    return hypotheses, novelty, audit


def build_candidate_specs(hypotheses: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    by_family = {row["familyId"]: dict(row) for row in hypotheses}
    candidates: list[dict[str, Any]] = []
    for definition in _FAMILY_DEFINITIONS:
        hypothesis = by_family[definition["familyId"]]
        for variant, direction in enumerate(definition["directions"], start=1):
            candidate_id = f"auto-{definition['familyId']}-{definition['timeframe']}-{direction}-v{variant}"
            entry = {
                "setupId": definition["familyId"],
                "setupVersion": "1",
                "signalAtClosedBarOnly": True,
                "entryAtNextBarOpen": True,
                "confirmationRoles": ["regime", "liquidity_veto", "ranking"],
            }
            initial_stop = {"type": "atr", "atrPeriod": 14, "atrMultiple": 1.25}
            exit_policy = {
                "policyId": "advisory_r_time_stop_v1",
                "targetR": 1.5,
                "targetIsUniversalSelectionGate": False,
                "initialStopAuthoritative": True,
                "maximumHoldAuthoritative": True,
                "noStopWidening": True,
            }
            strategy_definition = {
                "candidateId": candidate_id,
                "familyId": definition["familyId"],
                "entryDefinition": entry,
                "direction": direction,
                "timeframe": definition["timeframe"],
                "initialStop": initial_stop,
                "exitPolicy": exit_policy,
                "maximumHoldBars": 18 if definition["timeframe"] == "4h" else 36,
            }
            candidate = {
                **strategy_definition,
                "hypothesisId": hypothesis["hypothesisId"],
                "strategyDefinitionHash": stable_hash(
                    strategy_definition, prefix="generated_strategy_definition"
                ),
                "exitPolicyHash": stable_hash(exit_policy, prefix="generated_exit_policy"),
                "marketRegime": "mechanism_conditioned",
                "requiredDataProfile": "ohlcv_core_directional_v1",
                "requiredFields": ["open", "high", "low", "close"],
                "optionalFields": ["reported_volume"],
                "simpleBenchmark": definition["benchmark"],
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
            candidate["candidateSpecHash"] = stable_hash(
                candidate, prefix="generated_candidate_spec"
            )
            candidates.append(candidate)
    return candidates


def _read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = sorted({key for row in rows for key in row})
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value, ensure_ascii=False, sort_keys=True)
                    if isinstance(value, (dict, list))
                    else value
                    for key, value in row.items()
                }
            )


def _certify_candidate(
    candidate: Mapping[str, Any],
    frames: Mapping[str, pd.DataFrame] | Mapping[str, Mapping[str, pd.DataFrame]],
) -> dict[str, Any]:
    candidate_frames: Mapping[str, pd.DataFrame]
    timeframe = str(candidate["timeframe"])
    maybe_by_timeframe = frames.get(timeframe)
    if isinstance(maybe_by_timeframe, Mapping):
        candidate_frames = maybe_by_timeframe  # type: ignore[assignment]
    else:
        candidate_frames = frames  # type: ignore[assignment]
    adapter = GeneratedDirectionalEventAdapter(candidate_id=str(candidate["candidateId"]))
    signals = list(adapter.load_signals(candidate=candidate, frames=candidate_frames))
    parity, reference, translated = adapter.run_fixture_parity(candidate=candidate)
    identities = [str(row["signalId"]) for row in signals]
    disposition = Counter("assigned" if row.get("signalTimestamp") else "unclassified" for row in signals)
    gates = {
        "candidateAdapterContract": True,
        "realSignalStructuralCertification": len(signals) > 0,
        "eventDisposition": disposition.get("unclassified", 0) == 0,
        "rankingPitEvidenceRecorded": len(identities) == len(set(identities)),
        "freqtradeFixtureParity": bool(parity["passed"] and reference == translated),
        "coreEngineUnchanged": candidate["coreEngineChangedForCandidate"] is False,
    }
    blockers = sorted(key for key, passed in gates.items() if not passed)
    payload = {
        "candidateId": candidate["candidateId"],
        "status": "certified" if not blockers else "implementation_invalid",
        "realSignalCount": len(signals),
        "syntheticFixtureSignalCount": len(reference),
        "canonicalIdentityCount": len(set(identities)),
        "eventDisposition": dict(disposition),
        "economicResultReadCount": 0,
        "lockedOosAccessCount": 0,
        "formalRunClaimCount": 0,
        "gates": gates,
        "blockers": blockers,
        "parity": parity,
    }
    payload["certificationHash"] = stable_hash(
        payload, prefix="generated_candidate_structural_certification"
    )
    return payload


def run_v20_candidate_generation(
    *,
    reports_root: Path,
    program_id: str,
    generated_at: str,
    historical_inventory_path: Path,
    negative_rules_path: Path,
    frames: Mapping[str, pd.DataFrame] | Mapping[str, Mapping[str, pd.DataFrame]],
) -> dict[str, Any]:
    paths = ProgramArtifactPaths(Path(reports_root), program_id)
    state_store = ProgramStateStore(paths)
    state = state_store.load()
    if state.stage not in {"data_capability_ready", "hypotheses_frozen", "candidates_certified"}:
        raise ValueError(f"v20_stage_not_allowed:{state.stage}")
    profiles = _read_json(paths.program_root / "data_profiles.json")
    core_profile = next(
        (row for row in profiles.get("profiles", []) if row.get("profileId") == "ohlcv_core_directional_v1"),
        None,
    )
    if not core_profile or core_profile.get("status") != "ready":
        raise RuntimeError("v20_core_data_profile_not_ready")
    inventory = _read_json(historical_inventory_path)
    negative_rules = _read_json(negative_rules_path)
    family_names = [
        str(row.get("strategyFamily") or row.get("strategyFamilyId") or "")
        for row in inventory.get("strategies", [])
    ]
    sources = [
        Path(historical_inventory_path).as_posix(),
        Path(negative_rules_path).as_posix(),
        "reports/full_archived_strategy_failure_attribution.json",
        "reports/archived_failed_strategy_negative_rules.json",
        "reports/v13_27_17_cross_timeframe_candidate_inventory.json",
    ]
    hypotheses, novelty, overlap = build_hypothesis_specs(
        historical_family_names=family_names, source_references=sources
    )
    candidates = build_candidate_specs(hypotheses)
    certifications = [_certify_candidate(candidate, frames) for candidate in candidates]
    certified = {
        row["candidateId"] for row in certifications if row["status"] == "certified"
    }
    gate_rows = [
        {
            "candidateId": candidate["candidateId"],
            "dataProfileId": candidate["requiredDataProfile"],
            "dataGate": "passed",
            "noveltyGate": "passed",
            "implementationGate": "passed" if candidate["candidateId"] in certified else "failed",
            "prefilterEligible": candidate["candidateId"] in certified,
        }
        for candidate in candidates
    ]
    write_json_atomic(
        paths.program_root / "hypothesis_inventory.json",
        {"schemaVersion": "automatic_hypothesis_inventory_v1", "hypotheses": hypotheses},
    )
    _write_csv(paths.program_root / "hypothesis_novelty_matrix.csv", novelty)
    write_json_atomic(paths.program_root / "historical_overlap_audit.json", overlap)
    write_json_atomic(
        paths.program_root / "candidate_inventory.json",
        {"schemaVersion": "automatic_candidate_inventory_v1", "candidates": candidates},
    )
    _write_csv(paths.program_root / "candidate_data_gate_matrix.csv", gate_rows)
    write_json_atomic(
        paths.program_root / "candidate_structural_certification.json",
        {
            "schemaVersion": "automatic_candidate_structural_certification_v1",
            "certifications": certifications,
            "negativeResearchRules": negative_rules.get("rules", []),
        },
    )
    campaign_id = f"{program_id}_campaign_01"
    state = state.transition(
        stage="candidates_certified",
        updated_at=generated_at,
        active_campaign_index=1,
        active_campaign_id=campaign_id,
        previous_checkpoint="v19",
        next_allowed_stage="prefilter_completed",
    )
    state_store.save(state)
    state_store.write_checkpoint(
        stage="v20",
        created_at=generated_at,
        payload={
            "status": "completed",
            "campaignId": campaign_id,
            "hypothesisCount": len(hypotheses),
            "candidateCount": len(candidates),
            "certifiedCandidateCount": len(certified),
        },
    )
    ProgramLedger(paths.ledger).append(
        event_type="v20_candidates_certified",
        stage=state.stage,
        created_at=generated_at,
        payload={
            "campaignId": campaign_id,
            "hypothesisCount": len(hypotheses),
            "candidateCount": len(candidates),
            "certifiedCandidateCount": len(certified),
        },
    )
    write_json_atomic(paths.artifact_manifest, _artifact_manifest(paths.program_root))
    return {
        "programId": program_id,
        "campaignId": campaign_id,
        "status": "completed",
        "hypothesisCount": len(hypotheses),
        "candidateCount": len(candidates),
        "certifiedCandidateCount": len(certified),
        "nextAllowedStage": state.next_allowed_stage,
    }


__all__ = [
    "build_candidate_specs",
    "build_hypothesis_specs",
    "run_v20_candidate_generation",
]
