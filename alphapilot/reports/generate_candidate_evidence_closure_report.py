"""Generate preregistered candidate evidence-closure research artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import io
import json
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.validation.preregistration import (
    build_preregistration,
    verify_preregistration,
)
from alphapilot.validation.candidate_validator import (
    benjamini_hochberg,
    validate_candidate,
)
from alphapilot.validation.checkpoint import load_checkpoint, save_checkpoint
from alphapilot.validation.evidence_loader import load_candidate_evidence
from alphapilot.validation.monte_carlo import run_monte_carlo
from alphapilot.validation.portfolio_risk import analyze_portfolio_risk
from alphapilot.validation.registry_loader import load_candidate_preregistration_records

from .candidate_evidence_closure_schema import PREREGISTRATION_OUTPUTS, VALIDATION_OUTPUTS


GENERATED_EVIDENCE_OUTPUTS = {
    "tradeRows": "reports/generated/candidate_validation_trade_rows.jsonl",
    "monteCarloSamples": (
        "reports/generated/candidate_validation_monte_carlo_samples.jsonl"
    ),
}

PREREGISTRATION_PROMPT_ALIASES = {
    "reports/candidate_validation_queue.json": (
        "reports/candidate_evidence_closure_candidate_queue.json"
    ),
    "reports/candidate_deduplication_report.json": (
        "reports/candidate_evidence_closure_deduplication.json"
    ),
}


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_jsonl_atomic(path: Path, rows: Any) -> dict[str, Any]:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    count = 0
    sample: list[dict[str, Any]] = []
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            value = dict(row)
            handle.write(
                json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            )
            handle.write("\n")
            count += 1
            if len(sample) < 3:
                sample.append(value)
    temporary.replace(path)
    return {
        "path": path.as_posix(),
        "rowCount": count,
        "sha256": _sha256_file(path),
        "sample": sample,
        "trackedInGit": False,
    }


def write_preregistration_prompt_aliases(root: Path) -> None:
    """Preserve legacy paths while also satisfying the registered prompt names."""

    for source_relative, destination_relative in PREREGISTRATION_PROMPT_ALIASES.items():
        source = root / source_relative
        if not source.is_file():
            raise FileNotFoundError(f"missing locked preregistration artifact: {source}")
        payload = json.loads(source.read_text(encoding="utf-8"))
        write_json_atomic(root / destination_relative, payload)


def write_generated_evidence_files(
    root: Path,
    *,
    preregistration: dict[str, Any],
    candidate_trades: dict[str, list[dict[str, Any]]],
    candidate_results: list[dict[str, Any]],
) -> dict[str, Any]:
    """Write deterministic large evidence files and return tracked metadata."""

    preregistration_hash = str(preregistration["preRegistrationHash"])
    candidates = list(preregistration["candidates"])

    def trade_rows() -> Any:
        for candidate in candidates:
            strategy_version_id = str(candidate["strategyVersionId"])
            rows = sorted(
                candidate_trades.get(strategy_version_id, []),
                key=lambda row: (
                    int(row.get("entryTimestampMs") or 0),
                    int(row.get("exitTimestampMs") or 0),
                    str(row.get("instrumentId") or ""),
                ),
            )
            for row_index, row in enumerate(rows):
                yield {
                    **dict(row),
                    "preRegistrationHash": preregistration_hash,
                    "strategyVersionId": strategy_version_id,
                    "displayLabelZh": candidate.get("displayLabelZh"),
                    "rowIndex": row_index,
                }

    results_by_id = {
        str(result["strategyVersionId"]): result for result in candidate_results
    }

    def monte_carlo_rows() -> Any:
        base_seed = int(preregistration["seedRegistry"]["monteCarlo"])
        draws = int(preregistration["resourceLimits"]["monteCarloDraws"])
        for candidate_index, candidate in enumerate(candidates):
            strategy_version_id = str(candidate["strategyVersionId"])
            result = results_by_id[strategy_version_id]
            if not result.get("monteCarlo"):
                continue
            net_r_values = [
                float(row.get("netR") or 0.0)
                for row in candidate_trades.get(strategy_version_id, [])
            ]
            for model_offset, (model_id, model) in enumerate(
                preregistration["riskModels"].items()
            ):
                if model.get("role") == "signal_normalization_only":
                    continue
                if model_id not in result["monteCarlo"]:
                    continue
                seed = base_seed + candidate_index + model_offset
                raw = run_monte_carlo(
                    net_r_values,
                    risk_per_trade_pct=float(model["riskPerTradePct"]),
                    draws=draws,
                    seed=seed,
                    research_stop_pct=float(
                        model.get("drawdownResearchStopPct", 100.0)
                    ),
                    include_sample_rows=True,
                )
                for sample_row in raw.get("sampleRows", []):
                    yield {
                        **sample_row,
                        "preRegistrationHash": preregistration_hash,
                        "strategyVersionId": strategy_version_id,
                        "riskModelId": model_id,
                        "seed": seed,
                    }

    manifest: dict[str, Any] = {}
    for key, rows in (
        ("tradeRows", trade_rows()),
        ("monteCarloSamples", monte_carlo_rows()),
    ):
        relative = GENERATED_EVIDENCE_OUTPUTS[key]
        metadata = _write_jsonl_atomic(root / relative, rows)
        metadata["path"] = relative
        manifest[key] = metadata
    return manifest


def _git_head(root: Path) -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None


def environment_fingerprint(root: Path, source_root: Path) -> dict[str, Any]:
    packages: dict[str, str | None] = {}
    for name in ("numpy", "pandas", "pyarrow", "scipy"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    registry = source_root / "data" / "evolution_registry.sqlite"
    attribution = source_root / "reports" / "full_archived_strategy_failure_attribution.json"
    return {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "executable": str(Path(sys.executable).resolve()),
        "packages": packages,
        "gitHead": _git_head(root),
        "sourceGitHead": _git_head(source_root),
        "registrySha256": _sha256_file(registry) if registry.is_file() else None,
        "failureAttributionSha256": (
            _sha256_file(attribution) if attribution.is_file() else None
        ),
    }


def _markdown(preregistration: dict[str, Any], deduplication: dict[str, Any]) -> str:
    lines = [
        "# 候选证据闭环锁定验证预注册",
        "",
        f"- 预注册哈希：`{preregistration['preRegistrationHash']}`",
        f"- 候选版本：{deduplication['candidate_version_count']}",
        f"- 去重后家族：{deduplication['canonical_representative_count']}",
        "- 主验收风险模型：模型一（单笔账户风险 0.25%）",
        "- 模型二、模型三：仅敏感性观察，不能挽救主模型失败",
        "- 研究边界：不恢复归档版本，不授予执行资格，不创建订单",
        "",
        "## 候选队列",
        "",
    ]
    for candidate in preregistration["candidates"]:
        lines.append(
            f"- {candidate['tier']}：{candidate['displayLabelZh']} "
            f"(`{candidate['strategyVersionId']}`)"
        )
    lines.extend(
        [
            "",
            "## 锁定规则",
            "",
            "- 信号定义、方向、周期、阈值、成本模型、风险模型和门槛在查看结果前冻结。",
            "- 1D 需要至少 365 天且有效交易数不少于 50；30–49 笔仅探索。",
            "- 缺少无污染锁定样本或 point-in-time 宇宙证据时只能诊断，不能通过。",
            "- Bootstrap 和 Monte Carlo 正式运行均为 5,000 次，使用登记种子。",
            "- NoTrade 与简单方向基线只用于比较，不能授予通过。",
            "",
        ]
    )
    return "\n".join(lines)


def generate_preregistration(root: Path, source_root: Path) -> dict[str, Any]:
    locked_path = root / PREREGISTRATION_OUTPUTS["preregistrationJson"]
    if locked_path.is_file():
        locked = json.loads(locked_path.read_text(encoding="utf-8"))
        if not isinstance(locked, dict):
            raise ValueError("locked preregistration must be a JSON object")
        write_preregistration_prompt_aliases(root)
        return verify_preregistration(locked)

    attribution_path = (
        source_root / "reports" / "full_archived_strategy_failure_attribution.json"
    )
    registry_path = source_root / "data" / "evolution_registry.sqlite"
    attributions = json.loads(attribution_path.read_text(encoding="utf-8"))
    if not isinstance(attributions, list):
        raise ValueError("failure attribution report must be a JSON array")
    candidates, deduplication, diagnostics = load_candidate_preregistration_records(
        failure_attributions=attributions,
        registry_path=registry_path,
    )
    preregistration = build_preregistration(
        candidates=candidates,
        environment_fingerprint=environment_fingerprint(root, source_root),
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    queue = {
        "schemaVersion": "candidate_validation_queue_v1",
        "candidateVersionCount": deduplication.candidate_version_count,
        "candidateFamilyCount": deduplication.candidate_family_count,
        "canonicalRepresentativeCount": deduplication.canonical_representative_count,
        "candidates": candidates,
        "diagnostics": diagnostics,
    }
    deduplication_payload = asdict(deduplication)
    for key, relative in PREREGISTRATION_OUTPUTS.items():
        path = root / relative
        if key == "queue":
            write_json_atomic(path, queue)
        elif key == "deduplication":
            write_json_atomic(path, deduplication_payload)
        elif key == "preregistrationJson":
            write_json_atomic(path, preregistration)
        elif key == "preregistrationMarkdown":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                _markdown(preregistration, deduplication_payload), encoding="utf-8"
            )
    write_preregistration_prompt_aliases(root)
    return preregistration


def _compact_evidence(evidence: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "strategyVersionId",
        "workflowRunId",
        "evaluationBindingId",
        "strategyDataContractId",
        "dataSnapshotId",
        "dataSnapshotHash",
        "dataStartTime",
        "dataEndTime",
        "pointInTimeCutoff",
        "reportPath",
        "reportSha256",
        "reportResultHash",
        "validationManifestHash",
        "manifestHashes",
        "signalReproducible",
        "signalUnreproducibleReason",
        "historicalPointInTimeUniverse",
        "survivorshipAuditStatus",
        "lockedOrHoldoutUsedForSelection",
        "selectionMethod",
        "potentialLeakageFlags",
        "cleanLockedSampleAvailable",
        "lockedSampleStatus",
        "diagnosticReplayOnly",
        "pointInTimeUniverseAudit",
        "sourceFileCount",
        "contractContentHash",
    )
    return {key: evidence.get(key) for key in keys}


def _candidate_section(
    candidate_results: list[dict[str, Any]], key: str
) -> list[dict[str, Any]]:
    return [
        {
            "strategyVersionId": result["strategyVersionId"],
            "displayLabelZh": result.get("displayLabelZh"),
            "tier": result.get("tier"),
            "timeframe": result.get("timeframe"),
            "decision": result.get("decision"),
            key: result.get(key),
        }
        for result in candidate_results
    ]


def _leaderboard_csv(candidate_results: list[dict[str, Any]]) -> str:
    buffer = io.StringIO(newline="")
    fields = [
        "tier",
        "strategyVersionId",
        "displayLabelZh",
        "timeframe",
        "status",
        "displayStatusZh",
        "hardPass",
        "tradeCount",
        "profitFactor",
        "averageNetR",
        "lockedTradeCount",
        "lockedProfitFactor",
        "historicalMaximumDrawdownPct",
        "monteCarloP95MaximumDrawdownPct",
        "executionEligible",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for result in candidate_results:
        signal = (result.get("signalLayer") or {}).get("summary") or {}
        locked = (result.get("lockedSample") or {}).get("summary") or {}
        primary_id = next(
            (
                model_id
                for model_id, payload in (result.get("riskModels") or {}).items()
                if payload is not None
            ),
            None,
        )
        risk = (result.get("riskModels") or {}).get(primary_id or "", {})
        monte_carlo = (result.get("monteCarlo") or {}).get(primary_id or "", {})
        decision = result["decision"]
        writer.writerow(
            {
                "tier": result.get("tier"),
                "strategyVersionId": result["strategyVersionId"],
                "displayLabelZh": result.get("displayLabelZh"),
                "timeframe": result.get("timeframe"),
                "status": decision.get("status"),
                "displayStatusZh": decision.get("displayStatusZh"),
                "hardPass": decision.get("hardPass"),
                "tradeCount": signal.get("tradeCount"),
                "profitFactor": signal.get("profitFactor"),
                "averageNetR": signal.get("averageNetR"),
                "lockedTradeCount": locked.get("tradeCount"),
                "lockedProfitFactor": locked.get("profitFactor"),
                "historicalMaximumDrawdownPct": risk.get("maximumDrawdownPct"),
                "monteCarloP95MaximumDrawdownPct": (
                    monte_carlo.get("maximumDrawdownPct") or {}
                ).get("p95"),
                "executionEligible": result["executionEligibility"]["executionEligible"],
            }
        )
    return buffer.getvalue()


def _summary_markdown(
    preregistration: dict[str, Any], candidate_results: list[dict[str, Any]]
) -> str:
    passed = [result for result in candidate_results if result["decision"]["hardPass"]]
    lines = [
        "# 候选证据闭环锁定验证总结",
        "",
        f"- 预注册哈希：`{preregistration['preRegistrationHash']}`",
        f"- 去重后候选家族：{len(candidate_results)}",
        f"- 硬通过家族：{len(passed)}",
        "- 主风险模型：模型一，单笔账户风险 0.25%",
        "- 模型二、三：仅敏感性分析，不能挽救主模型失败",
        "- 执行边界：本轮不恢复归档版本，不进入 Dry-run、Demo 或实盘",
        "",
        "## 总结",
        "",
    ]
    if passed:
        lines.append(f"{len(passed)} 个家族完成证据闭环，可另行提出新研究版本。")
    else:
        lines.append(
            "无候选通过。现有归档证据的锁定区已被观察，且缺少 point-in-time 宇宙证据，"
            "因此只能作为诊断回放，不能转化为新的样本外通过。"
        )
    lines.extend(["", "## 候选结论", ""])
    for result in candidate_results:
        lines.append(
            f"- {result['displayLabelZh']}：{result['decision']['displayStatusZh']}；继续归档。"
        )
    lines.extend(
        [
            "",
            "## 下一步",
            "",
            "停止恢复旧归档版本。下一轮只研究与既有失败家族独立、可证伪的新市场假设，",
            "并从一开始保留未查看的 point-in-time 锁定样本。",
            "",
        ]
    )
    return "\n".join(lines)


def build_validation_artifacts(
    *,
    preregistration: dict[str, Any],
    candidate_results: list[dict[str, Any]],
    evidence_records: dict[str, dict[str, Any]],
    portfolio_risk: dict[str, Any],
    generated_evidence_files: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build every tracked validation artifact from completed candidate rows."""

    passed = [result for result in candidate_results if result["decision"]["hardPass"]]
    status_counts: dict[str, int] = {}
    for result in candidate_results:
        status = str(result["decision"]["status"])
        status_counts[status] = status_counts.get(status, 0) + 1
    recommendations = [
        {
            "sourceArchivedStrategyVersionId": result["strategyVersionId"],
            "strategyFamily": result.get("strategyFamily"),
            "displayLabelZh": result.get("displayLabelZh"),
            "action": "建议创建新的研究版本",
            "archivedVersionRestored": False,
            "executionEligibilityGranted": False,
        }
        for result in passed[: int(preregistration.get("recommendationLimit", 2))]
    ]
    closure = {
        "schemaVersion": "candidate_evidence_closure_v1",
        "generatedAt": preregistration["createdAt"],
        "preRegistrationHash": preregistration["preRegistrationHash"],
        "status": "completed",
        "summary": {
            "candidateCount": len(candidate_results),
            "passedCount": len(passed),
            "continueArchiveCount": len(candidate_results) - len(passed),
            "statusCounts": dict(sorted(status_counts.items())),
        },
        "candidateResults": candidate_results,
        "safetyBoundary": {
            "researchOnly": True,
            "archivedVersionsRestored": False,
            "executionEligibilityGranted": False,
            "dryRunExecuted": False,
            "demoOrderCreated": False,
            "liveOrderCreated": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyStored": False,
        },
    }
    base = {
        "schemaVersion": "candidate_validation_layer_v1",
        "generatedAt": preregistration["createdAt"],
        "preRegistrationHash": preregistration["preRegistrationHash"],
    }
    artifacts: dict[str, Any] = {
        "dataManifest": {
            **base,
            "environmentFingerprint": preregistration.get("environmentFingerprint"),
            "candidateEvidence": [
                evidence_records[key] for key in sorted(evidence_records)
            ],
            "pointInTimeUniverseAvailableForAll": all(
                bool(record.get("historicalPointInTimeUniverse"))
                for record in evidence_records.values()
            ),
            "generatedEvidenceFiles": generated_evidence_files or {},
        },
        "costModels": {
            **base,
            "frozenCostModel": preregistration.get("costModel"),
            "candidates": _candidate_section(candidate_results, "costStress"),
        },
        "riskModels": {
            **base,
            "primaryRiskModelId": preregistration.get("primaryRiskModelId"),
            "sensitivityRiskModelIds": preregistration.get("sensitivityRiskModelIds"),
            "frozenRiskModels": preregistration.get("riskModels"),
        },
        "signalLayer": {**base, "candidates": _candidate_section(candidate_results, "signalLayer")},
        "lockedSample": {**base, "candidates": _candidate_section(candidate_results, "lockedSample")},
        "walkForward": {**base, "candidates": _candidate_section(candidate_results, "walkForward")},
        "costStress": {**base, "candidates": _candidate_section(candidate_results, "costStress")},
        "riskModel": {**base, "candidates": _candidate_section(candidate_results, "riskModels")},
        "monteCarlo": {**base, "candidates": _candidate_section(candidate_results, "monteCarlo")},
        "portfolioRisk": {**base, "portfolioRisk": portfolio_risk},
        "closure": closure,
        "summary": _summary_markdown(preregistration, candidate_results),
        "leaderboard": _leaderboard_csv(candidate_results),
        "continueArchive": {
            **base,
            "rows": [
                {
                    "strategyVersionId": result["strategyVersionId"],
                    "displayLabelZh": result.get("displayLabelZh"),
                    "decision": result["decision"],
                    "action": (
                        "recommend_new_research_version"
                        if result["decision"]["hardPass"]
                        else "continue_archive"
                    ),
                    "archivedVersionRestored": False,
                }
                for result in candidate_results
            ],
        },
        "recommendations": {
            **base,
            "recommendationCount": len(recommendations),
            "recommendations": recommendations,
        },
    }
    return artifacts


