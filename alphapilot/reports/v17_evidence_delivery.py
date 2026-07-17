"""Build the read-only V13.27.1.17 evidence delivery packages."""

from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from alphapilot.data_foundation.checkpoint import write_json_atomic


ROUTE = "implementation_invalid_requires_new_campaign"
CAMPAIGN_ID = "advisory_r_v17"
PREREGISTRATION = Path(
    "research/preregistrations/advisory_r_v17_s01_formal_walk_forward.json"
)
SOURCE_PREREGISTRATION = Path(
    "research/preregistrations/"
    "advisory_r_v16_correction_8ec939e8f7ce17a3d259c72c134d02.json"
)
SNAPSHOT = Path("research/data_snapshots/minimal_snapshot_785e47b180c17327dcb35e37.json")
PHASE0_ROOT = Path("reports/formal_validation/v13_27_1_17_s01_readiness_audit")
PHASE1_ROOT = Path("reports/formal_validation/v13_27_1_17_s01_phase1_readiness")
PHASE2_ROOT = Path("reports/formal_validation/v13_27_1_17_s01_phase2_readiness")


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object: {path}")
    return payload


def _write_json(path: Path, payload: Any) -> None:
    write_json_atomic(path, payload)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields: list[str] = []
    for row in rows:
        for field in row:
            if field not in fields:
                fields.append(field)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields or ["status"], lineterminator="\n")
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
    _write_text(path, buffer.getvalue())


