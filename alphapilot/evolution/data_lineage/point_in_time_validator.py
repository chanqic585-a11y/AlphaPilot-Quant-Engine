"""Fail-closed point-in-time checks for factor inputs and universes."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


SYMBOLIC_AVAILABILITY_POLICIES = {
    "bar_open",
    "bar_close",
    "candle_open",
    "candle_close",
    "previous_bar_close",
    "publication_time",
    "snapshot_time",
    "event_time",
    "known_at_observation",
}


@dataclass(frozen=True)
class FieldAvailability:
    name: str
    role: str = "feature"
    availableAt: str | None = None
    delayBars: int | None = None
    relativeOffsetBars: int = 0
    source: str = "local_research"


@dataclass(frozen=True)
class DynamicUniverseEvidence:
    enabled: bool = False
    snapshotId: str | None = None
    snapshotAsOf: str | None = None


@dataclass(frozen=True)
class PointInTimeIssue:
    code: str
    message: str
    field: str | None = None


@dataclass(frozen=True)
class PointInTimeValidationResult:
    valid: bool
    issues: list[PointInTimeIssue]
    checkedFields: list[str]
    dynamicUniverseValidated: bool
    evaluationCutoff: str


def _parse_timestamp(value: str, *, label: str) -> datetime:
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"Invalid {label}: {value}") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone: {value}")
    return parsed.astimezone(UTC)


def _coerce_field(name: str, value: FieldAvailability | dict[str, Any]) -> FieldAvailability:
    if isinstance(value, FieldAvailability):
        return value
    return FieldAvailability(
        name=str(value.get("name") or name),
        role=str(value.get("role") or "feature"),
        availableAt=value.get("availableAt"),
        delayBars=value.get("delayBars"),
        relativeOffsetBars=int(value.get("relativeOffsetBars") or 0),
        source=str(value.get("source") or "local_research"),
    )


def _coerce_universe(
    value: DynamicUniverseEvidence | dict[str, Any] | None,
) -> DynamicUniverseEvidence:
    if value is None:
        return DynamicUniverseEvidence()
    if isinstance(value, DynamicUniverseEvidence):
        return value
    return DynamicUniverseEvidence(
        enabled=bool(value.get("enabled")),
        snapshotId=value.get("snapshotId"),
        snapshotAsOf=value.get("snapshotAsOf"),
    )


def validate_point_in_time(
    *,
    required_fields: list[str],
    field_metadata: dict[str, FieldAvailability | dict[str, Any]],
    evaluation_cutoff: str,
    data_snapshot_manifest: dict[str, Any] | None = None,
    dynamic_universe: DynamicUniverseEvidence | dict[str, Any] | None = None,
) -> PointInTimeValidationResult:
    cutoff = _parse_timestamp(evaluation_cutoff, label="evaluation_cutoff")
    issues: list[PointInTimeIssue] = []
    checked_fields = sorted(dict.fromkeys(required_fields))

    def add(code: str, message: str, field: str | None = None) -> None:
        issues.append(PointInTimeIssue(code, message, field))

    for field_name in checked_fields:
        raw_metadata = field_metadata.get(field_name)
        if raw_metadata is None:
            add(
                "missing_availability_metadata",
                f"Field {field_name} has no point-in-time availability metadata",
                field_name,
            )
            continue
        metadata = _coerce_field(field_name, raw_metadata)
        normalized_name = field_name.lower()
        if metadata.role.lower() in {"forward_label", "label", "target"} or normalized_name.startswith(
            ("forward_", "future_")
        ):
            add(
                "forward_label_as_factor_input",
                f"Forward label {field_name} cannot be used as a factor input",
                field_name,
            )
        if metadata.relativeOffsetBars > 0:
            add(
                "future_offset_forbidden",
                f"Field {field_name} references {metadata.relativeOffsetBars} future bars",
                field_name,
            )
        if metadata.delayBars is not None and metadata.delayBars < 0:
            add(
                "negative_publication_delay_forbidden",
                f"Field {field_name} has a negative availability delay",
                field_name,
            )
        if metadata.availableAt is None and metadata.delayBars is None:
            add(
                "missing_availability_rule",
                f"Field {field_name} requires availableAt or delayBars",
                field_name,
            )
        if metadata.availableAt:
            availability_policy = metadata.availableAt.lower()
            if availability_policy == "future":
                add(
                    "field_not_available_at_cutoff",
                    f"Field {field_name} is explicitly future-only",
                    field_name,
                )
            elif availability_policy not in SYMBOLIC_AVAILABILITY_POLICIES:
                try:
                    available_at = _parse_timestamp(
                        metadata.availableAt, label=f"{field_name} availableAt"
                    )
                except ValueError:
                    add(
                        "invalid_availability_policy",
                        f"Field {field_name} has an unknown availability policy",
                        field_name,
                    )
                else:
                    if available_at > cutoff:
                        add(
                            "field_not_available_at_cutoff",
                            f"Field {field_name} becomes available after the evaluation cutoff",
                            field_name,
                        )

    if data_snapshot_manifest is not None:
        snapshot_cutoff_value = data_snapshot_manifest.get("pointInTimeCutoff")
        if not snapshot_cutoff_value:
            add("data_snapshot_cutoff_required", "Data snapshot has no pointInTimeCutoff")
        else:
            try:
                snapshot_cutoff = _parse_timestamp(
                    str(snapshot_cutoff_value), label="data snapshot pointInTimeCutoff"
                )
            except ValueError:
                add("invalid_data_snapshot_cutoff", "Data snapshot cutoff is invalid")
            else:
                if snapshot_cutoff > cutoff:
                    add(
                        "data_snapshot_from_future",
                        "Data snapshot cutoff is after the evaluation cutoff",
                    )

    universe = _coerce_universe(dynamic_universe)
    universe_validated = not universe.enabled
    if universe.enabled:
        if not universe.snapshotId or not universe.snapshotAsOf:
            add(
                "dynamic_universe_snapshot_required",
                "Dynamic universe research requires a historical universe snapshot",
            )
        else:
            try:
                snapshot_as_of = _parse_timestamp(
                    universe.snapshotAsOf, label="dynamic universe snapshotAsOf"
                )
            except ValueError:
                add("invalid_dynamic_universe_snapshot_time", "Universe snapshot time is invalid")
            else:
                if snapshot_as_of > cutoff:
                    add(
                        "dynamic_universe_snapshot_from_future",
                        "Dynamic universe snapshot is after the evaluation cutoff",
                    )
                else:
                    universe_validated = True
            manifest_id = (data_snapshot_manifest or {}).get("dataSnapshotId")
            if manifest_id and manifest_id != universe.snapshotId:
                add(
                    "dynamic_universe_snapshot_mismatch",
                    "Dynamic universe snapshot does not match the registered data snapshot",
                )
                universe_validated = False

    return PointInTimeValidationResult(
        valid=not issues,
        issues=issues,
        checkedFields=checked_fields,
        dynamicUniverseValidated=universe_validated,
        evaluationCutoff=evaluation_cutoff,
    )
