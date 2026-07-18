"""Versioned public-data scheduling policy and durable scheduler state."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from alphapilot.data_foundation.checkpoint import load_json, write_json_atomic
from alphapilot.evolution.registry.hashing import stable_hash


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"Timestamp must include a timezone: {value}")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class TaskCadence:
    name: str
    interval_seconds: int
    retry_base_seconds: int
    max_consecutive_failures: int
    enabled: bool = True

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("Task cadence name cannot be empty")
        if self.interval_seconds <= 0:
            raise ValueError("Task cadence interval_seconds must be positive")
        if self.retry_base_seconds <= 0:
            raise ValueError("Task cadence retry_base_seconds must be positive")
        if self.max_consecutive_failures <= 0:
            raise ValueError("Task cadence max_consecutive_failures must be positive")


@dataclass(frozen=True)
class OkxPublicCollectionPolicy:
    schema_version: str
    tasks: tuple[TaskCadence, ...]
    instruments: tuple[str, ...]

    def __post_init__(self) -> None:
        task_names = tuple(task.name for task in self.tasks)
        if len(task_names) != len(set(task_names)):
            raise ValueError("Collection policy task names must be unique")
        if not self.instruments:
            raise ValueError("Collection policy requires at least one instrument")

    @classmethod
    def default(
        cls,
        instruments: tuple[str, ...] = (
            "BTC-USDT-SWAP",
            "ETH-USDT-SWAP",
            "SOL-USDT-SWAP",
        ),
    ) -> "OkxPublicCollectionPolicy":
        return cls(
            schema_version="v34c.public-data-schedule.v1",
            instruments=instruments,
            tasks=(
                TaskCadence("instrument_metadata", 86_400, 300, 3),
                TaskCadence("funding_increment", 3_600, 120, 3),
                TaskCadence("instrument_state", 3_600, 120, 3),
                TaskCadence("current_funding", 900, 60, 3),
                TaskCadence("open_interest", 900, 60, 3),
                TaskCadence("mark_price", 300, 30, 3),
                TaskCadence("index_price", 300, 30, 3),
                TaskCadence("ticker_spread", 300, 30, 3),
                TaskCadence("order_book_summary", 300, 30, 3),
                TaskCadence("quality", 900, 60, 3),
            ),
        )

    @property
    def policy_hash(self) -> str:
        return stable_hash(asdict(self), prefix="v34c_collection_policy")

    def with_interval(self, task_name: str, *, seconds: int) -> "OkxPublicCollectionPolicy":
        if seconds <= 0:
            raise ValueError("Task interval must be positive")
        found = False
        tasks: list[TaskCadence] = []
        for task in self.tasks:
            if task.name == task_name:
                tasks.append(replace(task, interval_seconds=seconds))
                found = True
            else:
                tasks.append(task)
        if not found:
            raise KeyError(f"Unknown scheduled task: {task_name}")
        return replace(self, tasks=tuple(tasks))


class SchedulerStatePolicyMismatch(RuntimeError):
    """Raised when durable state belongs to a different immutable policy."""


class SchedulerStateStore:
    def __init__(self, path: Path, *, policy: OkxPublicCollectionPolicy) -> None:
        self.path = Path(path)
        self.policy = policy

    def load_or_initialize(self, *, now: str) -> dict[str, Any]:
        _parse_utc(now)
        loaded = load_json(self.path)
        if loaded:
            if loaded.get("policyHash") != self.policy.policy_hash:
                raise SchedulerStatePolicyMismatch(
                    "Scheduler state policy hash does not match the active collection policy"
                )
            return loaded

        state: dict[str, Any] = {
            "schemaVersion": "v34c.scheduler-state.v1",
            "policySchemaVersion": self.policy.schema_version,
            "policyHash": self.policy.policy_hash,
            "instruments": list(self.policy.instruments),
            "createdAt": now,
            "updatedAt": now,
            "tasks": {
                task.name: {
                    "nextDueAt": now,
                    "lastStartedAt": None,
                    "lastCompletedAt": None,
                    "lastStatus": "due" if task.enabled else "disabled",
                    "lastError": None,
                    "consecutiveFailures": 0,
                }
                for task in self.policy.tasks
            },
        }
        self.save(state)
        return state

    def save(self, state: Mapping[str, Any]) -> None:
        if state.get("policyHash") != self.policy.policy_hash:
            raise SchedulerStatePolicyMismatch(
                "Refusing to persist scheduler state for a different policy"
            )
        write_json_atomic(self.path, dict(state))


def select_due_tasks(
    policy: OkxPublicCollectionPolicy,
    state: Mapping[str, Any],
    *,
    now: str,
) -> list[str]:
    current_time = _parse_utc(now)
    task_state = state.get("tasks", {})
    if not isinstance(task_state, Mapping):
        raise ValueError("Scheduler state tasks must be a mapping")

    due: list[tuple[datetime, int, str]] = []
    for policy_index, task in enumerate(policy.tasks):
        if not task.enabled:
            continue
        details = task_state.get(task.name)
        if not isinstance(details, Mapping):
            raise ValueError(f"Scheduler state is missing task: {task.name}")
        next_due_at = details.get("nextDueAt")
        if not isinstance(next_due_at, str):
            raise ValueError(f"Scheduler task {task.name} has no valid nextDueAt")
        due_time = _parse_utc(next_due_at)
        if due_time <= current_time:
            due.append((due_time, policy_index, task.name))
    return [task_name for _, _, task_name in sorted(due)]


class SchedulerLeaseUnavailable(RuntimeError):
    def __init__(self, owner_audit: Mapping[str, Any]) -> None:
        self.owner_audit = dict(owner_audit)
        super().__init__("Scheduler lease is already held")


class SchedulerLease:
    def __init__(self, path: Path, *, owner: str) -> None:
        if not owner:
            raise ValueError("Scheduler lease owner cannot be empty")
        self.path = Path(path)
        self.owner = owner
        self.acquired = False

    def acquire(self, *, acquired_at: str) -> None:
        _parse_utc(acquired_at)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schemaVersion": "v34c.scheduler-lease.v1",
            "owner": self.owner,
            "acquiredAt": acquired_at,
        }
        try:
            descriptor = os.open(
                self.path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
            )
        except FileExistsError as exc:
            raise SchedulerLeaseUnavailable(self._existing_owner_audit()) from exc
        try:
            encoded = json.dumps(payload, sort_keys=True).encode("utf-8")
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        self.acquired = True

    def release(self) -> None:
        if not self.acquired:
            return
        audit = self._existing_owner_audit()
        if audit.get("owner") != self.owner:
            raise SchedulerLeaseUnavailable(audit)
        self.path.unlink(missing_ok=False)
        self.acquired = False

    def _existing_owner_audit(self) -> dict[str, Any]:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"owner": "unknown", "acquiredAt": None}
        return {
            "owner": str(payload.get("owner", "unknown"))[:128],
            "acquiredAt": payload.get("acquiredAt"),
        }
