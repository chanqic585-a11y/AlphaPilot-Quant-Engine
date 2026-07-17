"""V13.27.1.17 Phase 0 formal-validation readiness audit."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.evaluation.purged_walk_forward import build_purged_walk_forward
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash
from alphapilot.research_screening.capital_competition import CapitalCompetitionPolicy

from .holdout_lineage_audit import CAMPAIGN_ID, audit_holdout_lineage, load_metadata_json
from .phase1_contracts import (
    FORMAL_CAMPAIGN_ID,
    FORMAL_PREREGISTRATION_PATH,
    verify_s01_formal_preregistration,
)


BASELINE_TAG = "v13.27.1.16"
BASELINE_COMMIT = "6d885eee532d45a2c7c1cbeb37c92fe2ac031c3b"
S01_CANDIDATE_ID = "s01_bear_idiosyncratic_selloff_recovery_4h"
PREREGISTRATION_PATH = Path("research/preregistrations") / f"{CAMPAIGN_ID}.json"
SNAPSHOT_PATH = Path("research/data_snapshots/minimal_snapshot_785e47b180c17327dcb35e37.json")
CAMPAIGN_PATH = Path("reports/advisory_r_campaign") / CAMPAIGN_ID

EXPECTED_V16_ARTIFACTS = {
    "benchmarkComparison": "benchmark_comparison.json",
    "campaignSummaryJson": "campaign_summary.json",
    "campaignSummaryMarkdown": "campaign_summary.md",
    "candidateEvents": "candidate_events.parquet",
    "conformanceMatrixCsv": "conformance_matrix.csv",
    "conformanceMatrixJson": "conformance_matrix.json",
    "correctedVsV15Comparison": "corrected_vs_v15_comparison.json",
    "correctionManifest": "correction_manifest.json",
    "eventSchema": "event_schema.json",
    "exitLegParity": "exit_leg_parity.json",
    "exitPolicyAttribution": "exit_policy_attribution.json",
    "failureAttribution": "failure_attribution.json",
    "implementationParity": "implementation_parity.json",
    "noveltyAudit": "novelty_audit.json",
    "prefilterGateMatrix": "prefilter_gate_matrix.json",
    "prefilterResults": "prefilter_results.json",
    "routeDecision": "route_decision.json",
    "simpleBenchmarks": "simple_benchmarks.json",
    "strategyInventory": "strategy_inventory.json",
    "trialLedgerCsv": "trial_ledger.csv",
    "trialLedgerJson": "trial_ledger.json",
}

_PHASE1_FORMAL_MESSAGES = {
    "v16_identity_incomplete": "V16 identity or its evidence bundle is incomplete.",
    "formal_preregistration_invalid": "The S01 formal preregistration is missing or invalid.",
    "formal_preregistration_not_published": "The S01 preregistration is not committed and published on the upstream branch.",
    "formal_split_policy_not_frozen": "The five-fold split, purge, and embargo policy is not frozen.",
    "capital_policy_not_frozen": "The capital-competition policy is not frozen.",
    "s01_freqtrade_translation_missing": "The exact research-only S01 Freqtrade translation is missing.",
    "freqtrade_runtime_missing": "Freqtrade is unavailable in the audited execution runtime.",
    "timerange_io_guard_missing": "The timerange and input/output isolation guard is incomplete.",
}


def classify_phase1_readiness(
    *,
    formal_checks: dict[str, bool],
    clean_locked_oos_available: bool,
    formal_walk_forward_completed: bool,
) -> dict[str, Any]:
    """Keep formal execution and one-shot Locked OOS admission independent."""

    unknown = set(formal_checks) - set(_PHASE1_FORMAL_MESSAGES)
    if unknown:
        raise ValueError(f"unknown Phase 1 formal checks: {sorted(unknown)}")
    formal_blockers = [
        {"code": code, "message": _PHASE1_FORMAL_MESSAGES[code]}
        for code, passed in formal_checks.items()
        if not passed
    ]
    locked_blockers: list[dict[str, str]] = []
    if not clean_locked_oos_available:
        locked_blockers.append(
            {
                "code": "locked_oos_identity_incomplete",
                "message": (
                    "The Locked OOS boundary, content hash, zero-access record, and "
                    "one-shot unlock ledger are not all available."
                ),
            }
        )
    if not formal_walk_forward_completed:
        locked_blockers.append(
            {
                "code": "formal_walk_forward_not_completed",
                "message": "The preregistered formal Walk-forward has not been completed.",
            }
        )
    return {
        "formalExecution": {
            "status": "ready" if not formal_blockers else "blocked",
            "blockers": formal_blockers,
        },
        "lockedOosAdmission": {
            "status": "ready" if not locked_blockers else "blocked",
            "blockers": locked_blockers,
        },
    }


def _git(repo_root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=check,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    return completed.stdout.strip()


def _git_succeeds(repo_root: Path, *args: str) -> bool:
    return (
        subprocess.run(
            ["git", *args],
            cwd=repo_root,
            capture_output=True,
        ).returncode
        == 0
    )


def _git_optional(repo_root: Path, *args: str) -> str | None:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if completed.returncode != 0:
        return None
    return completed.stdout.strip() or None


def audit_phase1_preregistration(repo_root: Path) -> dict[str, Any]:
    """Audit the frozen preregistration and its publication state only."""

    repo_root = Path(repo_root).resolve()
    path = repo_root / FORMAL_PREREGISTRATION_PATH
    relative_path = FORMAL_PREREGISTRATION_PATH.as_posix()
    upstream = _git_optional(
        repo_root,
        "rev-parse",
        "--abbrev-ref",
        "--symbolic-full-name",
        "@{u}",
    )
    if not path.is_file():
        return {
            "schemaVersion": "s01_formal_preregistration_audit_v1",
            "status": "missing",
            "path": relative_path,
            "exists": False,
            "hashValid": False,
            "identityValid": False,
            "tracked": False,
            "workingTreeMatchesCommit": False,
            "containingCommit": None,
            "upstream": upstream,
            "published": False,
        }

    payload = load_metadata_json(path)
    tracked = _git_succeeds(repo_root, "ls-files", "--error-unmatch", "--", relative_path)
    working_tree_matches = bool(
        tracked
        and _git_succeeds(repo_root, "diff", "--quiet", "HEAD", "--", relative_path)
        and _git_succeeds(repo_root, "diff", "--cached", "--quiet", "--", relative_path)
    )
    containing_commit = (
        _git_optional(repo_root, "log", "-1", "--format=%H", "--", relative_path)
        if tracked
        else None
    )
    published = bool(
        containing_commit
        and upstream
        and working_tree_matches
        and _git_succeeds(
            repo_root,
            "merge-base",
            "--is-ancestor",
            containing_commit,
            upstream,
        )
    )
    hash_valid = verify_s01_formal_preregistration(payload)
    identity_valid = bool(
        payload.get("campaignId") == FORMAL_CAMPAIGN_ID
        and payload.get("sourceCandidateId") == S01_CANDIDATE_ID
        and payload.get("candidateCount") == 1
    )
    return {
        "schemaVersion": "s01_formal_preregistration_audit_v1",
        "status": "published" if hash_valid and identity_valid and published else "blocked",
        "path": relative_path,
        "exists": True,
        "campaignId": payload.get("campaignId"),
        "candidateId": payload.get("sourceCandidateId"),
        "preregistrationHash": payload.get("preregistrationHash"),
        "hashValid": hash_valid,
        "identityValid": identity_valid,
        "tracked": tracked,
        "workingTreeMatchesCommit": working_tree_matches,
        "containingCommit": containing_commit,
        "upstream": upstream,
        "published": published,
    }


def _verify_preregistration_hash(payload: dict[str, Any]) -> bool:
    core = {key: value for key, value in payload.items() if key != "preregistrationHash"}
    expected = stable_hash(core, prefix="advisory_r_correction_preregistration")
    return payload.get("preregistrationHash") == expected


def _verify_snapshot_hash(payload: dict[str, Any]) -> bool:
    excluded = {"createdAt", "snapshotId", "snapshotHash"}
    core = {key: value for key, value in payload.items() if key not in excluded}
    expected = stable_hash(core, prefix="minimal_shared_snapshot")
    return payload.get("snapshotHash") == expected


def audit_v16_identity(repo_root: Path) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    preregistration = load_metadata_json(repo_root / PREREGISTRATION_PATH)
    snapshot = load_metadata_json(repo_root / SNAPSHOT_PATH)
    campaign_root = repo_root / CAMPAIGN_PATH
    tag_commit = _git(repo_root, "rev-list", "-n", "1", BASELINE_TAG)
    source_commit = str(preregistration.get("codeCommit") or "")
    source_commit_exists = _git_succeeds(
        repo_root, "cat-file", "-e", f"{source_commit}^{{commit}}"
    )
    source_is_ancestor = (
        _git_succeeds(repo_root, "merge-base", "--is-ancestor", source_commit, BASELINE_COMMIT)
        if source_commit_exists
        else False
    )

    artifacts: list[dict[str, Any]] = []
    missing: list[str] = []
    invalid_hashes: list[str] = []
    for role, filename in EXPECTED_V16_ARTIFACTS.items():
        path = campaign_root / filename
        if not path.is_file():
            missing.append(role)
            continue
        digest = sha256_file(path)
        if len(digest) != 64:
            invalid_hashes.append(role)
        artifacts.append(
            {
                "logicalRole": role,
                "path": path.relative_to(repo_root).as_posix(),
                "sha256": digest,
                "sizeBytes": path.stat().st_size,
            }
        )

    representative = set(preregistration["representativeUniverse"]["instrumentIds"])
    dataset_references = list(snapshot.get("datasetReferences") or [])
    formal_core = {str(row["instrumentId"]) for row in dataset_references}
    timeframes = sorted({str(row["timeframe"]) for row in dataset_references})
    reference_keys = {
        (str(row["instrumentId"]), str(row["timeframe"])) for row in dataset_references
    }
    expected_reference_keys = {(symbol, timeframe) for symbol in formal_core for timeframe in timeframes}
    candidates = list(preregistration.get("candidates") or [])
    candidate_ids = [str(row.get("candidateId")) for row in candidates]

    checks = {
        "baselineTagMatches": tag_commit == BASELINE_COMMIT,
        "sourceCommitExists": source_commit_exists,
        "sourceCommitIsAncestor": source_is_ancestor,
        "preregistrationHashValid": _verify_preregistration_hash(preregistration),
        "snapshotHashValid": _verify_snapshot_hash(snapshot),
        "snapshotLinkMatches": (
            preregistration.get("snapshotId") == snapshot.get("snapshotId")
            and preregistration.get("snapshotHash") == snapshot.get("snapshotHash")
        ),
        "artifactBundleComplete": not missing and len(artifacts) == len(EXPECTED_V16_ARTIFACTS),
        "representativeIsSubset": representative <= formal_core,
        "datasetGridComplete": reference_keys == expected_reference_keys,
        "s01Present": S01_CANDIDATE_ID in candidate_ids,
        "candidateCountFrozen": len(candidate_ids) == 10,
    }
    return {
        "schemaVersion": "formal_validation_v16_identity_audit_v1",
        "status": "ready" if all(checks.values()) and not invalid_hashes else "blocked",
        "baselineTag": BASELINE_TAG,
        "baselineCommit": BASELINE_COMMIT,
        "tagCommit": tag_commit,
        "sourceCodeCommit": source_commit,
        "campaignId": CAMPAIGN_ID,
        "preregistrationPath": PREREGISTRATION_PATH.as_posix(),
        "preregistrationHash": preregistration.get("preregistrationHash"),
        "snapshotPath": SNAPSHOT_PATH.as_posix(),
        "snapshotId": snapshot.get("snapshotId"),
        "snapshotHash": snapshot.get("snapshotHash"),
        "coreUniverseHash": snapshot.get("coreUniverseHash"),
        "candidateIds": candidate_ids,
        "checks": checks,
        "artifactCount": len(artifacts),
        "missingArtifacts": missing,
        "invalidArtifactHashes": invalid_hashes,
        "artifacts": artifacts,
        "universeMapping": {
            "representativeCount": len(representative),
            "representativeInstruments": sorted(representative),
            "formalCoreCount": len(formal_core),
            "formalCoreInstruments": sorted(formal_core),
            "representativeIsSubset": representative <= formal_core,
            "datasetReferenceCount": len(dataset_references),
            "datasetGridComplete": reference_keys == expected_reference_keys,
            "timeframes": timeframes,
        },
    }


def _contains_key(payload: Any, names: set[str]) -> bool:
    if isinstance(payload, dict):
        return any(
            (key in names and value not in (None, "", [], {}))
            or _contains_key(value, names)
            for key, value in payload.items()
        )
    if isinstance(payload, list):
        return any(_contains_key(item, names) for item in payload)
    return False


def _candidate_translation_available(repo_root: Path) -> tuple[bool, list[str]]:
    matches: list[str] = []
    roots = (
        repo_root / "user_data" / "strategies",
        repo_root / "strategies",
        repo_root / "alphapilot" / "formal_validation" / "strategies",
    )
    for root in roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            if S01_CANDIDATE_ID in path.read_text(encoding="utf-8", errors="ignore"):
                matches.append(path.relative_to(repo_root).as_posix())
    return bool(matches), matches


def audit_formal_prerequisites(repo_root: Path) -> dict[str, Any]:
    repo_root = Path(repo_root).resolve()
    preregistration = load_metadata_json(repo_root / PREREGISTRATION_PATH)
    event_path = repo_root / CAMPAIGN_PATH / "candidate_events.parquet"
    required_columns = {
        "candidateId",
        "symbol",
        "executionTimestamp",
        "netR",
        "split",
        "foldId",
    }
    frame = pd.read_parquet(event_path)
    present_columns = set(frame.columns)
    parsed_timestamps = pd.to_datetime(frame["executionTimestamp"], utc=True, errors="coerce")
    candidate_counts = frame.groupby("candidateId", dropna=False).size().to_dict()
    splits = sorted(str(value) for value in frame["split"].dropna().unique())
    folds = sorted(str(value) for value in frame["foldId"].dropna().unique())
    formal_split_policy_frozen = _contains_key(
        preregistration,
        {"formalWalkForward", "walkForwardPolicy", "formalSplitPolicy", "purgePolicy"},
    )
    formal_walk_forward_present = any(value.startswith("formal_") for value in splits)
    translation_available, translation_paths = _candidate_translation_available(repo_root)
    timerange_guard_paths = (
        repo_root / "alphapilot" / "formal_validation" / "timerange_io_guard.py",
        repo_root / "scripts" / "validate_formal_timerange.py",
    )
    timerange_guard_available = any(path.is_file() for path in timerange_guard_paths)
    policy = CapitalCompetitionPolicy()
    capital_policy_payload = asdict(policy)
    capital_policy_frozen = _contains_key(
        preregistration, {"riskCapitalHash", "capitalCompetitionPolicyHash"}
    )
    package_available = importlib.util.find_spec("freqtrade") is not None

    return {
        "schemaVersion": "formal_validation_prerequisite_audit_v1",
        "statisticalPanel": {
            "path": event_path.relative_to(repo_root).as_posix(),
            "rowCount": len(frame),
            "candidateCount": int(frame["candidateId"].nunique()),
            "candidateEventCounts": {str(key): int(value) for key, value in candidate_counts.items()},
            "requiredColumns": sorted(required_columns),
            "missingColumns": sorted(required_columns - present_columns),
            "netRNullCount": int(frame["netR"].isna().sum()),
            "invalidExecutionTimestampCount": int(parsed_timestamps.isna().sum()),
            "splitValues": splits,
            "foldIds": folds,
            "dailyPanelFeasible": bool(
                required_columns <= present_columns
                and not frame.empty
                and frame["candidateId"].nunique() == 10
                and frame["netR"].notna().all()
                and parsed_timestamps.notna().all()
            ),
            "formalWalkForwardEvidencePresent": formal_walk_forward_present,
        },
        "purgedWalkForward": {
            "available": callable(build_purged_walk_forward),
            "formalSplitPolicyFrozen": formal_split_policy_frozen,
            "note": "Infrastructure exists; V17 fold boundaries and purge policy are not frozen yet.",
        },
        "capitalCompetition": {
            "available": True,
            "policy": capital_policy_payload,
            "policyHash": stable_hash(
                capital_policy_payload, prefix="capital_competition_policy"
            ),
            "frozenForV17": capital_policy_frozen,
        },
        "freqtrade": {
            "packageAvailable": package_available,
            "s01TranslationAvailable": translation_available,
            "translationPaths": translation_paths,
            "timerangeIoGuardAvailable": timerange_guard_available,
            "timerangeIoGuardPaths": [
                path.relative_to(repo_root).as_posix()
                for path in timerange_guard_paths
                if path.is_file()
            ],
        },
    }


def build_phase0_readiness_audit(repo_root: Path) -> dict[str, Any]:
    identity = audit_v16_identity(repo_root)
    holdout = audit_holdout_lineage(repo_root)
    prerequisites = audit_formal_prerequisites(repo_root)
    blockers: list[dict[str, str]] = []

    def block(code: str, message: str) -> None:
        blockers.append({"code": code, "message": message})

    if identity["status"] != "ready":
        block("v16_identity_incomplete", "V16 identity or its 21-artifact evidence bundle is incomplete.")
    if not holdout["cleanLockedOosAvailable"]:
        block(
            "locked_oos_identity_incomplete",
            "Locked OOS has zero recorded access, but its frozen boundary/hash/ledger identity is incomplete.",
        )
    if not prerequisites["purgedWalkForward"]["formalSplitPolicyFrozen"]:
        block("formal_split_policy_not_frozen", "V17 walk-forward folds and purge policy are not preregistered.")
    if not prerequisites["capitalCompetition"]["frozenForV17"]:
        block("capital_policy_not_frozen", "The available capital-competition policy is not frozen for V17.")
    if not prerequisites["freqtrade"]["s01TranslationAvailable"]:
        block("s01_freqtrade_translation_missing", "No exact S01 Freqtrade translation is present.")
    if not prerequisites["freqtrade"]["packageAvailable"]:
        block("freqtrade_runtime_missing", "Freqtrade is not installed in the audited Python runtime.")
    if not prerequisites["freqtrade"]["timerangeIoGuardAvailable"]:
        block("timerange_io_guard_missing", "No formal timerange and output-isolation guard is present.")

    preregistration = load_metadata_json(Path(repo_root) / PREREGISTRATION_PATH)
    safety = dict(preregistration.get("safetyBoundary") or {})
    return {
        "schemaVersion": "formal_validation_phase0_readiness_audit_v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "phase": "V13.27.1.17-phase0",
        "scope": "readiness_only",
        "route": "blocked" if blockers else "ready_for_preregistration",
        "candidateId": S01_CANDIDATE_ID,
        "identity": identity,
        "holdoutLineage": holdout,
        "prerequisites": prerequisites,
        "blockers": blockers,
        "safetyBoundary": {
            "lockedOosAccessCount": safety.get("lockedOosAccessCount"),
            "formalEvidenceCount": safety.get("formalEvidenceCount"),
            "releaseCount": safety.get("releaseCount"),
            "demoArm": safety.get("demoArm"),
            "orderCount": safety.get("orderCount"),
            "formalWalkForwardExecuted": False,
            "lockedOosOpened": False,
            "releaseGenerated": False,
            "demoTouched": False,
            "ordersPlaced": False,
        },
    }


def _audit_phase1_frozen_contracts(repo_root: Path) -> dict[str, Any]:
    path = Path(repo_root).resolve() / FORMAL_PREREGISTRATION_PATH
    payload = load_metadata_json(path) if path.is_file() else {}
    split = dict(payload.get("splitPolicy") or {})
    capital = dict(payload.get("capitalCompetitionPolicy") or {})
    split_frozen = bool(
        split.get("foldCount") == 5
        and len(split.get("folds") or []) == 5
        and int(split.get("purgeBars") or 0) >= 24
        and int(split.get("embargoBars") or 0) >= 24
        and split.get("eventMayCrossFoldBoundary") is False
        and payload.get("splitPolicyHash") == split.get("splitPolicyHash")
    )
    capital_frozen = bool(
        capital.get("duplicateSymbolPolicy") == "reject_while_open"
        and len(capital.get("rankingPolicy") or []) == 4
        and payload.get("capitalCompetitionPolicyHash")
        == capital.get("capitalCompetitionPolicyHash")
    )
    translation_available, translation_paths = _candidate_translation_available(
        Path(repo_root).resolve()
    )
    timerange_module = (
        Path(repo_root).resolve()
        / "alphapilot"
        / "formal_validation"
        / "timerange_io_guard.py"
    )
    timerange_cli = Path(repo_root).resolve() / "scripts" / "validate_formal_timerange.py"
    return {
        "splitPolicyFrozen": split_frozen,
        "splitPolicyHash": payload.get("splitPolicyHash"),
        "capitalCompetitionPolicyFrozen": capital_frozen,
        "capitalCompetitionPolicyHash": payload.get("capitalCompetitionPolicyHash"),
        "s01TranslationAvailable": translation_available,
        "translationPaths": translation_paths,
        "freqtradePackageAvailable": importlib.util.find_spec("freqtrade") is not None,
        "timerangeGuardModuleAvailable": timerange_module.is_file(),
        "timerangeGuardCliAvailable": timerange_cli.is_file(),
    }


def build_phase1_readiness_audit(repo_root: Path) -> dict[str, Any]:
    """Build post-freeze readiness without running S01 or opening Locked OOS."""

    repo_root = Path(repo_root).resolve()
    identity = audit_v16_identity(repo_root)
    holdout = audit_holdout_lineage(repo_root)
    preregistration = audit_phase1_preregistration(repo_root)
    contracts = _audit_phase1_frozen_contracts(repo_root)
    formal_checks = {
        "v16_identity_incomplete": identity["status"] == "ready",
        "formal_preregistration_invalid": bool(
            preregistration["exists"]
            and preregistration["hashValid"]
            and preregistration["identityValid"]
        ),
        "formal_preregistration_not_published": preregistration["published"],
        "formal_split_policy_not_frozen": contracts["splitPolicyFrozen"],
        "capital_policy_not_frozen": contracts["capitalCompetitionPolicyFrozen"],
        "s01_freqtrade_translation_missing": contracts["s01TranslationAvailable"],
        "freqtrade_runtime_missing": contracts["freqtradePackageAvailable"],
        "timerange_io_guard_missing": bool(
            contracts["timerangeGuardModuleAvailable"]
            and contracts["timerangeGuardCliAvailable"]
        ),
    }
    gates = classify_phase1_readiness(
        formal_checks=formal_checks,
        clean_locked_oos_available=holdout["cleanLockedOosAvailable"],
        formal_walk_forward_completed=False,
    )
    return {
        "schemaVersion": "formal_validation_phase1_readiness_audit_v1",
        "generatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "phase": "V13.27.1.17-phase1",
        "scope": "prerequisite_freeze_only",
        "route": (
            "ready_for_formal_walk_forward"
            if gates["formalExecution"]["status"] == "ready"
            else "blocked"
        ),
        "candidateId": S01_CANDIDATE_ID,
        "identity": identity,
        "preregistration": preregistration,
        "frozenContracts": contracts,
        "holdoutLineage": holdout,
        "gates": gates,
        "blockers": gates["formalExecution"]["blockers"],
        "safetyBoundary": {
            "lockedOosAccessCount": 0,
            "formalResultCount": 0,
            "releaseCount": 0,
            "demoArm": False,
            "orderCount": 0,
        },
    }


def _render_holdout_markdown(audit: dict[str, Any]) -> str:
    missing = ", ".join(audit["missingIdentityFields"]) or "none"
    return "\n".join(
        [
            "# Locked OOS Lineage Audit",
            "",
            f"- Status: `{audit['status']}`",
            f"- Metadata only: `{str(audit['metadataOnly']).lower()}`",
            f"- Recorded access count: `{audit['recordedAccessCount']}`",
            f"- Access counts consistent: `{str(audit['accessCountsConsistent']).lower()}`",
            f"- Unlock ledger present: `{str(audit['unlockLedgerPresent']).lower()}`",
            f"- Frozen boundary present: `{str(audit['holdoutBoundaryPresent']).lower()}`",
            f"- Holdout hash present: `{str(audit['holdoutHashPresent']).lower()}`",
            f"- Clean Locked OOS available: `{str(audit['cleanLockedOosAvailable']).lower()}`",
            f"- Missing identity fields: `{missing}`",
            "",
            audit["admissionRule"],
            "",
        ]
    )


def _render_phase0_markdown(audit: dict[str, Any]) -> str:
    identity = audit["identity"]
    panel = audit["prerequisites"]["statisticalPanel"]
    lines = [
        "# V13.27.1.17 Phase 0 Readiness Audit",
        "",
        f"- Route: `{audit['route']}`",
        f"- Candidate: `{audit['candidateId']}`",
        f"- V16 artifacts: `{identity['artifactCount']}/21`",
        (
            "- Universe mapping: "
            f"`{identity['universeMapping']['representativeCount']}` representative -> "
            f"`{identity['universeMapping']['formalCoreCount']}` formal core"
        ),
        f"- Candidate events: `{panel['rowCount']}` across `{panel['candidateCount']}` candidates",
        f"- Locked OOS opened: `{str(audit['safetyBoundary']['lockedOosOpened']).lower()}`",
        "",
        "## Blockers",
        "",
    ]
    if audit["blockers"]:
        lines.extend(
            f"- `{item['code']}`: {item['message']}" for item in audit["blockers"]
        )
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "Do not start formal walk-forward or open Locked OOS until every blocker is "
                "resolved and the resulting identities are preregistered."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_phase0_evidence_bundle(audit: dict[str, Any], output_root: Path) -> list[Path]:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    readiness_json = output_root / "phase0_readiness_audit.json"
    readiness_md = output_root / "phase0_readiness_audit.md"
    holdout_json = output_root / "holdout_lineage_audit.json"
    holdout_md = output_root / "holdout_lineage_audit.md"
    manifest_path = output_root / "artifact_manifest.json"

    write_json_atomic(readiness_json, audit)
    readiness_md.write_text(_render_phase0_markdown(audit), encoding="utf-8")
    write_json_atomic(holdout_json, audit["holdoutLineage"])
    holdout_md.write_text(_render_holdout_markdown(audit["holdoutLineage"]), encoding="utf-8")
    report_paths = [readiness_json, readiness_md, holdout_json, holdout_md]
    logical_roles = {
        "phase0_readiness_audit.json": "phase0ReadinessJson",
        "phase0_readiness_audit.md": "phase0ReadinessMarkdown",
        "holdout_lineage_audit.json": "holdoutLineageJson",
        "holdout_lineage_audit.md": "holdoutLineageMarkdown",
    }
    manifest = {
        "schemaVersion": "formal_validation_phase0_manifest_v1",
        "artifacts": [
            {
                "logicalRole": logical_roles[path.name],
                "path": path.name,
                "sha256": sha256_file(path),
                "sizeBytes": path.stat().st_size,
            }
            for path in report_paths
        ],
    }
    write_json_atomic(manifest_path, manifest)
    return [*report_paths, manifest_path]


def _render_phase1_markdown(audit: dict[str, Any]) -> str:
    formal = audit["gates"]["formalExecution"]
    locked = audit["gates"]["lockedOosAdmission"]
    lines = [
        "# V13.27.1.17 Phase 1 Readiness Audit",
        "",
        f"- Route: `{audit['route']}`",
        f"- Candidate: `{audit['candidateId']}`",
        f"- Formal execution gate: `{formal['status']}`",
        f"- Locked OOS admission gate: `{locked['status']}`",
        f"- Preregistration published: `{str(audit['preregistration']['published']).lower()}`",
        "- Formal results produced: `0`",
        "- Locked OOS access count: `0`",
        "",
        "## Formal execution blockers",
        "",
    ]
    lines.extend(
        [f"- `{item['code']}`: {item['message']}" for item in formal["blockers"]]
        or ["- None"]
    )
    lines.extend(["", "## Locked OOS admission blockers", ""])
    lines.extend(
        [f"- `{item['code']}`: {item['message']}" for item in locked["blockers"]]
        or ["- None"]
    )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            (
                "A missing clean Locked OOS blocks only one-shot admission. It does not "
                "invalidate a separately preregistered formal Walk-forward research run."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def write_phase1_evidence_bundle(audit: dict[str, Any], output_root: Path) -> list[Path]:
    output_root = Path(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    readiness_json = output_root / "phase1_readiness_audit.json"
    readiness_md = output_root / "phase1_readiness_audit.md"
    holdout_json = output_root / "holdout_lineage_audit.json"
    holdout_md = output_root / "holdout_lineage_audit.md"
    manifest_path = output_root / "artifact_manifest.json"

    write_json_atomic(readiness_json, audit)
    readiness_md.write_text(_render_phase1_markdown(audit), encoding="utf-8")
    write_json_atomic(holdout_json, audit["holdoutLineage"])
    holdout_md.write_text(_render_holdout_markdown(audit["holdoutLineage"]), encoding="utf-8")
    report_paths = [readiness_json, readiness_md, holdout_json, holdout_md]
    logical_roles = {
        "phase1_readiness_audit.json": "phase1ReadinessJson",
        "phase1_readiness_audit.md": "phase1ReadinessMarkdown",
        "holdout_lineage_audit.json": "holdoutLineageJson",
        "holdout_lineage_audit.md": "holdoutLineageMarkdown",
    }
    manifest = {
        "schemaVersion": "formal_validation_phase1_manifest_v1",
        "artifacts": [
            {
                "logicalRole": logical_roles[path.name],
                "path": path.name,
                "sha256": sha256_file(path),
                "sizeBytes": path.stat().st_size,
            }
            for path in report_paths
        ],
    }
    write_json_atomic(manifest_path, manifest)
    return [*report_paths, manifest_path]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("reports/formal_validation/v13_27_1_17_s01_readiness_audit"),
    )
    args = parser.parse_args()
    repo_root = args.repo_root.resolve()
    output_root = args.output_root
    if not output_root.is_absolute():
        output_root = repo_root / output_root
    audit = build_phase0_readiness_audit(repo_root)
    paths = write_phase0_evidence_bundle(audit, output_root)
    print(
        json.dumps(
            {
                "route": audit["route"],
                "blockerCount": len(audit["blockers"]),
                "outputRoot": str(output_root),
                "artifacts": [path.name for path in paths],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
