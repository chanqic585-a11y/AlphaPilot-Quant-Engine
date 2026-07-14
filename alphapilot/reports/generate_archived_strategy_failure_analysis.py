"""Generate report-only attribution artifacts for archived failed strategies."""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from alphapilot.reports.archived_strategy_failure_analysis_schema import (
    METRIC_FIELDS,
    REPORT_ID,
    SAFETY_BOUNDARY,
)
from alphapilot.reports.archived_strategy_inventory import (
    build_archived_strategy_inventory,
)
from alphapilot.reports.signal_level_failure_attribution import (
    attribute_strategy_failure,
    build_cross_strategy_patterns,
)


OUTPUTS = {
    "inventory": Path("reports/archived_failed_strategy_inventory.json"),
    "metrics": Path("reports/archived_failed_strategy_metrics_matrix.json"),
    "attribution": Path("reports/archived_failed_strategy_failure_attribution.json"),
    "summary": Path("reports/archived_failed_strategy_failure_attribution_summary.md"),
    "negativeRules": Path("reports/archived_failed_strategy_negative_rules.json"),
    "reusableComponents": Path("reports/archived_failed_strategy_reusable_components.json"),
    "revivalCandidates": Path("reports/archived_failed_strategy_revival_candidates.json"),
    "metricsCsv": Path("reports/archived_failed_strategy_metrics_matrix.csv"),
    "attributionCsv": Path("reports/archived_failed_strategy_failure_attribution.csv"),
}


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _summary(inventory: list[dict[str, Any]], attributions: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "strategyCount": len(inventory),
        "familyCount": len({row.get("strategyFamily") for row in inventory}),
        "timeframeCount": len({row.get("timeframe") for row in inventory if row.get("timeframe")}),
        "evidenceLevelCounts": dict(
            sorted(Counter(str(row.get("evidenceLevel")) for row in inventory).items())
        ),
        "primaryFailureCounts": dict(
            sorted(Counter(row.get("primaryFailureType") for row in attributions).items())
        ),
        "dryRunApprovedCount": sum(bool(row.get("dryRunApproved")) for row in inventory),
        "liveTradingApprovedCount": sum(bool(row.get("liveTradingApproved")) for row in inventory),
        "completeMetricEvidenceCount": sum(bool(row.get("evidenceComplete")) for row in inventory),
        "missingMetricEvidenceCount": sum(not bool(row.get("evidenceComplete")) for row in inventory),
    }


def _negative_rules(
    inventory: list[dict[str, Any]], attributions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    primary_counts = Counter(row.get("primaryFailureType") for row in attributions)
    secondary_counts = Counter(
        item for row in attributions for item in row.get("secondaryFailureTypes") or []
    )
    return [
        {
            "ruleId": "AFS_NEG_001",
            "rule": "Do not promote a strategy whose available profit factor is below 1 or whose average net R is non-positive.",
            "evidenceStrategyCount": primary_counts.get("signal_edge_failure", 0),
            "scope": "promotion_gate",
        },
        {
            "ruleId": "AFS_NEG_002",
            "rule": "Do not rescue a structurally negative strategy family with small threshold changes alone.",
            "evidenceStrategyCount": primary_counts.get("signal_edge_failure", 0),
            "scope": "redesign_required",
        },
        {
            "ruleId": "AFS_NEG_003",
            "rule": "Always review fee and slippage stress before interpreting raw return.",
            "evidenceStrategyCount": secondary_counts.get("cost_amplification", 0),
            "scope": "cost_model",
        },
        {
            "ruleId": "AFS_NEG_004",
            "rule": "High trade count without positive per-trade edge is evidence of noise amplification, not diversification.",
            "evidenceStrategyCount": secondary_counts.get("overtrading", 0),
            "scope": "frequency",
        },
        {
            "ruleId": "AFS_NEG_005",
            "rule": "Never treat missing metrics as zero or as passing evidence.",
            "evidenceStrategyCount": sum(bool(row.get("missingEvidenceFields")) for row in inventory),
            "scope": "data_integrity",
        },
        {
            "ruleId": "AFS_NEG_006",
            "rule": "Signal edge and account-path risk must pass independently; one layer cannot hide failure in the other.",
            "evidenceStrategyCount": len(inventory),
            "scope": "attribution",
        },
        {
            "ruleId": "AFS_NEG_007",
            "rule": "Martingale and inverse-averaging designs remain rejected regardless of short-sample headline return.",
            "evidenceStrategyCount": primary_counts.get("rejected_risk_design", 0),
            "scope": "risk_boundary",
        },
        {
            "ruleId": "AFS_NEG_008",
            "rule": "Archived strategies are negative research assets and cannot become executable without a new version and fresh evidence.",
            "evidenceStrategyCount": len(inventory),
            "scope": "versioning",
        },
    ]


def _reusable_components(attributions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "componentId": "slippage_stress_review",
            "name": "Slippage and fee stress review",
            "researchUse": "Retain as a mandatory comparison layer for every future candidate.",
            "executionEligible": False,
        },
        {
            "componentId": "signal_audit_counters",
            "name": "Signal audit and skip-reason counters",
            "researchUse": "Retain instrumentation while redesigning entry logic.",
            "executionEligible": False,
        },
        {
            "componentId": "pair_exposure_diagnostics",
            "name": "Pair contribution and concentration diagnostics",
            "researchUse": "Retain for detecting single-pair dominance without hard-coding exclusions from one sample.",
            "executionEligible": False,
        },
        {
            "componentId": "regime_attribution_contract",
            "name": "Per-trade regime attribution contract",
            "researchUse": "Require before reviving directional candidates where market state may dominate results.",
            "executionEligible": False,
        },
        {
            "componentId": "immutable_failure_archive",
            "name": "Immutable failed-strategy archive",
            "researchUse": "Use archived evidence to prevent repeated hypotheses and silent metric resets.",
            "executionEligible": False,
        },
        {
            "componentId": "separate_signal_and_risk_layers",
            "name": "Separate signal-edge and account-risk review",
            "researchUse": (
                f"Applied to {len(attributions)} archived records so future candidates cannot pass on one layer alone."
            ),
            "executionEligible": False,
        },
    ]


