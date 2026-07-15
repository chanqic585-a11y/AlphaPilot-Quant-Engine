"""Generate the full archived strategy evidence and failure analysis bundle."""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from alphapilot.reports.archived_strategy_evidence_index import build_evidence_index
from alphapilot.reports.archived_strategy_failure_attribution_v2 import (
    attribute_archived_failure,
    build_cross_strategy_patterns,
)
from alphapilot.reports.archived_strategy_failure_schema_v2 import (
    CORE_METRIC_FIELDS,
    EVIDENCE_LEVELS,
    FULL_TRADE_OUTPUT,
    OUTPUTS,
    REPORT_ID,
    SAFETY_BOUNDARY,
    STRATEGY_CORE_PRINCIPLES,
    STRATEGY_DOCS_DIR,
)
from alphapilot.reports.archived_strategy_metrics_normalizer import (
    merge_metric_rows,
    normalize_freqtrade_metrics,
    normalize_registry_metrics,
)
from alphapilot.reports.archived_strategy_trade_extractor import (
    extract_freqtrade_trades,
    read_freqtrade_strategy_result,
)
from alphapilot.reports.full_archived_strategy_inventory import build_full_inventory


REQUIRED_OUTPUTS = OUTPUTS


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def _write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _attach_evidence(
    inventory: list[dict[str, Any]], evidence: list[dict[str, Any]]
) -> None:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        if item.get("strategyId"):
            grouped[str(item["strategyId"])].append(item)
    for record in inventory:
        items = grouped.get(str(record["strategyId"]), [])
        if items:
            record["evidenceLevel"] = min(int(item["evidenceLevel"]) for item in items)
            record["evidenceCompleteness"] = round(
                max(float(item.get("completenessScore") or 0) for item in items), 4
            )
        record["evidenceArtifactCount"] = len(items)
        record["tradeEvidenceAvailable"] = any(
            bool(item.get("tradeRowsAvailable")) for item in items
        )
        record["evidenceArtifactIds"] = [item.get("artifactId") for item in items]


def _primary_freqtrade_artifacts(evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for item in evidence:
        if item.get("artifactType") != "freqtrade_backtest_zip" or not item.get("strategyId"):
            continue
        key = (str(item["strategyId"]), str(item.get("timeframe") or "unknown"))
        grouped[key].append(item)
    selected = []
    for items in grouped.values():
        selected.append(
            max(
                items,
                key=lambda item: (
                    int(item.get("backtestEndTs") or 0),
                    int(item.get("artifactMtimeNs") or 0),
                ),
            )
        )
    return sorted(selected, key=lambda item: (str(item["strategyId"]), str(item.get("timeframe"))))


def _normalize_legacy_metrics(record: dict[str, Any]) -> dict[str, Any]:
    source = dict(record.get("metrics") or {})
    result = {field: source.get(field) for field in CORE_METRIC_FIELDS}
    result.update(
        {
            "strategyId": record["strategyId"],
            "averageGrossR": source.get("grossRewardRiskR"),
            "longTradeCount": source.get("longTradeCount"),
            "shortTradeCount": source.get("shortTradeCount"),
            "pairCount": source.get("pairCount"),
            "timeframe": record.get("timeframe"),
            "bySplit": source.get("bySplit") or {},
            "byRegime": source.get("byRegime") or {},
            "bySymbol": source.get("bySymbol") or {},
            "byDirection": source.get("byDirection") or {},
            "byMonth": source.get("byMonth") or {},
            "byExitReason": source.get("byExitReason") or {},
            "byEnterTag": source.get("byEnterTag") or {},
            "costStress": source.get("costStress") or {},
            "metricSource": "legacy_status_archive",
        }
    )
    result["missingMetricFields"] = [
        field for field in CORE_METRIC_FIELDS if result.get(field) is None
    ]
    return result


def _sample_trades(rows: list[dict[str, Any]], limit: int = 120) -> list[dict[str, Any]]:
    if len(rows) <= limit:
        return rows
    winners = sorted(
        (item for item in rows if (_number(item.get("netRApprox")) or 0) > 0),
        key=lambda item: _number(item.get("netRApprox")) or 0,
        reverse=True,
    )
    losers = sorted(
        (item for item in rows if (_number(item.get("netRApprox")) or 0) <= 0),
        key=lambda item: _number(item.get("netRApprox")) or 0,
    )
    half = limit // 2
    return winners[:half] + losers[: limit - half]


def _trade_outputs(
    root: Path, evidence: list[dict[str, Any]]
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]], dict[str, Any]]:
    generated_path = root / FULL_TRADE_OUTPUT
    generated_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_by_strategy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    samples: list[dict[str, Any]] = []
    total_trades = 0
    artifact_count = 0
    extraction_errors = []
    with generated_path.open("w", encoding="utf-8") as full_handle:
        for artifact in _primary_freqtrade_artifacts(evidence):
            source = root / str(artifact["sourceZip"])
            strategy_name = str(artifact["strategyName"])
            try:
                rows = extract_freqtrade_trades(source, strategy_name, str(artifact["artifactId"]))
                strategy_result = read_freqtrade_strategy_result(source, strategy_name)
            except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
                extraction_errors.append(
                    {
                        "artifactId": artifact.get("artifactId"),
                        "sourcePath": artifact.get("sourcePath"),
                        "error": str(exc),
                    }
                )
                continue
            artifact["containsTrades"] = bool(rows)
            artifact["tradeCount"] = len(rows)
            artifact_count += 1
            total_trades += len(rows)
            for row in rows:
                row["strategyId"] = artifact["strategyId"]
                row["timeframe"] = artifact.get("timeframe")
                full_handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
            samples.extend(_sample_trades(rows, limit=12))
            metrics_by_strategy[str(artifact["strategyId"])].append(
                normalize_freqtrade_metrics(
                    str(artifact["strategyId"]),
                    artifact.get("timeframe"),
                    strategy_result,
                    rows,
                )
            )
    manifest = {
        "recordType": "generated_file_manifest",
        "fullTradeFile": FULL_TRADE_OUTPUT.as_posix(),
        "trackedInGit": False,
        "primaryArtifactCount": artifact_count,
        "tradeRowCount": total_trades,
        "extractionErrorCount": len(extraction_errors),
        "extractionErrors": extraction_errors,
        "method": (
            "One latest primary artifact per legacy strategy and timeframe; repeated tuning runs are not pooled."
        ),
    }
    manifest_path = root / OUTPUTS["tradeLevelJsonl"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False) + "\n", encoding="utf-8")
    return metrics_by_strategy, samples, manifest