def write_validation_artifacts(root: Path, artifacts: dict[str, Any]) -> None:
    """Write the complete registered output set using deterministic encoding."""

    for key, relative in VALIDATION_OUTPUTS.items():
        path = root / relative
        value = artifacts[key]
        if isinstance(value, str):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(value, encoding="utf-8")
        else:
            write_json_atomic(path, value)


def run_validation(root: Path, source_root: Path) -> dict[str, Any]:
    """Validate one candidate at a time with preregistration-bound resume."""

    preregistration_path = root / PREREGISTRATION_OUTPUTS["preregistrationJson"]
    preregistration = verify_preregistration(
        json.loads(preregistration_path.read_text(encoding="utf-8"))
    )
    preregistration_hash = preregistration["preRegistrationHash"]
    checkpoint_path = root / "reports/generated/candidate_evidence_closure_checkpoint.json"
    checkpoint = load_checkpoint(
        checkpoint_path, preregistration_hash=preregistration_hash
    )
    completed = dict(checkpoint["completed"])
    registry_path = source_root / "data/evolution_registry.sqlite"
    evidence_records: dict[str, dict[str, Any]] = {}
    candidate_trades: dict[str, list[dict[str, Any]]] = {}
    for index, candidate in enumerate(preregistration["candidates"]):
        strategy_version_id = str(candidate["strategyVersionId"])
        evidence = load_candidate_evidence(registry_path, candidate)
        evidence_records[strategy_version_id] = _compact_evidence(evidence)
        candidate_trades[strategy_version_id] = [
            dict(row) for row in evidence.get("trades") or []
        ]
        if strategy_version_id not in completed:
            result = validate_candidate(
                candidate,
                evidence,
                preregistration,
                candidate_index=index,
            )
            completed[strategy_version_id] = {
                "result": result,
                "evidenceManifest": evidence_records[strategy_version_id],
            }
            save_checkpoint(
                checkpoint_path,
                preregistration_hash=preregistration_hash,
                completed=completed,
            )

    ordered_results = [
        dict(completed[str(candidate["strategyVersionId"])]["result"])
        for candidate in preregistration["candidates"]
    ]
    raw_pvalues = {
        result["strategyVersionId"]: float(
            result["signalLayer"]["multipleTestingRawP"]
        )
        for result in ordered_results
        if result.get("signalLayer")
        and result["signalLayer"].get("multipleTestingRawP") is not None
    }
    adjusted = benjamini_hochberg(raw_pvalues)
    for result in ordered_results:
        if result.get("signalLayer"):
            result["signalLayer"]["multipleTestingAdjustedP"] = adjusted.get(
                result["strategyVersionId"]
            )
    portfolio_risk = analyze_portfolio_risk(candidate_trades)
    generated_evidence_files = write_generated_evidence_files(
        root,
        preregistration=preregistration,
        candidate_trades=candidate_trades,
        candidate_results=ordered_results,
    )
    artifacts = build_validation_artifacts(
        preregistration=preregistration,
        candidate_results=ordered_results,
        evidence_records=evidence_records,
        portfolio_risk=portfolio_risk,
        generated_evidence_files=generated_evidence_files,
    )
    write_validation_artifacts(root, artifacts)
    return artifacts["closure"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--phase", choices=("preregister", "validate", "all"), default="all"
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--source-root", type=Path, default=None)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    root = args.root.resolve()
    source_root = (args.source_root or root).resolve()
    preregistration = generate_preregistration(root, source_root)
    if args.phase in {"validate", "all"}:
        report = run_validation(root, source_root)
        print(
            json.dumps(
                {
                    "status": report["status"],
                    "candidateCount": report["summary"]["candidateCount"],
                    "passedCount": report["summary"]["passedCount"],
                    "preRegistrationHash": report["preRegistrationHash"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    print(
        json.dumps(
            {
                "status": "preregistered",
                "candidateCount": len(preregistration["candidates"]),
                "preRegistrationHash": preregistration["preRegistrationHash"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
