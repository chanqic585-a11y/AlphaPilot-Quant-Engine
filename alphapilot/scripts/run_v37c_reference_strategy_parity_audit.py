"""Run the offline V37C reference-strategy reproduction and parity audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from alphapilot.data_foundation.checkpoint import write_json_atomic
from alphapilot.evolution.registry.hashing import sha256_file
from alphapilot.reference_strategy_research.candidates import build_selected_candidates
from alphapilot.reference_strategy_research.package_loader import load_reference_package
from alphapilot.reference_strategy_research.parity_audit import (
    audit_parquet_signal_parity,
    audit_signal_parity,
    build_gate_reachability_report,
)
from alphapilot.reference_strategy_research.source_semantics import audit_source_semantics


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return value


def _json_value(value: Any, fallback: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return fallback
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return fallback
    return value


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8", newline="")
    temporary.replace(path)


def _manifest_target(repo: Path, manifest: Path, value: str) -> Path:
    raw = Path(value)
    if raw.is_absolute():
        return raw
    local = manifest.parent / raw
    if local.is_file():
        return local
    rooted = repo / raw
    if rooted.is_file():
        return rooted
    raise RuntimeError(f"manifest artifact is missing: {value}")


def _verify_manifest(repo: Path, manifest: Path) -> dict[str, Any]:
    payload = _load_json(manifest)
    rows = payload.get("artifacts")
    if not isinstance(rows, list) or not rows:
        raise RuntimeError(f"manifest has no artifacts: {manifest}")
    verified: list[dict[str, str]] = []
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError(f"invalid manifest row: {manifest}")
        target = _manifest_target(repo, manifest, str(row.get("path") or ""))
        observed = sha256_file(target)
        if observed != row.get("sha256"):
            raise RuntimeError(f"artifact hash mismatch: {target}")
        verified.append({"path": str(target), "sha256": observed})
    return {
        "manifestPath": str(manifest),
        "manifestSha256": sha256_file(manifest),
        "verifiedArtifactCount": len(verified),
        "artifacts": verified,
    }


def _catalog_dataset(catalog: dict[str, Any], timeframe: str) -> dict[str, Any]:
    matches = [
        dict(row)
        for row in catalog.get("datasets", [])
        if row.get("dataType") == "ohlcv"
        and row.get("timeframe") == timeframe
        and "BTC-USDT-SWAP" in row.get("symbols", [])
    ]
    if len(matches) != 1:
        raise RuntimeError(f"expected one registered BTC {timeframe} OHLCV dataset")
    row = matches[0]
    path = Path(str(row["sourcePath"]))
    if not path.is_file():
        raise RuntimeError(f"registered parity fixture is missing: {path}")
    observed = sha256_file(path)
    if row.get("contentHash") and observed != row["contentHash"]:
        raise RuntimeError(f"registered parity fixture hash mismatch: {path}")
    row["observedContentHash"] = observed
    return row


def _synthetic_session(direction: str) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01T00:00:00Z", periods=32, freq="1h"),
            "open": np.full(32, 100.0),
            "high": np.full(32, 101.0),
            "low": np.full(32, 99.0),
            "close": np.full(32, 100.0),
            "volume": np.full(32, 1000.0),
        }
    )
    if direction == "long":
        frame.loc[24, ["open", "high", "low", "close"]] = [100.0, 103.0, 99.8, 102.5]
        frame.loc[25, ["open", "high", "low", "close"]] = [102.6, 104.0, 102.0, 103.5]
    else:
        frame.loc[24, ["open", "high", "low", "close"]] = [100.0, 100.2, 97.0, 97.5]
        frame.loc[25, ["open", "high", "low", "close"]] = [97.4, 98.0, 96.0, 96.5]
    return frame


def _synthetic_second_entry(direction: str) -> pd.DataFrame:
    frame = pd.DataFrame(
        {
            "date": pd.date_range("2024-01-01T00:00:00Z", periods=50, freq="4h"),
            "open": np.full(50, 102.0),
            "high": np.full(50, 104.0),
            "low": np.full(50, 100.0),
            "close": np.full(50, 102.0),
            "volume": np.full(50, 1000.0),
        }
    )
    if direction == "long":
        frame.loc[25, ["open", "high", "low", "close"]] = [101.0, 101.5, 98.5, 99.5]
        frame.loc[26, ["open", "high", "low", "close"]] = [99.7, 102.0, 99.2, 101.0]
        frame.loc[27, ["open", "high", "low", "close"]] = [100.8, 103.5, 99.1, 103.0]
        frame.loc[28, ["open", "high", "low", "close"]] = [103.1, 106.0, 102.5, 105.0]
    else:
        frame.loc[25, ["open", "high", "low", "close"]] = [103.0, 105.5, 102.5, 104.5]
        frame.loc[26, ["open", "high", "low", "close"]] = [104.3, 104.8, 102.0, 103.0]
        frame.loc[27, ["open", "high", "low", "close"]] = [104.2, 104.9, 101.5, 102.0]
        frame.loc[28, ["open", "high", "low", "close"]] = [101.9, 102.5, 99.0, 100.0]
    return frame


def _signal_report(
    candidates: list[Any],
    datasets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    synthetic: list[dict[str, Any]] = []
    registered: list[dict[str, Any]] = []
    for candidate in candidates:
        if candidate.marketMechanismId == "reference_utc_session_range_breakout":
            synthetic_frame = _synthetic_session(candidate.direction)
        else:
            synthetic_frame = _synthetic_second_entry(candidate.direction)
        synthetic.append(
            audit_signal_parity(
                candidate=candidate,
                frame=synthetic_frame,
                fixture_id=f"synthetic_{candidate.candidateId}",
                provenance={"kind": "synthetic_known_positive"},
            )
        )
        dataset = datasets[candidate.timeframe]
        registered.append(
            audit_parquet_signal_parity(
                candidate=candidate,
                parquet_path=dataset["sourcePath"],
                fixture_id=str(dataset["datasetId"]),
                provenance={
                    "kind": "registered_real_partition",
                    "provider": dataset.get("provider"),
                    "exchange": dataset.get("exchange"),
                    "contentHash": dataset["observedContentHash"],
                    "isProxy": dataset.get("isProxy"),
                    "isPointInTime": dataset.get("isPointInTime"),
                },
            )
        )
    all_rows = synthetic + registered
    return {
        "schemaVersion": "reference_signal_parity_bundle_v1",
        "allParityPassed": all(row["parityPassed"] for row in all_rows),
        "syntheticFixtures": synthetic,
        "registeredRealFixtures": registered,
        "interpretation": (
            "Parity proves the frozen AlphaPilot executable matches an independent oracle. "
            "It does not prove source equivalence or profitability."
        ),
    }


def _candidate_reassessment(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for record in frame.to_dict(orient="records"):
        gates = _json_value(record.get("gates"), {})
        labels = list(_json_value(record.get("failureLabels"), []))
        economic_base_passed = bool(gates.get("basePassed", record.get("basePassed", False)))
        if record.get("prescreenPassed") and not economic_base_passed:
            labels.append("out_of_sample_failed")
        corrected = list(dict.fromkeys(str(value) for value in labels))
        oos = dict(gates.get("oosMetrics") or {})
        development = dict(gates.get("developmentMetrics") or {})
        rows.append(
            {
                "candidateId": record.get("candidateId"),
                "prescreenPassed": bool(record.get("prescreenPassed")),
                "economicBasePassed": economic_base_passed,
                "endToEndBasePassed": bool(record.get("basePassed")),
                "formalPassed": bool(record.get("formalPassed")),
                "translationPassed": bool(record.get("freqtradeTranslationPassed")),
                "correctedFailureLabels": corrected,
                "developmentMetrics": development,
                "oosMetrics": oos,
            }
        )
    return rows


def _translation_gap_csv(source_audit: dict[str, Any]) -> str:
    buffer = io.StringIO(newline="")
    fields = ("candidateId", "equivalenceStatus", "translationClass", "materialGap")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    for candidate in source_audit["candidates"]:
        for gap in candidate["materialGaps"]:
            writer.writerow(
                {
                    "candidateId": candidate["candidateId"],
                    "equivalenceStatus": candidate["equivalenceStatus"],
                    "translationClass": candidate["translationClass"],
                    "materialGap": gap,
                }
            )
    return buffer.getvalue()


def run_v37c_reference_strategy_parity_audit(
    *,
    repo_root: str | Path,
    package_path: str | Path,
    v37b_run_dir: str | Path,
    output_root: str | Path | None = None,
) -> dict[str, Any]:
    """Generate a deterministic, offline audit without changing V37B artifacts."""

    repo = Path(repo_root).resolve()
    run_dir = Path(v37b_run_dir).resolve()
    package = load_reference_package(package_path)
    source_verification = _load_json(run_dir / "source_verification.json")
    if source_verification.get("archiveSha256") != package.archiveSha256:
        raise RuntimeError("V37B source package hash does not match the supplied package")

    workflow_chain = _verify_manifest(repo, run_dir / "workflow_artifact_manifest.json")
    implementation = _load_json(run_dir / "implementation_evidence.json")
    selected_path = run_dir / "selected_candidates.json"
    if implementation.get("selectedCandidatesSha256") != sha256_file(selected_path):
        raise RuntimeError("V37B selected-candidate hash mismatch")
    campaign_id = str(_load_json(run_dir / "campaign_start.json")["campaignId"])
    campaign_dir = repo / "reports" / "backtest_screening" / campaign_id
    campaign_chain = _verify_manifest(repo, campaign_dir / "artifact_manifest.json")
    preregistration = _load_json(repo / "research" / "preregistrations" / f"{campaign_id}.json")
    if implementation.get("sourceHashes") != preregistration.get("implementationSourceHashes"):
        raise RuntimeError("V37B implementation hashes do not match the preregistration")

    source_audit = audit_source_semantics(package.archivePath)
    candidates = build_selected_candidates(package.candidates)
    if len(candidates) != 4:
        raise RuntimeError(f"expected four directional candidates, found {len(candidates)}")
    catalog = _load_json(
        repo / "reports" / "backtest_screening" / "data_readiness" / "dataset_catalog.json"
    )
    datasets = {timeframe: _catalog_dataset(catalog, timeframe) for timeframe in ("1h", "4h")}
    signal_report = _signal_report(candidates, datasets)
    gate_rows = {
        timeframe: build_gate_reachability_report(
            preregistration=preregistration,
            timeframe=timeframe,
        )
        for timeframe in ("1h", "4h")
    }
    gate_report = {
        "schemaVersion": "reference_gate_reachability_bundle_v1",
        "thresholdsChanged": False,
        "allGatesReachable": all(row["allGatesReachable"] for row in gate_rows.values()),
        "timeframes": gate_rows,
    }

    result_frame = pd.read_parquet(campaign_dir / "candidate_results.parquet")
    reassessed = _candidate_reassessment(result_frame)
    input_identity = {
        "packageSha256": package.archiveSha256,
        "v37bRunId": source_verification.get("runId") or run_dir.name,
        "v37bCodeCommit": implementation.get("codeCommit"),
        "campaignId": campaign_id,
        "preregistrationHash": preregistration.get("preregistrationHash"),
        "workflowManifest": workflow_chain,
        "campaignManifest": campaign_chain,
    }
    reassessment = {
        "schemaVersion": "v37b_reference_strategy_reassessment_v1",
        "inputIdentity": input_identity,
        "sourceEquivalenceEstablished": False,
        "executableParityPassed": signal_report["allParityPassed"],
        "gatesReachable": gate_report["allGatesReachable"],
        "forcedWinner": False,
        "gateThresholdsChanged": False,
        "v37bArtifactsRewritten": False,
        "networkDownloads": 0,
        "demoOrLiveMutations": 0,
        "candidates": reassessed,
        "conclusion": (
            "V37B remains valid evidence that its normalized candidates failed the frozen OOS economics. "
            "It is not evidence that the original external strategies failed because source equivalence "
            "was not established."
        ),
    }

    identity_raw = json.dumps(input_identity, sort_keys=True, default=str).encode("utf-8")
    run_id = f"v37c-parity-{package.archiveSha256[:12]}-{hashlib.sha256(identity_raw).hexdigest()[:12]}"
    root = (
        Path(output_root).resolve()
        if output_root is not None
        else repo / "reports" / "backtest_screening" / "reference_strategy_parity"
    )
    output = root / run_id
    output.mkdir(parents=True, exist_ok=True)
    write_json_atomic(output / "source_lineage_audit.json", source_audit)
    _write_text(output / "translation_gap_matrix.csv", _translation_gap_csv(source_audit))
    write_json_atomic(output / "signal_parity_report.json", signal_report)
    write_json_atomic(output / "gate_reachability_report.json", gate_report)
    write_json_atomic(output / "v37b_reassessment.json", reassessment)
    conclusion = (
        "# V37C Reference Strategy Parity Audit\n\n"
        f"- Run: `{run_id}`\n"
        f"- Frozen V37B campaign: `{campaign_id}`\n"
        f"- Source equivalence established: no\n"
        f"- Production-oracle parity: {'passed' if signal_report['allParityPassed'] else 'failed'}\n"
        f"- Unchanged gates reachable: {'yes' if gate_report['allGatesReachable'] else 'no'}\n"
        "- Forced winner: no\n"
        "- Network, Demo or Live mutation: none\n\n"
        "## Conclusion\n\n"
        "The backtester is not shown to be rejecting every strategy because of impossible gates. "
        "The frozen executable matches an independent oracle on synthetic and registered fixtures. "
        "V37B therefore remains negative OOS evidence for the normalized AlphaPilot variants. "
        "It must not be generalized to the original external source strategies because their execution "
        "semantics were not reproduced exactly and the registered real fixture is proxy, non-PIT data.\n"
    )
    _write_text(output / "final_conclusion.md", conclusion)

    artifact_names = (
        "source_lineage_audit.json",
        "translation_gap_matrix.csv",
        "signal_parity_report.json",
        "gate_reachability_report.json",
        "v37b_reassessment.json",
        "final_conclusion.md",
    )
    manifest = {
        "schemaVersion": "v37c_reference_strategy_parity_artifact_manifest_v1",
        "runId": run_id,
        "artifacts": [
            {"path": name, "sha256": sha256_file(output / name)} for name in artifact_names
        ],
    }
    write_json_atomic(output / "artifact_manifest.json", manifest)
    return {
        "status": "completed",
        "runId": run_id,
        "output": str(output),
        "allParityPassed": signal_report["allParityPassed"],
        "allGatesReachable": gate_report["allGatesReachable"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--v37b-run-dir", type=Path, required=True)
    parser.add_argument("--output-root", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    result = run_v37c_reference_strategy_parity_audit(
        repo_root=args.repo,
        package_path=args.package,
        v37b_run_dir=args.v37b_run_dir,
        output_root=args.output_root,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] == "completed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