def _metrics_matrix(
    inventory: list[dict[str, Any]],
    freqtrade_metrics: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = []
    for record in inventory:
        if record.get("identitySource") == "registry_version":
            metric = normalize_registry_metrics(record)
        elif record["strategyId"] in freqtrade_metrics:
            metric = merge_metric_rows(record["strategyId"], freqtrade_metrics[record["strategyId"]])
        else:
            metric = _normalize_legacy_metrics(record)
        metric.update(
            {
                "strategyName": record.get("strategyName"),
                "strategyFamily": record.get("strategyFamily"),
                "status": record.get("status"),
                "identitySource": record.get("identitySource"),
                "evidenceLevel": record.get("evidenceLevel"),
                "evidenceCompleteness": record.get("evidenceCompleteness"),
            }
        )
        rows.append(metric)
        record["metrics"] = metric
    return rows


def _coverage_audit(
    inventory: list[dict[str, Any]], evidence: list[dict[str, Any]], trade_manifest: dict[str, Any]
) -> dict[str, Any]:
    source_counts = Counter(item.get("identitySource") for item in inventory)
    level_counts = Counter(str(item.get("evidenceLevel")) for item in evidence)
    unresolved = [item for item in evidence if not item.get("strategyId")]
    return {
        "status": "completed_with_evidence_gaps" if unresolved else "completed",
        "strategyIdentityCount": len(inventory),
        "strategyFamilyCount": len({item.get("strategyFamily") for item in inventory}),
        "identitySourceCounts": dict(sorted(source_counts.items())),
        "registryArchivedVersionCount": source_counts.get("registry_version", 0),
        "legacyFreqtradeIdentityCount": source_counts.get("legacy_freqtrade_class", 0),
        "legacyStatusOnlyIdentityCount": source_counts.get("legacy_status_archive", 0),
        "evidenceArtifactCount": len(evidence),
        "evidenceLevelCounts": dict(sorted(level_counts.items())),
        "unresolvedEvidenceArtifactCount": len(unresolved),
        "tradeEvidenceStrategyCount": len(
            {item.get("strategyId") for item in evidence if item.get("tradeRowsAvailable")}
        ),
        "withoutTradeEvidenceCount": sum(not item.get("tradeEvidenceAvailable") for item in inventory),
        "primaryTradeArtifactCount": trade_manifest["primaryArtifactCount"],
        "extractedTradeRowCount": trade_manifest["tradeRowCount"],
        "notes": [
            "注册表版本是当前不可变身份主源。",
            "旧 Freqtrade 类保留为独立历史身份；没有可靠映射时不强行合并。",
            "逐笔提取只使用每个策略类和周期的最新主证据，避免重复试验放大样本。",
        ],
    }


def _evidence_gaps(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in inventory:
        missing = list(item.get("metrics", {}).get("missingMetricFields") or [])
        if not item.get("tradeEvidenceAvailable"):
            missing.append("tradeLevelRows")
        if not (item.get("metrics", {}).get("byRegime") or {}):
            missing.append("marketRegimeAttribution")
        if item.get("evidenceLevel", 4) >= 3:
            missing.append("structuredPrimaryEvidence")
        if missing:
            rows.append(
                {
                    "strategyId": item["strategyId"],
                    "strategyName": item.get("strategyName"),
                    "evidenceLevel": item.get("evidenceLevel"),
                    "missingFields": sorted(set(missing)),
                    "interpretation": "缺项保持 unavailable/null，不能作为通过证据。",
                }
            )
    return rows


def _signal_funnel(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for item in inventory:
        smoke = item.get("researchSmoke") or {}
        metrics = item.get("metrics") or {}
        rows.append(
            {
                "strategyId": item["strategyId"],
                "strategyName": item.get("strategyName"),
                "timeframe": item.get("timeframe"),
                "candidateBars": smoke.get("candidateBars"),
                "rawSignals": smoke.get("rawSignals") or smoke.get("signalCount"),
                "acceptedSignals": smoke.get("acceptedSignals"),
                "rejectedSignals": metrics.get("rejectedSignals"),
                "tradeCount": metrics.get("tradeCount"),
                "zeroTrade": metrics.get("tradeCount") == 0,
                "missingFunnelEvidence": not bool(smoke),
            }
        )
    return rows


def _negative_rules(attributions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    primary = Counter(item["primaryFailureType"] for item in attributions)
    secondary = Counter(
        failure for item in attributions for failure in item.get("secondaryFailureTypes") or []
    )
    empirical = [
        ("NEG_001", "净平均 R 不为正或利润因子低于 1 的策略不得晋级。", "signal_edge_failure"),
        ("NEG_002", "结构性负边际不能靠微调阈值或增加指标强行修复。", "signal_edge_failure"),
        ("NEG_003", "成本压力后失效的高频策略不得以毛收益解释为有效。", "cost_amplification"),
        ("NEG_004", "大量交易但单笔边际为负属于噪声放大，不属于分散化。", "overtrading"),
        ("NEG_005", "缺失指标、缺失逐笔或缺失锁定样本不能当作 0 或通过。", "data_evidence_gap"),
        ("NEG_006", "信号层和账户风险层必须分别通过，不能互相遮盖。", "risk_model_failure"),
        ("NEG_007", "马丁格尔、逆势加仓和放宽止损不得进入复活路径。", "rejected_risk_design"),
    ]
    rows = []
    for rule_id, rule, failure in empirical:
        count = primary.get(failure, 0) + secondary.get(failure, 0)
        rows.append(
            {
                "ruleId": rule_id,
                "rule": rule,
                "evidenceStrategyCount": count,
                "scope": "future_strategy_generation_and_promotion",
            }
        )
    return rows


def _reusable_components() -> list[dict[str, Any]]:
    components = [
        ("data_gate", "数据质量与来源校验", "在任何绩效判断前确认周期、币种、成本与时间范围。"),
        ("signal_audit", "信号漏斗和跳过原因", "保留候选、过滤、拒绝和成交各层计数。"),
        ("multi_timeframe_context", "高周期环境与低周期触发", "高周期只定义环境，低周期只负责入场触发。"),
        ("session_feature", "交易时段特征", "作为可检验特征，不按截图经验硬编码时段胜负。"),
        ("portfolio_exposure", "相关性与同向暴露控制", "按相关性、Beta 和方向管理组合风险。"),
        ("bounded_atr_risk", "有边界的 ATR 风险模型", "允许按波动分位调整，但必须版本化并保持最大 R 风险。"),
        ("cost_stress", "手续费、资金费、滑点与延迟压力", "统一比较毛边际和净边际。"),
        ("orderbook_quality", "盘口质量研究层", "仅保留为流动性和执行质量特征，不直接当方向信号。"),
        ("cross_asset_lead_lag", "BTC 与山寨币传导研究", "先做时间隔离的领先滞后检验，禁止凭叙事抢跑。"),
        ("ml_meta_label", "机器学习元标签与排序", "只做排序、过滤或否决，并使用时间隔离验证。"),
        ("multiple_testing", "多重试验与过拟合审计", "记录试验次数并使用 PBO/Deflated Sharpe 等校正。"),
    ]
    return [
        {
            "componentId": item[0],
            "name": item[1],
            "researchUse": item[2],
            "executionEligible": False,
        }
        for item in components
    ]


def _revival_split(
    inventory: list[dict[str, Any]], attributions: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    attribution_by_id = {item["strategyId"]: item for item in attributions}
    revival = []
    keep_archived = []
    for item in inventory:
        attribution = attribution_by_id[item["strategyId"]]
        metrics = item.get("metrics") or {}
        pf = _number(metrics.get("profitFactor"))
        avg_r = _number(metrics.get("averageNetR"))
        primary = attribution["primaryFailureType"]
        near_threshold = (pf is not None and 0.9 <= pf < 1.0) or (
            avg_r is not None and -0.05 <= avg_r <= 0
        )
        evidence_repair = primary in {"data_evidence_gap", "small_sample", "zero_trade_or_blocked"}
        prohibited = primary == "rejected_risk_design"
        row = {
            "strategyId": item["strategyId"],
            "strategyName": item.get("strategyName"),
            "strategyFamily": item.get("strategyFamily"),
            "primaryFailureType": primary,
            "profitFactor": pf,
            "averageNetR": avg_r,
            "currentExecutionEligibility": "none",
        }
        if not prohibited and (near_threshold or evidence_repair):
            row.update(
                {
                    "revivalEligible": True,
                    "revivalMode": "new_version_only",
                    "conditions": [
                        "先提出不同且可证伪的市场假设，禁止只微调旧阈值。",
                        "补齐逐笔、成本、锁定样本和市场状态证据。",
                        "新版本必须重新走时间隔离回测和不可变 Release。",
                    ],
                }
            )
            revival.append(row)
        else:
            row.update(
                {
                    "continueArchive": True,
                    "reason": (
                        "禁止的风险设计" if prohibited else "现有证据显示结构性弱势或离通过门槛过远"
                    ),
                }
            )
            keep_archived.append(row)
    return revival, keep_archived


def _prohibited_routes() -> list[dict[str, Any]]:
    return [
        {"routeId": "PROHIBIT_001", "route": "马丁格尔、逆势加仓或亏损后放大仓位"},
        {"routeId": "PROHIBIT_002", "route": "为了命中目标而随机移动或放宽止损"},
        {"routeId": "PROHIBIT_003", "route": "机器学习直接黑箱生成订单或动态杠杆"},
        {"routeId": "PROHIBIT_004", "route": "在锁定样本、Demo 或实盘结果上反向调参"},
        {"routeId": "PROHIBIT_005", "route": "达到自动优化上限后强制放行"},
        {"routeId": "PROHIBIT_006", "route": "堆叠多个同源指标制造虚假共振"},
        {"routeId": "PROHIBIT_007", "route": "把缺失证据、Mock 或摘要文案当成真实回测"},
    ]


def _slug(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_")
    return value[:140] or "unknown_strategy"


def _write_strategy_docs(
    root: Path, inventory: list[dict[str, Any]], attributions: list[dict[str, Any]]
) -> int:
    directory = root / STRATEGY_DOCS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    by_id = {item["strategyId"]: item for item in attributions}
    expected = set()
    for item in inventory:
        attribution = by_id[item["strategyId"]]
        path = directory / f"{_slug(item['strategyId'])}.md"
        expected.add(path.name)
        metrics = item.get("metrics") or {}
        lines = [
            f"# {item.get('strategyName') or item['strategyId']}",
            "",
            f"- 策略 ID：`{item['strategyId']}`",
            f"- 家族：`{item.get('strategyFamily') or 'unavailable'}`",
            f"- 周期：`{item.get('timeframe') or ', '.join(item.get('timeframes') or []) or 'unavailable'}`",
            f"- 当前状态：`{item.get('status')}`",
            f"- 证据等级：`{item.get('evidenceLevel')}`",
            f"- 逐笔证据：`{'有' if item.get('tradeEvidenceAvailable') else '无'}`",
            f"- 交易数：`{metrics.get('tradeCount') if metrics.get('tradeCount') is not None else 'unavailable'}`",
            f"- 利润因子：`{metrics.get('profitFactor') if metrics.get('profitFactor') is not None else 'unavailable'}`",
            f"- 平均净 R：`{metrics.get('averageNetR') if metrics.get('averageNetR') is not None else 'unavailable'}`",
            f"- 主要失败：**{attribution['primaryFailureLabelZh']}**",
            f"- 归因置信度：`{attribution['confidence']}`",
            "",
            "> 本页只记录历史研究证据，不授予回测通过、Demo 或实盘资格。",
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
    for path in directory.glob("*.md"):
        if path.name not in expected:
            path.unlink()
    return len(expected)


def _summary_markdown(
    generated_at: str,
    coverage: dict[str, Any],
    patterns: dict[str, Any],
    gaps: list[dict[str, Any]],
    revival: list[dict[str, Any]],
    archived: list[dict[str, Any]],
    trade_manifest: dict[str, Any],
) -> str:
    top_failures = sorted(
        patterns["primaryFailureCounts"].items(), key=lambda item: item[1], reverse=True
    )[:8]
    lines = [
        "# AlphaPilot 全量归档策略证据与失败归因报告",
        "",
        f"- 生成时间：`{generated_at}`",
        f"- 报告状态：`{coverage['status']}`",
        f"- 策略身份：**{coverage['strategyIdentityCount']}**",
        f"- 当前注册表归档版本：**{coverage['registryArchivedVersionCount']}**",
        f"- 旧 Freqtrade 身份：**{coverage['legacyFreqtradeIdentityCount']}**",
        f"- 证据产物：**{coverage['evidenceArtifactCount']}**",
        f"- 主证据逐笔交易：**{trade_manifest['tradeRowCount']}**",
        f"- 存在证据缺口的策略：**{len(gaps)}**",
        f"- 仅允许新版本复活研究：**{len(revival)}**",
        f"- 继续归档：**{len(archived)}**",
        "",
        "## 关键结论",
        "",
        "1. 归档库中自动优化父子版本高度相关，不能把版本数量当作独立策略数量。",
        "2. 注册表版本具备正式分割、成本压力、币种和市场状态指标，但普遍缺逐笔文件；旧 Freqtrade 证据具备逐笔交易，但与新版本身份不能全部可靠映射。",
        "3. 任何结构性负平均 R、利润因子低于 1 或成本压力后失效的策略都应继续归档，不能通过堆指标或微调阈值强行放行。",
        "4. 可复用的是数据门、信号漏斗、成本压力、市场状态和组合暴露等研究组件，不是失败策略本身。",
        "5. 本报告没有重跑回测、下载数据、修改参数或改变 Demo/实盘状态。",
        "",
        "## 主要失败分布",
        "",
    ]
    lines.extend(f"- `{name}`：{count}" for name, count in top_failures)
    lines.extend(
        [
            "",
            "## 逐笔数据说明",
            "",
            f"完整逐笔 JSONL 位于本地未跟踪目录：`{trade_manifest['fullTradeFile']}`。",
            "Git 中只保留清单、样本和聚合结果，避免提交大体积重复试验数据。",
            "",
            "## 策略生成核心准则",
            "",
        ]
    )
    lines.extend(f"- {item}" for item in STRATEGY_CORE_PRINCIPLES)
    lines.extend(
        [
            "",
            "## 边界",
            "",
            "这是历史研究与失败证据报告，不是交易建议，不授予任何执行资格。",
            "",
        ]
    )
    return "\n".join(lines)


def generate_full_archived_strategy_analysis(
    root: Path | str, generated_at: str | None = None
) -> dict[str, Any]:
    project_root = Path(root).resolve()
    timestamp = generated_at or _utc_now()
    inventory = build_full_inventory(project_root)
    evidence = build_evidence_index(project_root, inventory)
    _attach_evidence(inventory, evidence)
    freqtrade_metrics, trade_sample, trade_manifest = _trade_outputs(project_root, evidence)
    metrics = _metrics_matrix(inventory, freqtrade_metrics)
    attributions = [attribute_archived_failure(item) for item in inventory]
    patterns = build_cross_strategy_patterns(attributions)
    coverage = _coverage_audit(inventory, evidence, trade_manifest)
    gaps = _evidence_gaps(inventory)
    signal_funnel = _signal_funnel(inventory)
    negative_rules = _negative_rules(attributions)
    reusable = _reusable_components()
    revival, keep_archived = _revival_split(inventory, attributions)
    prohibited = _prohibited_routes()
    strategy_doc_count = _write_strategy_docs(project_root, inventory, attributions)

    report = {
        "reportId": REPORT_ID,
        "generatedAt": timestamp,
        "status": coverage["status"],
        "coverageAudit": coverage,
        "evidenceLevelDefinitions": EVIDENCE_LEVELS,
        "strategyDocumentCount": strategy_doc_count,
        "tradeManifest": trade_manifest,
        "primaryFailureCounts": patterns["primaryFailureCounts"],
        "safetyBoundary": dict(SAFETY_BOUNDARY),
        "methodologyLimits": [
            "归档版本和旧 Freqtrade 类之间只有在身份可证明时才合并。",
            "注册表聚合指标没有逐笔行时，不推导不存在的手续费、滑点或逐笔 R。",
            "逐笔库只选择每个旧策略类和周期的最新主产物，防止重复调参运行放大样本。",
            "归因只表示证据关联，不证明单一因果关系。",
        ],
    }

    _write_json(
        project_root / OUTPUTS["inventoryJson"],
        {"reportId": REPORT_ID, "generatedAt": timestamp, "strategies": inventory},
    )
    _write_csv(
        project_root / OUTPUTS["inventoryCsv"],
        [
            "strategyId", "strategyName", "strategyFamily", "status", "identitySource",
            "sourceType", "direction", "timeframe", "evidenceLevel",
            "evidenceCompleteness", "evidenceArtifactCount", "tradeEvidenceAvailable",
            "workflowRunId", "failureCategory", "failureSummary",
        ],
        inventory,
    )
    _write_json(project_root / OUTPUTS["coverageAudit"], coverage)
    _write_json(
        project_root / OUTPUTS["evidenceIndex"],
        {"generatedAt": timestamp, "summary": coverage, "artifacts": evidence},
    )
    _write_json(project_root / OUTPUTS["evidenceGaps"], gaps)
    _write_json(project_root / OUTPUTS["metricsJson"], metrics)
    _write_csv(
        project_root / OUTPUTS["metricsCsv"],
        [
            "strategyId", "strategyName", "strategyFamily", "status", "timeframe",
            "evidenceLevel", "tradeCount", "profitFactor", "averageNetR",
            "averageGrossR", "maximumDrawdownR", "maxDrawdownPct", "winRatePct",
            "totalReturnPct", "feesPaid", "fundingFees", "slippageCost",
            "longTradeCount", "shortTradeCount", "pairCount", "metricSource",
        ],
        metrics,
    )
    _write_csv(
        project_root / OUTPUTS["tradeSampleCsv"],
        [
            "tradeId", "strategyId", "strategyName", "timeframe", "artifactId", "pair",
            "direction", "openAt", "closeAt", "openRate", "closeRate", "profitRatio",
            "profitAbs", "netRApprox", "mfeRApprox", "maeRApprox", "feeCostEstimate",
            "fundingFees", "slippageCost", "enterTag", "exitReason", "marketRegime",
        ],
        trade_sample,
    )
    _write_json(project_root / OUTPUTS["signalFunnel"], signal_funnel)
    _write_json(project_root / OUTPUTS["attributionJson"], attributions)
    _write_csv(
        project_root / OUTPUTS["failureCsv"],
        [
            "strategyId", "strategyName", "strategyFamily", "timeframe", "status",
            "primaryFailureType", "primaryFailureLabelZh", "severity", "confidence",
            "confidenceScore", "causalityProven",
        ],
        attributions,
    )
    _write_json(project_root / OUTPUTS["patterns"], patterns)
    _write_json(project_root / OUTPUTS["negativeRules"], negative_rules)
    _write_json(project_root / OUTPUTS["reusableComponents"], reusable)
    _write_json(project_root / OUTPUTS["revivalCandidates"], revival)
    _write_json(project_root / OUTPUTS["continueArchive"], keep_archived)
    _write_json(project_root / OUTPUTS["prohibitedRoutes"], prohibited)
    (project_root / OUTPUTS["summary"]).write_text(
        _summary_markdown(
            timestamp, coverage, patterns, gaps, revival, keep_archived, trade_manifest
        ),
        encoding="utf-8",
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    report = generate_full_archived_strategy_analysis(args.root)
    print(
        json.dumps(
            {
                "reportId": report["reportId"],
                "status": report["status"],
                "strategyIdentityCount": report["coverageAudit"]["strategyIdentityCount"],
                "evidenceArtifactCount": report["coverageAudit"]["evidenceArtifactCount"],
                "tradeRowCount": report["tradeManifest"]["tradeRowCount"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