def _revival_candidates(
    inventory: list[dict[str, Any]], attributions: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    attribution_by_id = {row.get("strategyId"): row for row in attributions}
    rows: list[dict[str, Any]] = []
    for item in inventory:
        attribution = attribution_by_id[item.get("strategyId")]
        primary = attribution.get("primaryFailureType")
        never_revive = primary == "rejected_risk_design"
        conditions = []
        if primary == "signal_edge_failure":
            conditions.extend(
                [
                    "Create a new strategy version with a materially different signal thesis.",
                    "Show positive average net R and profit factor above 1 on development evidence.",
                    "Pass cost stress, holdout, and walk-forward review without using locked data for selection.",
                ]
            )
        if "risk_model_failure" in attribution.get("secondaryFailureTypes", []):
            conditions.append("Demonstrate bounded drawdown and loss-sequence behavior under the new risk model.")
        if "data_evidence_gap" in attribution.get("secondaryFailureTypes", []) or primary == "data_evidence_gap":
            conditions.append("Fill the listed evidence gaps; missing values cannot be treated as passing evidence.")
        rows.append(
            {
                "strategyId": item.get("strategyId"),
                "strategyName": item.get("strategyName"),
                "revivalEligible": not never_revive,
                "revivalMode": "new_version_only" if not never_revive else "prohibited_risk_design",
                "conditions": conditions if not never_revive else [
                    "This risk design conflicts with the AlphaPilot risk boundary and must not be revived."
                ],
                "currentExecutionEligibility": "none",
            }
        )
    return rows


def build_archived_failure_analysis(root: Path | str, generated_at: str | None = None) -> dict[str, Any]:
    project_root = Path(root).resolve()
    inventory = build_archived_strategy_inventory(project_root)
    attributions = [attribute_strategy_failure(row) for row in inventory]
    return {
        "reportId": REPORT_ID,
        "generatedAt": generated_at or _utc_now(),
        "summary": _summary(inventory, attributions),
        "inventory": inventory,
        "attributions": attributions,
        "crossStrategyPatterns": build_cross_strategy_patterns(attributions),
        "negativeRules": _negative_rules(inventory, attributions),
        "reusableComponents": _reusable_components(attributions),
        "revivalCandidates": _revival_candidates(inventory, attributions),
        "safetyBoundary": dict(SAFETY_BOUNDARY),
        "methodologyLimits": [
            "Existing evidence is heterogeneous and not every strategy has trade-level rows.",
            "Missing values remain null and are never interpreted as zero or success.",
            "Failure labels are descriptive associations, not proof of a single causal mechanism.",
            "No archived record is promoted, modified, or executed by this report.",
        ],
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _metrics_rows(inventory: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in inventory:
        rows.append(
            {
                "strategyId": item.get("strategyId"),
                "strategyName": item.get("strategyName"),
                "strategyFamily": item.get("strategyFamily"),
                "timeframe": item.get("timeframe"),
                "direction": item.get("direction"),
                "status": item.get("status"),
                "evidenceLevel": item.get("evidenceLevel"),
                **(item.get("metrics") or {}),
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _summary_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    pattern_rows = "\n".join(
        f"| {row['failureType']} | {row['role']} | {row['strategyCount']} |"
        for row in report["crossStrategyPatterns"]
    )
    critical = [row for row in report["attributions"] if row.get("severity") == "critical"]
    critical_rows = "\n".join(
        f"- `{row['strategyId']}`: {row['primaryFailureType']}"
        for row in critical
    ) or "- 无"
    return f"""# 归档失败策略归因摘要

生成时间：`{report['generatedAt']}`

## 结论

- 共分析 **{summary['strategyCount']}** 条失败、拒绝或负向研究记录，来自 **{summary['familyCount']}** 个策略家族。
- Dry-run 获批：**{summary['dryRunApprovedCount']}**；实盘获批：**{summary['liveTradingApprovedCount']}**。
- 本报告只读取已有证据；没有修改策略、调参、启动回测、访问交易所或改变 Demo/实盘状态。
- 缺失指标保持 `null`。归因是证据分类，不代表证明了唯一因果关系。

## 跨策略模式

| 失败类型 | 角色 | 策略数 |
| --- | --- | ---: |
{pattern_rows}

## 严重失败记录

{critical_rows}

## 研究边界

1. 归档策略只能作为负向研究资产，不能直接恢复为可执行候选。
2. 结构性信号失败必须创建新版本和新假设，不能靠小幅调参覆盖。
3. 信号层与账户/风险层必须分别通过。
4. 任何复活候选都要重新经过成本压力、留出集和 Walk-forward 证据。

## 输出

- `reports/archived_failed_strategy_inventory.json`
- `reports/archived_failed_strategy_metrics_matrix.json`
- `reports/archived_failed_strategy_failure_attribution.json`
- `reports/archived_failed_strategy_negative_rules.json`
- `reports/archived_failed_strategy_reusable_components.json`
- `reports/archived_failed_strategy_revival_candidates.json`
- `reports/archived_failed_strategy_metrics_matrix.csv`
- `reports/archived_failed_strategy_failure_attribution.csv`
"""


def write_archived_failure_analysis(root: Path | str, generated_at: str | None = None) -> dict[str, Any]:
    project_root = Path(root).resolve()
    report = build_archived_failure_analysis(project_root, generated_at)
    inventory_payload = {
        "reportId": f"{REPORT_ID}_inventory",
        "generatedAt": report["generatedAt"],
        "summary": report["summary"],
        "records": report["inventory"],
        "safetyBoundary": report["safetyBoundary"],
    }
    metric_rows = _metrics_rows(report["inventory"])
    metrics_payload = {
        "reportId": f"{REPORT_ID}_metrics_matrix",
        "generatedAt": report["generatedAt"],
        "rows": metric_rows,
        "nullSemantics": "null means unavailable; zero is retained only when observed as zero",
    }
    attribution_payload = {
        "reportId": f"{REPORT_ID}_attribution",
        "generatedAt": report["generatedAt"],
        "summary": report["summary"],
        "rows": report["attributions"],
        "crossStrategyPatterns": report["crossStrategyPatterns"],
        "methodologyLimits": report["methodologyLimits"],
        "safetyBoundary": report["safetyBoundary"],
    }
    _write_json(project_root / OUTPUTS["inventory"], inventory_payload)
    _write_json(project_root / OUTPUTS["metrics"], metrics_payload)
    _write_json(project_root / OUTPUTS["attribution"], attribution_payload)
    _write_json(
        project_root / OUTPUTS["negativeRules"],
        {"reportId": f"{REPORT_ID}_negative_rules", "rules": report["negativeRules"]},
    )
    _write_json(
        project_root / OUTPUTS["reusableComponents"],
        {"reportId": f"{REPORT_ID}_reusable_components", "components": report["reusableComponents"]},
    )
    _write_json(
        project_root / OUTPUTS["revivalCandidates"],
        {"reportId": f"{REPORT_ID}_revival_candidates", "records": report["revivalCandidates"]},
    )
    (project_root / OUTPUTS["summary"]).write_text(
        _summary_markdown(report), encoding="utf-8"
    )
    metric_fields = [
        "strategyId",
        "strategyName",
        "strategyFamily",
        "timeframe",
        "direction",
        "status",
        "evidenceLevel",
        *METRIC_FIELDS,
    ]
    _write_csv(project_root / OUTPUTS["metricsCsv"], metric_rows, metric_fields)
    attribution_rows = [
        {
            **row,
            "secondaryFailureTypes": ";".join(row.get("secondaryFailureTypes") or []),
            "signalLayerAssessment": (row.get("signalLayer") or {}).get("assessment"),
            "accountRiskLayerAssessment": (row.get("accountRiskLayer") or {}).get("assessment"),
            "missingEvidenceFields": ";".join(row.get("missingEvidenceFields") or []),
        }
        for row in report["attributions"]
    ]
    _write_csv(
        project_root / OUTPUTS["attributionCsv"],
        attribution_rows,
        [
            "strategyId",
            "strategyName",
            "strategyFamily",
            "timeframe",
            "direction",
            "primaryFailureType",
            "secondaryFailureTypes",
            "severity",
            "signalLayerAssessment",
            "accountRiskLayerAssessment",
            "evidenceLevel",
            "missingEvidenceFields",
            "causalityProven",
        ],
    )
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--generated-at", default=None)
    args = parser.parse_args()
    report = write_archived_failure_analysis(args.root, args.generated_at)
    print(
        json.dumps(
            {
                "status": "completed",
                "reportId": report["reportId"],
                "strategyCount": report["summary"]["strategyCount"],
                "outputs": {key: str(value) for key, value in OUTPUTS.items()},
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