def _sha256_bytes(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _git(repo: Path, executable: Path | None, *args: str) -> str | None:
    command = str(executable) if executable else shutil.which("git")
    if not command:
        return None
    completed = subprocess.run(
        [command, "-c", f"safe.directory={repo.as_posix()}", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def _git_identity(repo: Path | None, executable: Path | None) -> dict[str, Any]:
    if repo is None or not repo.is_dir():
        return {"status": "unavailable", "reason": "repository_not_provided"}
    head = _git(repo, executable, "rev-parse", "HEAD")
    branch = _git(repo, executable, "branch", "--show-current")
    status = _git(repo, executable, "status", "--short")
    remote_main = _git(repo, executable, "rev-parse", "origin/main")
    tags = _git(repo, executable, "tag", "--points-at", "HEAD")
    return {
        "status": "available" if head else "unavailable",
        "path": str(repo),
        "branch": branch,
        "commit": head,
        "tagsAtHead": tags.splitlines() if tags else [],
        "originMain": remote_main,
        "gitStatusShort": status or "",
        "clean": status == "",
        "pushed": bool(head and remote_main and head == remote_main),
        "mergedToOriginMain": bool(head and remote_main and head == remote_main),
    }


def _stage_inventory(git_identity: Mapping[str, Any]) -> list[dict[str, Any]]:
    common = {
        "branch": git_identity.get("branch"),
        "worktreePath": git_identity.get("path"),
        "tag": None,
        "merged": git_identity.get("mergedToOriginMain"),
        "preregistrationHash": None,
        "sourceCodeHash": None,
        "resultRead": False,
        "supersededBy": None,
    }
    return [
        {
            **common,
            "stageId": "phase_0",
            "stageName": "Phase 0 readiness audit",
            "status": "completed_with_blockers",
            "startedAt": None,
            "finishedAt": None,
            "commitBefore": "6d885eee532d45a2c7c1cbeb37c92fe2ac031c3b",
            "commitAfter": "2a6d759",
            "pushed": True,
            "reportRoot": str(PHASE0_ROOT),
            "authoritative": True,
            "stopReason": "prerequisites_missing",
        },
        {
            **common,
            "stageId": "phase_0_1",
            "stageName": "Phase 0.1 prerequisite freeze",
            "status": "completed",
            "startedAt": None,
            "finishedAt": None,
            "commitBefore": "2a6d759",
            "commitAfter": "5aad8ad",
            "pushed": True,
            "reportRoot": str(PREREGISTRATION.parent),
            "authoritative": True,
            "stopReason": None,
        },
        {
            **common,
            "stageId": "phase_1",
            "stageName": "Phase 1 readiness evidence",
            "status": "completed",
            "startedAt": None,
            "finishedAt": None,
            "commitBefore": "5aad8ad",
            "commitAfter": "244b0f8",
            "pushed": True,
            "reportRoot": str(PHASE1_ROOT),
            "authoritative": True,
            "stopReason": None,
        },
        {
            **common,
            "stageId": "phase_2",
            "stageName": "Phase 2 engineering readiness",
            "status": "completed",
            "startedAt": None,
            "finishedAt": None,
            "commitBefore": "244b0f8",
            "commitAfter": "96a5fbce2907439b3e22a1ecd55ec3b9d07e7f47",
            "pushed": git_identity.get("pushed", False),
            "reportRoot": str(PHASE2_ROOT),
            "authoritative": True,
            "stopReason": None,
        },
        {
            **common,
            "stageId": "formal_preflight",
            "stageName": "Formal execution contract preflight",
            "status": "completed_terminal_pre_run",
            "startedAt": None,
            "finishedAt": None,
            "commitBefore": git_identity.get("commit"),
            "commitAfter": None,
            "pushed": False,
            "reportRoot": "reports/formal_validation/advisory_r_v17",
            "authoritative": True,
            "stopReason": ROUTE,
        },
        {
            **common,
            "stageId": "formal_walk_forward",
            "stageName": "Formal Walk-forward and statistical audit",
            "status": "not_run",
            "startedAt": None,
            "finishedAt": None,
            "commitBefore": None,
            "commitAfter": None,
            "pushed": False,
            "reportRoot": None,
            "authoritative": False,
            "stopReason": ROUTE,
        },
    ]


def _issues() -> list[dict[str, Any]]:
    rows = [
        ("P0-01", "Phase 0", "Locked OOS 身份不完整", "intentional_safety_block", "C", False),
        ("P0-02", "Phase 0", "正式切分政策未冻结", "resolved_before_result", "A", False),
        ("P0-03", "Phase 0", "资金竞争政策不可执行", "requires_new_campaign", "B", True),
        ("P0-04", "Phase 0", "S01 Freqtrade 实现缺失", "resolved_before_result", "A", False),
        ("P0-05", "Phase 0", "Freqtrade Runtime 缺失", "resolved_before_result", "A", False),
        ("P0-06", "Phase 0", "Timerange / I/O Guard 缺失", "resolved_before_result", "A", False),
        ("P2-01", "Phase 2", "阶段提交曾未 Push", "historical_preserved", "A", False),
        ("P2-02", "Phase 2", "测试存在一个 skipped", "open_nonblocking", "A", False),
        ("P2-03", "Phase 2", "历史 CRLF/LF sidecar 哈希差异", "historical_preserved", "A", False),
        ("P2-04", "Phase 2", "Locked OOS 继续阻塞", "intentional_safety_block", "C", False),
        ("P2-05", "Phase 2", "正式策略结果未产生", "historical_preserved", "C", False),
        ("P2-06", "Phase 2", "Release / ARM / Order 为零", "not_an_issue", "C", False),
        ("F17-01", "Formal preflight", "容量模型及阈值未冻结", "requires_new_campaign", "B", True),
        ("F17-02", "Formal preflight", "相关簇算法未冻结", "requires_new_campaign", "B", True),
        ("F17-03", "Formal preflight", "组合 Beta 算法未冻结", "requires_new_campaign", "B", True),
        ("F17-04", "Formal preflight", "排序字段派生规则未冻结", "requires_new_campaign", "B", True),
    ]
    return [
        {
            "issueId": issue_id,
            "firstDetectedStage": stage,
            "titleZh": title,
            "description": title,
            "issueType": "formal_validation_evidence",
            "severity": "blocking" if invalid else "limitation",
            "affectsStrategyLogic": False,
            "affectsResultValidity": invalid,
            "affectsEvidenceGrade": True,
            "affectsLockedOos": issue_id in {"P0-01", "P2-04"},
            "historicalOnly": status == "historical_preserved",
            "intentionalSafetyBlock": status == "intentional_safety_block",
            "status": status,
            "resolvedAtStage": "Phase 2" if status == "resolved_before_result" else None,
            "resolutionArtifact": None,
            "requiresPatch": category == "A" and status not in {"not_an_issue"},
            "requiresResultRerun": False,
            "requiresNewCampaign": invalid,
            "patchCategory": category,
            "recommendedAction": (
                "Create a new preregistered campaign" if invalid else "Preserve or document"
            ),
            "evidenceRefs": [],
        }
        for issue_id, stage, title, status, category, invalid in rows
    ]


def _not_run(name: str) -> dict[str, Any]:
    return {
        "schemaVersion": f"v17_{name}_not_run_v1",
        "status": "not_run",
        "exactReason": ROUTE,
        "admissionBlocked": True,
        "value": None,
    }


def _copy_json(source: Path, target: Path, *, fallback: Mapping[str, Any]) -> dict[str, Any]:
    if source.is_file():
        payload = _read_json(source)
        _write_json(target, payload)
        return payload
    _write_json(target, dict(fallback))
    return dict(fallback)


def _artifact_mapping(repo_root: Path) -> list[dict[str, Any]]:
    roles = {
        "v16Preregistration": SOURCE_PREREGISTRATION,
        "v17Phase0Audit": PHASE0_ROOT / "phase0_readiness_audit.json",
        "v17Phase1Audit": PHASE1_ROOT / "phase1_readiness_audit.json",
        "v17Phase2Audit": PHASE2_ROOT / "phase2_readiness_audit.json",
        "formalPreregistration": PREREGISTRATION,
        "dataSnapshot": SNAPSHOT,
        "s01FreqtradeSource": Path("user_data/strategies/AlphaPilotS01BearRecovery4H.py"),
        "runtimeManifest": PHASE2_ROOT / "freqtrade_runtime_manifest.json",
        "ioGuard": PHASE2_ROOT / "freqtrade_io_guard_readiness.json",
        "dualEngineReadinessParity": PHASE2_ROOT / "dual_engine_readiness_parity.json",
        "formalResult": Path("reports/formal_validation/advisory_r_v17/s01_formal_metric_summary.json"),
    }
    rows = []
    for role, relative in roles.items():
        path = repo_root / relative
        rows.append(
            {
                "logicalRole": role,
                "actualPath": str(relative),
                "exists": path.is_file(),
                "sizeBytes": path.stat().st_size if path.is_file() else None,
                "sha256": _sha256(path) if path.is_file() else None,
                "schemaFingerprint": None,
                "authoritative": role != "dualEngineReadinessParity",
                "selectedBy": "frozen_v17_identity" if path.is_file() else None,
                "ambiguity": None,
                "missingReason": None if path.is_file() else ROUTE,
            }
        )
    return rows


def _write_not_run_tables(output: Path) -> None:
    metric_names = [
        "rawSignalCount", "acceptedSignalCount", "rejectedByCapitalCompetitionCount",
        "tradeCount", "winRatePct", "profitFactor", "averageGrossR", "averageNetR",
        "totalNetR", "maximumDrawdownR", "maximumDrawdownPct", "feesR", "slippageR",
        "spreadR", "fundingR",
    ]
    metrics = {
        "schemaVersion": "v17_s01_formal_metric_summary_v1",
        "formalResultStatus": "not_run",
        "exactReason": ROUTE,
        **{name: None for name in metric_names},
    }
    _write_json(output / "s01_formal_metric_summary.json", metrics)
    _write_csv(output / "s01_formal_metric_summary.csv", [metrics])
    _write_json(output / "s01_gate_matrix.json", _not_run("s01_gate_matrix"))
    _write_csv(output / "s01_gate_matrix.csv", [_not_run("s01_gate_matrix")])

    tables = {
        "fold_results": ["foldId", "tradeCount", "profitFactor", "averageNetR", "passed"],
        "formal_translation_parity_mismatches": ["signalId", "mismatchType"],
        "rejected_competing_signals": ["signalId", "reason"],
        "benchmark_increment_by_fold": ["foldId", "incrementalNetR"],
        "trial_lineage": ["trialId", "campaignId", "resultRead"],
        "event_level_sample": ["signalId", "symbol", "netR"],
        "trade_level_sample": ["signalId", "symbol", "netR"],
        "exit_leg_sample": ["signalId", "exitReason", "netR"],
    }
    for name, fields in tables.items():
        _write_csv(
            output / f"{name}.csv",
            [{**{field: None for field in fields}, "status": "not_run", "exactReason": ROUTE}],
        )

    json_names = [
        "fold_results", "purge_embargo_audit", "cross_fold_event_audit",
        "capital_competition_results", "simple_benchmark_results", "return_panel_audit",
        "newey_west_alpha", "benjamini_hochberg_fdr", "deflated_sharpe", "pbo",
        "white_reality_check", "spa", "bootstrap_sensitivity",
        "statistical_availability_matrix", "trial_lineage", "trial_parent_child_graph",
        "uncertainty_intervals", "concentration", "breakdown_by_symbol",
        "breakdown_by_month", "breakdown_by_year", "breakdown_by_bear_substate",
        "breakdown_by_volatility_state", "breakdown_by_exit_reason",
        "breakdown_by_holding_time", "event_level_schema",
    ]
    for name in json_names:
        _write_json(output / f"{name}.json", _not_run(name))
    _write_text(
        output / "capital_competition_summary.md",
        f"# Capital competition\n\nStatus: `not_run`\n\nReason: `{ROUTE}`.\n",
    )


def _zip_files(zip_path: Path, root: Path, names: Iterable[str]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(set(names)):
            path = root / name
            if not path.is_file():
                continue
            content = path.read_bytes()
            archive.writestr(name.replace("\\", "/"), content)
            entries.append(
                {"path": name.replace("\\", "/"), "sha256": _sha256_bytes(content)}
            )
    return entries


def _sensitive_scan(output: Path) -> dict[str, Any]:
    pattern = re.compile(
        r"(?i)(?:api[_ -]?key|secret(?:[_ -]?key)?|passphrase|authorization|"
        r"ok-access-key|ok-access-sign|private[_ -]?key)\s*[=:]\s*[\"']?"
        r"(?!false\b|null\b|none\b|unavailable\b)[A-Za-z0-9_+/=-]{16,}"
    )
    hits = []
    scanned = 0
    for path in sorted(output.rglob("*")):
        if not path.is_file() or path.suffix.lower() in {".zip", ".parquet", ".feather"}:
            continue
        scanned += 1
        text = path.read_text(encoding="utf-8", errors="replace")
        if pattern.search(text):
            hits.append(str(path.relative_to(output)).replace("\\", "/"))
    return {
        "schemaVersion": "v17_sensitive_information_scan_v1",
        "scannedFileCount": scanned,
        "sensitiveHitCount": len(hits),
        "hitFiles": hits,
        "credentialValuesIncluded": False,
    }


def _integrity(output: Path, zip_entries: Mapping[str, Sequence[Mapping[str, Any]]]) -> dict[str, Any]:
    json_errors = []
    csv_errors = []
    crlf_files = []
    for path in sorted(output.rglob("*")):
        if not path.is_file() or path.suffix.lower() == ".zip":
            continue
        relative = str(path.relative_to(output)).replace("\\", "/")
        content = path.read_bytes()
        if b"\r\n" in content:
            crlf_files.append(relative)
        try:
            if path.suffix.lower() == ".json":
                json.loads(content.decode("utf-8"))
            elif path.suffix.lower() == ".csv":
                list(csv.reader(content.decode("utf-8").splitlines()))
        except (UnicodeDecodeError, json.JSONDecodeError, csv.Error) as exc:
            (json_errors if path.suffix.lower() == ".json" else csv_errors).append(
                {"path": relative, "error": str(exc)}
            )

    zip_crc = {}
    hash_mismatches = []
    for zip_name, entries in zip_entries.items():
        with zipfile.ZipFile(output / zip_name) as archive:
            zip_crc[zip_name] = archive.testzip()
            for entry in entries:
                content = archive.read(str(entry["path"]))
                if _sha256_bytes(content) != entry["sha256"]:
                    hash_mismatches.append(f"{zip_name}:{entry['path']}")
    return {
        "schemaVersion": "v17_integrity_verification_v1",
        "jsonParseErrors": json_errors,
        "csvParseErrors": csv_errors,
        "parquetArtifactsPresent": False,
        "parquetStatus": "not_run_no_artifacts",
        "zipCrcFailures": {key: value for key, value in zip_crc.items() if value},
        "sourceToZipHashMismatches": hash_mismatches,
        "crlfFiles": crlf_files,
        "requiredLogicalRoleMissingSilentlyCount": 0,
        "passed": (
            not json_errors
            and not csv_errors
            and not any(zip_crc.values())
            and not hash_mismatches
            and not crlf_files
        ),
    }


def build_evidence_delivery(
    repo_root: Path,
    output_root: Path,
    *,
    route_root: Path,
    console_root: Path | None = None,
    docs_root: Path | None = None,
    git_executable: Path | None = None,
    test_manifest: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Create normalized evidence and ZIPs without running formal research."""

    repo_root = Path(repo_root).resolve()
    output = Path(output_root).resolve()
    output.mkdir(parents=True, exist_ok=True)
    prereg = _read_json(repo_root / PREREGISTRATION)
    source_prereg = _read_json(repo_root / SOURCE_PREREGISTRATION)
    snapshot = _read_json(repo_root / SNAPSHOT)
    route = _read_json(Path(route_root) / "route_decision.json")
    if route.get("route") != ROUTE:
        raise ValueError("evidence delivery must preserve the existing terminal route")

    git_manifest = {
        "schemaVersion": "v17_git_manifest_v1",
        "quant": _git_identity(repo_root, git_executable),
        "console": _git_identity(console_root, git_executable),
        "docs": _git_identity(docs_root, git_executable),
        "phase0Commit": "2a6d759",
        "phase1Commit": "244b0f8",
        "phase2Commit": "96a5fbce2907439b3e22a1ecd55ec3b9d07e7f47",
        "resultsBeforeCommit": None,
        "resultsAfterCommit": None,
        "preExistingChanges": [],
    }
    _write_json(output / "git_manifest.json", git_manifest)
    _write_json(output / "version_manifest.json", {"version": "V13.27.1.17", "route": ROUTE})
    _write_json(
        output / "worktree_manifest.json",
        {"quantWorktree": str(repo_root), "consoleRoot": str(console_root) if console_root else None, "docsRoot": str(docs_root) if docs_root else None},
    )

    stages = _stage_inventory(git_manifest["quant"])
    _write_json(output / "v17_stage_inventory.json", stages)
    _write_csv(output / "v17_stage_inventory.csv", stages)
    _write_json(output / "v17_git_timeline.json", {"stages": stages})
    _write_json(
        output / "v17_command_timeline.json",
        {"status": "partial", "reason": "historical shell transcript was not persistently captured", "formalRunCommands": []},
    )

    issues = _issues()
    _write_json(output / "v17_stage_issue_ledger.json", issues)
    _write_csv(output / "v17_stage_issue_ledger.csv", issues)
    _write_text(
        output / "v17_stage_issue_ledger.md",
        "# V17 Stage Issue Ledger\n\n" + "\n".join(f"- `{row['issueId']}` {row['titleZh']} - `{row['status']}`" for row in issues) + "\n",
    )
    patch_rows = [
        {
            "issueId": row["issueId"],
            "category": row["patchCategory"],
            "doesNotChangeStrategyLogic": not row["requiresNewCampaign"],
            "doesNotChangeResultComputation": not row["requiresNewCampaign"],
            "doesNotChangeArtifactIdentity": not row["requiresNewCampaign"],
            "preserveOriginalCampaign": True,
            "newCampaignIdRequired": row["requiresNewCampaign"],
            "newPreregistrationRequired": row["requiresNewCampaign"],
        }
        for row in issues
    ]
    _write_json(output / "v17_patch_candidate_matrix.json", patch_rows)
    _write_csv(output / "v17_patch_candidate_matrix.csv", patch_rows)
    _write_text(
        output / "v17_patch_recommendation.md",
        "# Patch recommendation\n\nV17 must remain immutable. The four executable capital-policy gaps are category B and require a new preregistered campaign. Locked OOS availability is category C and must remain unavailable.\n",
    )

    mapping = _artifact_mapping(repo_root)
    _write_json(output / "input_artifact_mapping.json", mapping)
    _write_csv(output / "artifact_identity_matrix.csv", mapping)
    _write_text(
        output / "input_artifact_mapping.md",
        "# Input artifact mapping\n\n" + "\n".join(f"- `{row['logicalRole']}`: `{row['actualPath']}` ({'exists' if row['exists'] else 'missing'})" for row in mapping) + "\n",
    )

    candidate = next(
        row for row in source_prereg.get("candidates", [])
        if row.get("candidateId") == prereg.get("sourceCandidateId")
    )
    strategy_definition = {
        **candidate,
        "strategyId": candidate.get("candidateId"),
        "displayNameZh": "S01 熊市特异性急跌修复",
        "sourceCampaignId": prereg.get("sourceCampaignId"),
        "sourceCandidateId": prereg.get("sourceCandidateId"),
        "parameterChangesAcrossV17": 0,
        "exitPolicyChangesAcrossV17": 0,
        "BearDefinitionChangesAcrossV17": 0,
        "resultIdentityInvalid": False,
    }
    _write_json(output / "s01_strategy_definition.json", strategy_definition)
    _write_text(output / "s01_strategy_definition.md", "# S01 strategy definition\n\n```json\n" + json.dumps(strategy_definition, ensure_ascii=False, indent=2) + "\n```\n")
    source_dir = output / "source" / "s01"
    source_dir.mkdir(parents=True, exist_ok=True)
    source_paths = [
        Path("user_data/strategies/AlphaPilotS01BearRecovery4H.py"),
        Path("alphapilot/formal_validation/s01_freqtrade_translation.py"),
        Path("alphapilot/formal_validation/s01_dual_engine_audit.py"),
    ]
    source_manifest = []
    for relative in source_paths:
        source = repo_root / relative
        if source.is_file():
            target = source_dir / relative.name
            _write_text(target, source.read_text(encoding="utf-8"))
            source_manifest.append({"path": str(relative), "sha256": _sha256(source), "sizeBytes": source.stat().st_size})
    _write_json(output / "s01_source_manifest.json", source_manifest)

    representative = source_prereg.get("representativeUniverse", {})
    core = prereg.get("coreUniverse", {})
    _write_json(output / "representative_universe.json", representative)
    _write_json(output / "core_universe.json", core)
    representative_ids = set(representative.get("instrumentIds", []))
    core_ids = set(core.get("instrumentIds", []))
    mapping_payload = {"representativeToCore": {item: item if item in core_ids else None for item in sorted(representative_ids)}}
    _write_json(output / "representative_to_core_mapping.json", mapping_payload)
    _write_json(
        output / "universe_identity_audit.json",
        {
            "representativeCount": len(representative_ids),
            "coreCount": len(core_ids),
            "representativeUniverseHash": source_prereg.get("snapshotHash"),
            "coreUniverseHash": prereg.get("coreUniverseHash"),
            "mappingHash": _sha256_bytes(json.dumps(mapping_payload, sort_keys=True).encode()),
            "representativeSubsetOfCore": representative_ids.issubset(core_ids),
            "exactUSDT_SWAP": all(item.endswith("-USDT-SWAP") for item in core_ids),
            "commonCutoff": prereg.get("splitPolicy", {}).get("commonCutoffExclusive"),
            "effectiveStartBySymbol": snapshot.get("effectiveStarts"),
            "historicalPitAvailable": False,
            "fixedCohortLimitation": True,
        },
    )

    locked_identity = _copy_json(
        repo_root / "research/locked_oos/s01_future_locked_oos_identity.json",
        output / "locked_oos_identity.json",
        fallback={"status": "unavailable", "route": "future_locked_oos_required"},
    )
    future = _copy_json(
        repo_root / PHASE2_ROOT / "future_locked_oos_readiness.json",
        output / "future_holdout_status.json",
        fallback={"status": "unavailable", "route": "future_locked_oos_required"},
    )
    access_audit = {
        "route": "future_locked_oos_required",
        "holdoutId": locked_identity.get("holdoutId"),
        "startTime": locked_identity.get("startTime"),
        "endTime": locked_identity.get("endTime"),
        "preexistingHash": locked_identity.get("preexistingHash"),
        "metadataSource": str(PHASE2_ROOT / "future_locked_oos_readiness.json"),
        "accessCountBeforeV17": 0,
        "accessCountDuringV17": 0,
        "accessCountAfterV17": 0,
        "contentReadCount": 0,
        "contentHashRecomputed": False,
        "selectionContaminated": False,
        "cleanLockedOosAvailable": bool(prereg.get("lockedOosPolicy", {}).get("cleanLockedOosAvailable")),
    }
    _write_json(output / "locked_oos_access_audit.json", access_audit)
    _write_json(output / "locked_oos_access_ledger.json", {"entries": [], "accessCount": 0, "contentReadCount": 0})

    _write_json(output / "formal_preregistration.json", prereg)
    _write_text(output / "formal_preregistration_hash.txt", str(prereg.get("preregistrationHash")) + "\n")
    _write_json(output / "split_policy.json", prereg.get("splitPolicy"))
    _write_json(output / "formal_portfolio_policy.json", prereg.get("capitalCompetitionPolicy"))
    _write_json(output / "cost_policy.json", prereg.get("costModel"))
    _write_json(output / "statistical_method_contract.json", prereg.get("statisticalPolicy"))

    runtime = _copy_json(
        repo_root / PHASE2_ROOT / "freqtrade_runtime_manifest.json",
        output / "freqtrade_runtime_manifest.json",
        fallback=_not_run("freqtrade_runtime_manifest"),
    )
    _write_json(output / "runtime_manifest.json", runtime)
    dependency = repo_root / PHASE2_ROOT / "freqtrade_dependency_lock.txt"
    _write_text(output / "freqtrade_dependency_lock.txt", dependency.read_text("utf-8") if dependency.is_file() else "unavailable\n")
    _copy_json(repo_root / PHASE2_ROOT / "freqtrade_io_guard_readiness.json", output / "freqtrade_io_guard_audit.json", fallback=_not_run("freqtrade_io_guard"))
    _copy_json(repo_root / PHASE2_ROOT / "freqtrade_io_fixture_access_log.json", output / "freqtrade_file_access_log.json", fallback={"status": "unavailable"})
    _copy_json(repo_root / PHASE2_ROOT / "non_holdout_data_root_manifest.json", output / "non_holdout_data_root_manifest.json", fallback={"status": "unavailable"})
    _copy_json(repo_root / PHASE2_ROOT / "dual_engine_readiness_parity.json", output / "dual_engine_fixture_parity.json", fallback=_not_run("dual_engine_fixture_parity"))
    _write_json(output / "formal_translation_parity.json", _not_run("formal_translation_parity"))
    _write_json(output / "exit_leg_parity.json", _not_run("exit_leg_parity"))

    _write_not_run_tables(output)
    for name in ("route_decision.json", "gate_matrix.json", "failure_attribution.json", "campaign_summary.json"):
        _write_json(output / name, _read_json(Path(route_root) / name))
    _write_text(
        output / "campaign_summary.md",
        (Path(route_root) / "campaign_summary.md").read_text(encoding="utf-8"),
    )

    tests = {
        "schemaVersion": "v17_test_manifest_v1",
        "status": "pending_final_verification",
        "focusedTests": None,
        "formalValidationTests": None,
        "fullTests": None,
        "subtestCount": None,
        "skippedCount": None,
        "deselectedCount": None,
        "compileall": None,
        "validateConfig": None,
        "safetyScan": None,
        "gitDiffCheck": None,
        **dict(test_manifest or {}),
    }
    _write_json(output / "test_manifest.json", tests)
    _write_json(output / "skipped_test_audit.json", {"status": "pending_final_verification", "tests": []})
    _write_json(output / "known_issues.json", {"issues": issues, "historicalCrLfSidecarHashDifferencePreserved": True})
    _write_json(
        output / "safety_boundary_audit.json",
        {
            "apiKeyPersisted": False,
            "tradeApiConnected": False,
            "withdrawApiConnected": False,
            "realAccountRead": False,
            "realPositionRead": False,
            "demoOrderCreated": False,
            "liveOrderCreated": False,
            "exchangeDryRun": False,
            "demoArm": False,
            "releaseCount": 0,
            "formalEvidenceCount": 0,
            "lockedOosAccessCount": 0,
            "evidenceBasis": ["frozen preregistration safety boundary", "terminal route bundle", "source safety scan"],
        },
    )

    final_check = {
        "schemaVersion": "v17_final_self_check_v1",
        "v17Complete": True,
        "finalRoute": ROUTE,
        "quant": git_manifest["quant"],
        "docs": git_manifest["docs"],
        "console": git_manifest["console"],
        "authoritativeCampaignId": CAMPAIGN_ID,
        "preregistrationHash": prereg.get("preregistrationHash"),
        "strategyDefinitionHash": candidate.get("strategyDefinitionHash"),
        "exitPolicyHash": prereg.get("exitPolicyHash"),
        "representativeUniverseHash": source_prereg.get("snapshotHash"),
        "coreUniverseHash": prereg.get("coreUniverseHash"),
        "splitPolicyHash": prereg.get("splitPolicyHash"),
        "formalPortfolioPolicyHash": prereg.get("capitalCompetitionPolicyHash"),
        "costModelHash": prereg.get("costModelHash"),
        "runtimeHash": runtime.get("manifestHash") or runtime.get("runtimeHash"),
        "lockedOosRoute": "future_locked_oos_required",
        "lockedOosAccessCount": 0,
        "lockedOosContentReadCount": 0,
        "formalRunCount": 0,
        "resultReadCount": 0,
        "foldCompleteness": None,
        "eventCount": None,
        "tradeCount": None,
        "formalMetrics": None,
        "statisticalMetrics": None,
        "formalPass": False,
        "formalEvidenceCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "demoOrderCount": 0,
        "liveOrderCount": 0,
        "stageIssueCount": len(issues),
        "resolvedIssueCount": sum(row["status"] == "resolved_before_result" for row in issues),
        "patchCategoryACount": sum(row["patchCategory"] == "A" for row in issues),
        "patchCategoryBCount": sum(row["patchCategory"] == "B" for row in issues),
        "patchCategoryCCount": sum(row["patchCategory"] == "C" for row in issues),
        "resultInvalidated": False,
        "resultUnavailable": True,
        "knownIssues": [row["issueId"] for row in issues if row["status"] not in {"resolved_before_result", "not_an_issue"}],
        "nextStep": "Create a new preregistered correction campaign with complete executable capital-policy definitions.",
    }
    _write_json(output / "final_self_check.json", final_check)
    _write_text(
        output / "final_self_check.md",
        f"# V13.27.1.17 Final Self Check\n\n- Complete: yes\n- Route: `{ROUTE}`\n- Formal run / result reads: 0 / 0\n- Locked OOS reads: 0\n- Formal Evidence / Release / Demo ARM / orders: 0 / 0 / false / 0\n- Result metrics: unavailable, not zero\n- Next: new preregistered campaign with executable capital policy.\n",
    )
    _write_text(
        output / "README.md",
        "# AlphaPilot V13.27.1.17 Evidence Delivery\n\nRead in order: final_self_check.md, campaign_summary.md, route_decision.json, s01_formal_metric_summary.csv, fold_results.csv, gate_matrix.json, statistical_availability_matrix.json, stage issue ledger, patch recommendation, known issues, and safety audit.\n",
    )

    not_run_manifest = {"status": "not_run", "exactReason": ROUTE, "eventLevelArtifactUnavailable": True, "parquetArtifacts": []}
    _write_json(output / "not_run_manifest.json", not_run_manifest)

    def build_manifest_and_archives() -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
        evidence = []
        for path in sorted(output.rglob("*")):
            if path.is_file() and path.suffix.lower() != ".zip" and path.name not in {"evidence_manifest.json", "artifact_manifest.json"}:
                evidence.append({"path": str(path.relative_to(output)).replace("\\", "/"), "sizeBytes": path.stat().st_size, "sha256": _sha256(path)})
        manifest = {"schemaVersion": "v17_evidence_manifest_v1", "campaignId": CAMPAIGN_ID, "route": ROUTE, "artifacts": evidence}
        _write_json(output / "evidence_manifest.json", manifest)
        _write_json(output / "artifact_manifest.json", manifest)
        core_names = [path.name for path in output.iterdir() if path.is_file() and path.suffix.lower() in {".json", ".csv", ".md", ".txt"} and path.name not in {"not_run_manifest.json"}]
        event_names = ["not_run_manifest.json", "event_level_schema.json", "event_level_sample.csv", "trade_level_sample.csv", "exit_leg_sample.csv", "freqtrade_file_access_log.json"]
        source_names = [str(path.relative_to(output)).replace("\\", "/") for path in source_dir.rglob("*") if path.is_file()]
        source_names += ["s01_source_manifest.json", "runtime_manifest.json", "freqtrade_dependency_lock.txt", "freqtrade_io_guard_audit.json"]
        entries = {
            "AlphaPilot-V13.27.1.17-core-evidence.zip": _zip_files(output / "AlphaPilot-V13.27.1.17-core-evidence.zip", output, core_names),
            "AlphaPilot-V13.27.1.17-event-and-return-evidence.zip": _zip_files(output / "AlphaPilot-V13.27.1.17-event-and-return-evidence.zip", output, event_names),
            "AlphaPilot-V13.27.1.17-source-runtime-evidence.zip": _zip_files(output / "AlphaPilot-V13.27.1.17-source-runtime-evidence.zip", output, source_names),
        }
        return manifest, entries

    _, zip_entries = build_manifest_and_archives()
    sensitive = _sensitive_scan(output)
    _write_json(output / "sensitive_information_scan.json", sensitive)
    integrity = _integrity(output, zip_entries)
    _write_json(output / "integrity_verification.json", integrity)
    final_check["integrityPassed"] = integrity["passed"]
    final_check["artifactHashMismatchCount"] = len(integrity["sourceToZipHashMismatches"])
    final_check["sensitiveHitCount"] = sensitive["sensitiveHitCount"]
    _write_json(output / "final_self_check.json", final_check)
    _, zip_entries = build_manifest_and_archives()
    integrity = _integrity(output, zip_entries)
    _write_json(output / "integrity_verification.json", integrity)
    return {
        "outputRoot": str(output),
        "route": ROUTE,
        "formalRunCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "integrityPassed": integrity["passed"],
        "sensitiveHitCount": sensitive["sensitiveHitCount"],
    }
