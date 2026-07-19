"""Funding-aware freeze gate for the two V36 TSMOM Formal candidates."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import pandas as pd

from alphapilot.evolution.registry.hashing import sha256_file, stable_hash

from .tsmom_engine import TSMOM_SYMBOLS, build_tsmom_candidate_spec


_TIMEFRAME_INTERVALS = {
    "4h": pd.Timedelta(hours=4),
    "1dutc": pd.Timedelta(days=1),
}
_FUNDING_MAX_GAP = pd.Timedelta(hours=8)


class TsmomFormalReadinessError(RuntimeError):
    """Raised when the readiness audit input is malformed."""


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise TsmomFormalReadinessError(f"snapshot_manifest_missing:{path}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TsmomFormalReadinessError("snapshot_manifest_not_object")
    return value


def _utc(value: object, *, field: str) -> pd.Timestamp:
    parsed = pd.Timestamp(value)
    if parsed.tzinfo is None:
        parsed = parsed.tz_localize("UTC")
    else:
        parsed = parsed.tz_convert("UTC")
    if pd.isna(parsed):
        raise TsmomFormalReadinessError(f"timestamp_invalid:{field}")
    return parsed


def _iso(value: pd.Timestamp | None) -> str | None:
    return value.isoformat() if value is not None else None


def _partition_index(path: Path) -> pd.DatetimeIndex:
    try:
        frame = pd.read_parquet(path, columns=["date"])
        values = pd.to_datetime(frame["date"], utc=True, errors="coerce")
    except (KeyError, ValueError):
        frame = pd.read_parquet(path, columns=["timestamp_ms"])
        values = pd.to_datetime(
            pd.to_numeric(frame["timestamp_ms"], errors="coerce"),
            unit="ms",
            utc=True,
            errors="coerce",
        )
    if values.isna().any():
        raise TsmomFormalReadinessError(f"ohlcv_timestamp_invalid:{path}")
    index = pd.DatetimeIndex(values).sort_values().drop_duplicates()
    if index.empty:
        raise TsmomFormalReadinessError(f"ohlcv_partition_empty:{path}")
    return index


def _funding_frame(paths: Iterable[Path], *, symbol: str) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_parquet(path)
        timestamp_column = next(
            (
                column
                for column in ("timestamp_ms", "fundingTime", "date")
                if column in frame.columns
            ),
            None,
        )
        rate_column = next(
            (
                column
                for column in ("funding_rate", "fundingRate")
                if column in frame.columns
            ),
            None,
        )
        if timestamp_column is None or rate_column is None:
            continue
        selected = frame[[timestamp_column, rate_column]].rename(
            columns={timestamp_column: "timestamp", rate_column: "fundingRate"}
        )
        if "instrument_id" in frame.columns:
            instruments = set(frame["instrument_id"].dropna().astype(str))
            if instruments and instruments != {symbol}:
                continue
        selected["sourceEndpoint"] = (
            frame["source_endpoint"].astype(str)
            if "source_endpoint" in frame.columns
            else ""
        )
        frames.append(selected)
    if not frames:
        return pd.DataFrame(
            columns=["timestamp", "fundingRate", "sourceEndpoint"]
        )
    result = pd.concat(frames, ignore_index=True)
    if pd.api.types.is_numeric_dtype(result["timestamp"]):
        result["timestamp"] = pd.to_datetime(
            pd.to_numeric(result["timestamp"], errors="coerce"),
            unit="ms",
            utc=True,
            errors="coerce",
        )
    else:
        result["timestamp"] = pd.to_datetime(
            result["timestamp"], utc=True, errors="coerce"
        )
    result["fundingRate"] = pd.to_numeric(
        result["fundingRate"], errors="coerce"
    )
    return (
        result.dropna(subset=["timestamp"])
        .sort_values("timestamp")
        .drop_duplicates("timestamp", keep="last")
        .reset_index(drop=True)
    )


def _is_okx_endpoint(value: str) -> bool:
    normalized = str(value or "").strip().lower()
    return normalized.startswith("https://") and "okx.com/" in normalized


def _candidate_readiness(
    *,
    candidate_id: str,
    partitions: Mapping[tuple[str, str], Mapping[str, Any]],
    funding_root: Path,
    formal_start: pd.Timestamp,
    fold_count: int,
    minimum_test_bars: int,
) -> dict[str, Any]:
    candidate = build_tsmom_candidate_spec(candidate_id)
    definition = dict(candidate["definition"])
    timeframe = str(candidate["timeframe"])
    interval = _TIMEFRAME_INTERVALS.get(timeframe)
    if interval is None:
        raise TsmomFormalReadinessError(f"timeframe_unsupported:{timeframe}")

    blockers: list[str] = []
    indexes: dict[str, pd.DatetimeIndex] = {}
    partition_evidence: list[dict[str, Any]] = []
    for symbol in TSMOM_SYMBOLS:
        reference = partitions.get((symbol, timeframe))
        if not reference:
            blockers.append("ohlcv_partition_missing")
            continue
        path = Path(str(reference.get("outputPath") or ""))
        expected_hash = str(reference.get("outputSha256") or "")
        if not path.is_file():
            blockers.append("ohlcv_partition_missing")
            continue
        actual_hash = sha256_file(path)
        if not expected_hash or actual_hash != expected_hash:
            blockers.append("ohlcv_partition_hash_mismatch")
            continue
        index = _partition_index(path)
        index = index[index >= formal_start]
        if index.empty:
            blockers.append("ohlcv_formal_window_empty")
            continue
        indexes[symbol] = index
        partition_evidence.append(
            {
                "instrumentId": symbol,
                "timeframe": timeframe,
                "path": str(path),
                "sha256": actual_hash,
                "firstTimestamp": index[0].isoformat(),
                "lastTimestamp": index[-1].isoformat(),
                "rowCount": len(index),
                "contentColumnsRead": ["date_or_timestamp_ms"],
            }
        )

    common_index = pd.DatetimeIndex([])
    if len(indexes) == len(TSMOM_SYMBOLS):
        common_index = indexes[TSMOM_SYMBOLS[0]]
        exact_common_index = all(
            common_index.equals(indexes[symbol]) for symbol in TSMOM_SYMBOLS[1:]
        )
        if not exact_common_index:
            blockers.append("ohlcv_common_index_mismatch")
            for symbol in TSMOM_SYMBOLS[1:]:
                common_index = common_index.intersection(indexes[symbol])

    warmup_bars = max(
        int(definition["lookbackBars"]),
        int(definition["entryDonchianBars"]),
        int(definition["atrBars"]),
    )
    purge_bars = int(definition["maximumHoldBars"])
    required_bars = warmup_bars + fold_count * (purge_bars + minimum_test_bars)
    available_bars = len(common_index)
    if available_bars < required_bars:
        blockers.append("purged_walk_forward_capacity_insufficient")

    cutoff_exclusive = (
        common_index[-1] + interval if not common_index.empty else None
    )
    funding_rows: list[dict[str, Any]] = []
    funding_full = True
    funding_provenance = True
    funding_contiguous = True
    for symbol in TSMOM_SYMBOLS:
        paths = sorted((funding_root / symbol).rglob("*.parquet"))
        frame = _funding_frame(paths, symbol=symbol)
        if frame.empty:
            funding_rows.append(
                {
                    "instrumentId": symbol,
                    "fileCount": len(paths),
                    "rowCount": 0,
                    "firstTimestamp": None,
                    "lastTimestamp": None,
                    "maximumGapHours": None,
                    "fullWindowCovered": False,
                    "provenanceValid": False,
                    "zeroFilled": False,
                }
            )
            funding_full = False
            funding_provenance = False
            funding_contiguous = False
            continue
        valid_rates = frame["fundingRate"].notna().all()
        endpoints = sorted(set(frame["sourceEndpoint"].astype(str)))
        provenance_valid = bool(endpoints) and all(
            _is_okx_endpoint(endpoint) for endpoint in endpoints
        )
        gaps = frame["timestamp"].diff().dropna()
        maximum_gap = gaps.max() if not gaps.empty else pd.Timedelta(0)
        contiguous = bool(valid_rates and maximum_gap <= _FUNDING_MAX_GAP)
        full_window = bool(
            cutoff_exclusive is not None
            and frame.iloc[0]["timestamp"] <= formal_start
            and frame.iloc[-1]["timestamp"]
            >= cutoff_exclusive - _FUNDING_MAX_GAP
        )
        funding_rows.append(
            {
                "instrumentId": symbol,
                "fileCount": len(paths),
                "rowCount": len(frame),
                "firstTimestamp": frame.iloc[0]["timestamp"].isoformat(),
                "lastTimestamp": frame.iloc[-1]["timestamp"].isoformat(),
                "maximumGapHours": float(maximum_gap / pd.Timedelta(hours=1)),
                "fullWindowCovered": full_window,
                "provenanceValid": provenance_valid,
                "zeroFilled": False,
            }
        )
        funding_full = funding_full and full_window
        funding_provenance = funding_provenance and provenance_valid
        funding_contiguous = funding_contiguous and contiguous

    if any(row["rowCount"] == 0 for row in funding_rows):
        blockers.append("funding_evidence_missing")
    if not funding_provenance:
        blockers.append("funding_provenance_invalid")
    if not funding_contiguous and not any(
        row["rowCount"] == 0 for row in funding_rows
    ):
        blockers.append("funding_schedule_incomplete")
    if not funding_full and not any(
        row["rowCount"] == 0 for row in funding_rows
    ):
        blockers.append("funding_window_incomplete")

    blockers = sorted(set(blockers))
    return {
        "candidateId": candidate_id,
        "selectedTrialId": candidate["selectedTrialId"],
        "strategyDefinitionHash": candidate["strategyDefinitionHash"],
        "exitPolicyHash": candidate["exitPolicyHash"],
        "timeframe": timeframe,
        "status": "ready" if not blockers else "blocked",
        "blockers": blockers,
        "formalWindow": {
            "start": formal_start.isoformat(),
            "cutoffExclusive": _iso(cutoff_exclusive),
            "metadataOnlyAudit": True,
        },
        "ohlcvCoverage": {
            "instrumentCount": len(indexes),
            "commonRowCount": available_bars,
            "partitions": partition_evidence,
        },
        "walkForwardCapacity": {
            "foldCount": fold_count,
            "warmupBars": warmup_bars,
            "purgeBarsPerFold": purge_bars,
            "minimumTestBarsPerFold": minimum_test_bars,
            "requiredBars": required_bars,
            "availableBars": available_bars,
            "sufficient": available_bars >= required_bars,
        },
        "fundingCoverage": {
            "required": True,
            "sameExchangeRequired": True,
            "maximumAllowedGapHours": 8,
            "fullWindowCovered": funding_full,
            "provenanceValid": funding_provenance,
            "scheduleComplete": funding_contiguous,
            "zeroFilled": False,
            "instruments": funding_rows,
        },
    }


def build_tsmom_formal_readiness(
    *,
    snapshot_manifest_path: Path,
    funding_root: Path,
    candidate_ids: Sequence[str],
    formal_start: object,
    fold_count: int = 3,
    minimum_test_bars: int = 60,
    generated_at: str | None = None,
    campaign_id: str | None = None,
    source_commit: str | None = None,
    source_branch: str | None = None,
) -> dict[str, Any]:
    """Audit Formal metadata and fail closed before preregistration or input reads."""

    if fold_count < 2 or minimum_test_bars < 1:
        raise TsmomFormalReadinessError("walk_forward_policy_invalid")
    manifest_path = Path(snapshot_manifest_path).resolve()
    manifest = _read_json(manifest_path)
    partitions = {
        (str(row.get("instrumentId")), str(row.get("timeframe"))): row
        for row in manifest.get("partitions", [])
        if isinstance(row, Mapping)
    }
    start = _utc(formal_start, field="formal_start")
    candidates = [
        _candidate_readiness(
            candidate_id=str(candidate_id),
            partitions=partitions,
            funding_root=Path(funding_root).resolve(),
            formal_start=start,
            fold_count=fold_count,
            minimum_test_bars=minimum_test_bars,
        )
        for candidate_id in candidate_ids
    ]
    ready_count = sum(row["status"] == "ready" for row in candidates)
    result: dict[str, Any] = {
        "schemaVersion": "v36_tsmom_formal_readiness_v1",
        "generatedAt": generated_at
        or datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "status": "ready" if ready_count == len(candidates) else "blocked",
        "campaignId": campaign_id,
        "sourceCommit": source_commit,
        "sourceBranch": source_branch,
        "snapshotManifestPath": str(manifest_path),
        "snapshotId": manifest.get("snapshotId"),
        "fundingRoot": str(Path(funding_root).resolve()),
        "formalStart": start.isoformat(),
        "candidateCount": len(candidates),
        "formalReadyCandidateCount": ready_count,
        "blockedCandidateCount": len(candidates) - ready_count,
        "candidates": candidates,
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
        "demoArm": False,
        "orderCount": 0,
        "zeroFillUsed": False,
        "mixedExchangeFundingUsed": False,
    }
    result["readinessHash"] = stable_hash(
        {
            key: value
            for key, value in result.items()
            if key not in {"generatedAt", "readinessHash"}
        },
        prefix="v36_tsmom_formal_readiness",
    )
    return result


def render_tsmom_formal_readiness_markdown(
    report: Mapping[str, Any],
) -> str:
    lines = [
        "# V36 TSMOM Formal data readiness",
        "",
        f"- Status: `{report.get('status')}`",
        f"- Snapshot: `{report.get('snapshotId')}`",
        f"- Formal start: `{report.get('formalStart')}`",
        f"- Ready candidates: `{report.get('formalReadyCandidateCount')}` / "
        f"`{report.get('candidateCount')}`",
        "- Missing funding is never zero-filled and mixed-exchange funding is not used.",
        "",
        "## Candidate audit",
        "",
        "| Candidate | Timeframe | Status | OHLCV bars | Required bars | Funding window | Blockers |",
        "| --- | --- | --- | ---: | ---: | --- | --- |",
    ]
    for candidate in report.get("candidates", []):
        walk = candidate.get("walkForwardCapacity") or {}
        funding = candidate.get("fundingCoverage") or {}
        blockers = ", ".join(candidate.get("blockers") or []) or "none"
        lines.append(
            "| "
            f"{candidate.get('candidateId')} | {candidate.get('timeframe')} | "
            f"{candidate.get('status')} | {walk.get('availableBars')} | "
            f"{walk.get('requiredBars')} | "
            f"{'complete' if funding.get('fullWindowCovered') else 'incomplete'} | "
            f"{blockers} |"
        )
        lines.extend(
            [
                "",
                f"### {candidate.get('candidateId')}",
                "",
                f"- Selected trial: `{candidate.get('selectedTrialId')}`",
                f"- Strategy definition hash: `{candidate.get('strategyDefinitionHash')}`",
                f"- Exit policy hash: `{candidate.get('exitPolicyHash')}`",
            ]
        )
        for row in funding.get("instruments", []):
            lines.append(
                "- Funding "
                f"`{row.get('instrumentId')}`: `{row.get('firstTimestamp')}` to "
                f"`{row.get('lastTimestamp')}`, rows `{row.get('rowCount')}`, "
                f"full window `{row.get('fullWindowCovered')}`, "
                f"provenance `{row.get('provenanceValid')}`."
            )
    lines.extend(
        [
            "",
            "## Safety counters",
            "",
            "| Counter | Value |",
            "| --- | ---: |",
            f"| Formal runs | {report.get('formalRunCount')} |",
            f"| Formal input reads | {report.get('formalInputReadCount')} |",
            f"| Result reads | {report.get('resultReadCount')} |",
            f"| Locked OOS access | {report.get('lockedOosAccessCount')} |",
            f"| Releases | {report.get('releaseCount')} |",
            f"| Orders | {report.get('orderCount')} |",
            "",
        ]
    )
    return "\n".join(lines)


def write_tsmom_formal_readiness_artifacts(
    report: Mapping[str, Any],
    *,
    output_dir: Path,
) -> dict[str, Path]:
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    json_path = output / "funding_data_readiness.json"
    markdown_path = output / "funding_data_readiness.md"
    json_path.write_text(
        json.dumps(dict(report), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(
        render_tsmom_formal_readiness_markdown(report), encoding="utf-8"
    )
    allowed = report.get("status") == "ready"
    preflight = {
        "schemaVersion": "v36_tsmom_formal_preflight_v1",
        "status": "ready_to_preregister" if allowed else "blocked_before_preregistration",
        "readinessHash": report.get("readinessHash"),
        "allowedToCreatePreregistration": allowed,
        "allowedToRunFormal": False,
        "blockedCandidates": [
            {
                "candidateId": candidate.get("candidateId"),
                "blockers": candidate.get("blockers") or [],
            }
            for candidate in report.get("candidates", [])
            if candidate.get("status") != "ready"
        ],
        "formalRunCount": 0,
        "formalInputReadCount": 0,
        "resultReadCount": 0,
        "lockedOosAccessCount": 0,
        "releaseCount": 0,
    }
    preflight_path = output / "formal_preflight.json"
    preflight_path.write_text(
        json.dumps(preflight, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    manifest: dict[str, Any] = {
        "schemaVersion": "v36_tsmom_formal_readiness_manifest_v1",
        "status": report.get("status"),
        "readinessHash": report.get("readinessHash"),
        "formalRunCount": report.get("formalRunCount"),
        "formalInputReadCount": report.get("formalInputReadCount"),
        "resultReadCount": report.get("resultReadCount"),
        "lockedOosAccessCount": report.get("lockedOosAccessCount"),
        "releaseCount": report.get("releaseCount"),
        "artifacts": [
            {
                "path": json_path.name,
                "sha256": sha256_file(json_path),
            },
            {
                "path": markdown_path.name,
                "sha256": sha256_file(markdown_path),
            },
            {
                "path": preflight_path.name,
                "sha256": sha256_file(preflight_path),
            },
        ],
    }
    manifest_path = output / "artifact_manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        json_path.name: json_path,
        markdown_path.name: markdown_path,
        preflight_path.name: preflight_path,
        manifest_path.name: manifest_path,
    }
