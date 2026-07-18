"""Mechanical freshness and integrity classification for V34C public data."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from alphapilot.data_foundation.checkpoint import load_json, write_json_atomic
from alphapilot.data_foundation.okx_official_v1 import OkxOfficialV1Layout
from alphapilot.data_foundation.okx_official_v1_schedule import (
    OkxPublicCollectionPolicy,
    SchedulerStatePolicyMismatch,
    SchedulerStateStore,
)
from alphapilot.evolution.registry.hashing import sha256_file, stable_hash


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed.astimezone(UTC)


@dataclass(frozen=True)
class StreamQuality:
    task_name: str
    status: str
    next_due_at: str | None
    lateness_seconds: int
    consecutive_failures: int
    artifact_count: int
    row_count: int


@dataclass(frozen=True)
class QualityReport:
    schema_version: str
    evaluated_at: str
    policy_hash: str
    status: str
    reasons: tuple[str, ...]
    streams: tuple[StreamQuality, ...]
    artifact_count: int
    artifact_bytes: int

    @property
    def quality_hash(self) -> str:
        return stable_hash(asdict(self), prefix="v34c_quality")

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "qualityHash": self.quality_hash}


class OkxOfficialV1QualityMonitor:
    def __init__(
        self,
        *,
        warehouse_root: Path | str,
        policy: OkxPublicCollectionPolicy,
        state_store: SchedulerStateStore,
    ) -> None:
        self.layout = OkxOfficialV1Layout.from_warehouse(warehouse_root)
        self.policy = policy
        self.state_store = state_store
        self.index_path = self.layout.manifestRoot / "v34c" / "artifact_index.json"

    def evaluate(self, *, now: str) -> QualityReport:
        current_time = _parse_utc(now)
        reasons: list[str] = []
        blocked_reasons: list[str] = []
        degraded_reasons: list[str] = []
        warning_reasons: list[str] = []
        try:
            state = self.state_store.load_or_initialize(now=now)
        except SchedulerStatePolicyMismatch:
            state = {"tasks": {}}
            blocked_reasons.append("scheduler_policy_hash_mismatch")

        entries, index_reasons = self._load_and_validate_artifacts()
        blocked_reasons.extend(index_reasons)
        artifact_counts: dict[str, int] = {}
        row_counts: dict[str, int] = {}
        artifact_bytes = 0
        for entry in entries:
            task_name = str(entry.get("taskName") or "unknown")
            artifact_counts[task_name] = artifact_counts.get(task_name, 0) + 1
            row_counts[task_name] = row_counts.get(task_name, 0) + int(
                entry.get("rowCount") or 0
            )
            path = Path(str(entry.get("path") or ""))
            if path.is_file():
                artifact_bytes += path.stat().st_size

        streams: list[StreamQuality] = []
        task_state = state.get("tasks") if isinstance(state, dict) else {}
        if not isinstance(task_state, dict):
            blocked_reasons.append("scheduler_task_state_invalid")
            task_state = {}
        for task in self.policy.tasks:
            details = task_state.get(task.name)
            if not isinstance(details, dict):
                blocked_reasons.append(f"scheduler_task_state_missing:{task.name}")
                streams.append(
                    StreamQuality(task.name, "blocked", None, 0, 0, 0, 0)
                )
                continue
            next_due_at = details.get("nextDueAt")
            try:
                due_time = _parse_utc(str(next_due_at))
            except (TypeError, ValueError):
                blocked_reasons.append(f"task_due_timestamp_invalid:{task.name}")
                due_time = current_time
                next_due_at = None
            lateness = max(0, int((current_time - due_time).total_seconds()))
            failures = int(details.get("consecutiveFailures") or 0)
            stream_status = "healthy"
            if lateness > task.interval_seconds * 4:
                degraded_reasons.append(f"task_severely_overdue:{task.name}")
                stream_status = "degraded"
            elif lateness > 0:
                warning_reasons.append(f"task_overdue:{task.name}")
                stream_status = "warning"
            if failures >= task.max_consecutive_failures:
                degraded_reasons.append(f"task_repeated_failures:{task.name}")
                stream_status = "degraded"
            elif failures > 0:
                warning_reasons.append(f"task_recoverable_failure:{task.name}")
                if stream_status == "healthy":
                    stream_status = "warning"
            streams.append(
                StreamQuality(
                    task_name=task.name,
                    status=stream_status,
                    next_due_at=str(next_due_at) if next_due_at else None,
                    lateness_seconds=lateness,
                    consecutive_failures=failures,
                    artifact_count=artifact_counts.get(task.name, 0),
                    row_count=row_counts.get(task.name, 0),
                )
            )

        if blocked_reasons:
            status = "blocked"
            reasons.extend(blocked_reasons)
        elif degraded_reasons:
            status = "degraded"
            reasons.extend(degraded_reasons)
            reasons.extend(warning_reasons)
        elif warning_reasons:
            status = "warning"
            reasons.extend(warning_reasons)
        else:
            status = "healthy"
        return QualityReport(
            schema_version="okx_official_v1_v34c_quality_report_v1",
            evaluated_at=now,
            policy_hash=self.policy.policy_hash,
            status=status,
            reasons=tuple(dict.fromkeys(reasons)),
            streams=tuple(streams),
            artifact_count=len(entries),
            artifact_bytes=artifact_bytes,
        )

    def _load_and_validate_artifacts(self) -> tuple[list[dict[str, Any]], list[str]]:
        index = load_json(self.index_path)
        if not index:
            return [], []
        if (
            index.get("schemaVersion")
            != "okx_official_v1_v34c_artifact_index_v1"
            or index.get("appendOnly") is not True
            or not isinstance(index.get("entries"), list)
        ):
            return [], ["artifact_index_schema_invalid"]
        entries = [entry for entry in index["entries"] if isinstance(entry, dict)]
        reasons: list[str] = []
        for entry in entries:
            task_name = str(entry.get("taskName") or "unknown")
            path = Path(str(entry.get("path") or ""))
            expected_hash = str(entry.get("sha256") or "")
            if not path.is_file():
                reasons.append(f"artifact_missing:{task_name}")
                continue
            try:
                path.resolve().relative_to(self.layout.root.resolve())
            except ValueError:
                reasons.append(f"artifact_outside_warehouse:{task_name}")
                continue
            if len(expected_hash) != 64 or sha256_file(path) != expected_hash:
                reasons.append(f"artifact_hash_mismatch:{task_name}")
                continue
            reasons.extend(self._validate_artifact_schema(task_name, path))
        return entries, reasons

    @staticmethod
    def _validate_artifact_schema(task_name: str, path: Path) -> list[str]:
        if path.suffix == ".parquet":
            try:
                frame = pd.read_parquet(path)
            except (OSError, ValueError):
                return [f"artifact_schema_invalid:{task_name}"]
            required = {
                "instrumentId",
                "fundingTime",
                "realizedRateAvailableAt",
                "retrievedAt",
                "sourceHash",
                "sourceEndpoint",
                "observedAt",
            }
            if not required.issubset(frame.columns):
                return [f"artifact_provenance_invalid:{task_name}"]
            for row in frame.to_dict(orient="records"):
                try:
                    available_at = _parse_utc(str(row["realizedRateAvailableAt"]))
                    funding_at = datetime.fromtimestamp(
                        int(row["fundingTime"]) / 1000,
                        tz=UTC,
                    )
                except (TypeError, ValueError, OverflowError):
                    return [f"artifact_causal_schema_invalid:{task_name}"]
                if available_at < funding_at:
                    return [f"artifact_causal_schema_invalid:{task_name}"]
            return []
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return [f"artifact_schema_invalid:{task_name}"]
        if payload.get("publicDataOnly") is not True:
            return [f"artifact_public_boundary_invalid:{task_name}"]
        records = payload.get("records")
        if not isinstance(records, list):
            return [f"artifact_schema_invalid:{task_name}"]
        if task_name == "instrument_metadata":
            if not str(payload.get("sourceEndpoint") or "").startswith("/api/v5/"):
                return [f"artifact_provenance_invalid:{task_name}"]
            if len(str(payload.get("sourceResponseHash") or "")) != 64:
                return [f"artifact_provenance_invalid:{task_name}"]
            return []
        for record in records:
            if not isinstance(record, dict):
                return [f"artifact_schema_invalid:{task_name}"]
            if not str(record.get("sourceEndpoint") or "").startswith("/api/v5/"):
                return [f"artifact_provenance_invalid:{task_name}"]
            if len(str(record.get("sourceHash") or "")) != 64:
                return [f"artifact_provenance_invalid:{task_name}"]
            if not record.get("retrievedAt") or not record.get("observedAt"):
                return [f"artifact_provenance_invalid:{task_name}"]
        return []

    def write_report(self, report: QualityReport) -> dict[str, str]:
        root = (
            self.layout.auditRoot
            / "v34c"
            / "quality"
            / report.evaluated_at[:10]
        )
        json_path = root / f"quality-{report.quality_hash}.json"
        markdown_path = root / f"quality-{report.quality_hash}.md"
        payload = report.to_dict()
        if json_path.is_file():
            if json.loads(json_path.read_text(encoding="utf-8")) != payload:
                raise RuntimeError("v34c_quality_json_identity_mismatch")
        else:
            write_json_atomic(json_path, payload)
        markdown = self._markdown(report)
        if markdown_path.is_file():
            if markdown_path.read_text(encoding="utf-8") != markdown:
                raise RuntimeError("v34c_quality_markdown_identity_mismatch")
        else:
            markdown_path.parent.mkdir(parents=True, exist_ok=True)
            markdown_path.write_text(markdown, encoding="utf-8", newline="\n")
        return {
            "jsonPath": str(json_path.resolve()),
            "jsonSha256": sha256_file(json_path),
            "markdownPath": str(markdown_path.resolve()),
            "markdownSha256": sha256_file(markdown_path),
        }

    @staticmethod
    def _markdown(report: QualityReport) -> str:
        reason_text = ", ".join(report.reasons) if report.reasons else "none"
        rows = [
            "# V34C Public Data Quality",
            "",
            f"- Status: `{report.status}`",
            f"- Evaluated at: `{report.evaluated_at}`",
            f"- Policy hash: `{report.policy_hash}`",
            f"- Quality hash: `{report.quality_hash}`",
            f"- Reasons: `{reason_text}`",
            f"- Artifacts: `{report.artifact_count}`",
            f"- Artifact bytes: `{report.artifact_bytes}`",
            "",
            "| Stream | Status | Next due | Late seconds | Failures | Artifacts | Rows |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: |",
        ]
        rows.extend(
            "| {task} | {status} | {due} | {late} | {failures} | {artifacts} | {count} |".format(
                task=stream.task_name,
                status=stream.status,
                due=stream.next_due_at or "--",
                late=stream.lateness_seconds,
                failures=stream.consecutive_failures,
                artifacts=stream.artifact_count,
                count=stream.row_count,
            )
            for stream in report.streams
        )
        return "\n".join(rows) + "\n"
