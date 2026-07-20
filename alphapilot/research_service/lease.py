"""Single-writer file lease for deterministic research cycles."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import sys
from typing import Any
from datetime import datetime, timezone


class ResearchServiceLeaseUnavailable(RuntimeError):
    def __init__(self, owner_audit: dict[str, Any]) -> None:
        super().__init__("research_service_lease_unavailable")
        self.owner_audit = owner_audit


class ResearchServiceLease:
    def __init__(
        self,
        path: Path,
        *,
        owner: str,
        stale_after_seconds: int = 21_600,
    ) -> None:
        self.path = Path(path)
        self.owner = owner
        self.stale_after_seconds = int(stale_after_seconds)
        self._held = False

    def acquire(self, *, acquired_at: str) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"owner": self.owner, "acquiredAt": acquired_at}
        try:
            descriptor = self._create_descriptor()
        except FileExistsError as error:
            owner_audit = self._read_owner_audit()
            if not self._is_stale(owner_audit, acquired_at=acquired_at):
                raise ResearchServiceLeaseUnavailable(owner_audit) from error
            try:
                self.path.unlink()
                descriptor = self._create_descriptor()
            except (FileNotFoundError, FileExistsError, OSError) as retry_error:
                raise ResearchServiceLeaseUnavailable(
                    self._read_owner_audit()
                ) from retry_error
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        self._held = True

    def _create_descriptor(self) -> int:
        return os.open(
            self.path,
            os.O_CREAT | os.O_EXCL | os.O_WRONLY,
        )

    def _read_owner_audit(self) -> dict[str, Any]:
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {"owner": "unknown", "acquiredAt": None}

    def _is_stale(
        self,
        owner_audit: dict[str, Any],
        *,
        acquired_at: str,
    ) -> bool:
        owner = str(owner_audit.get("owner") or "")
        if self._same_host_process_alive(owner):
            return False
        try:
            existing = self._parse_timestamp(owner_audit.get("acquiredAt"))
            requested = self._parse_timestamp(acquired_at)
        except (TypeError, ValueError):
            return False
        return (requested - existing).total_seconds() >= self.stale_after_seconds

    @staticmethod
    def _same_host_process_alive(owner: str) -> bool:
        host, separator, pid_text = owner.rpartition(":")
        if not separator or host != socket.gethostname():
            return False
        try:
            pid = int(pid_text)
        except (TypeError, ValueError):
            return False
        if sys.platform == "win32":
            return ResearchServiceLease._windows_process_alive(pid)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False
        return True

    @staticmethod
    def _windows_process_alive(pid: int) -> bool:
        import ctypes

        process_query_limited_information = 0x1000
        handle = ctypes.windll.kernel32.OpenProcess(
            process_query_limited_information,
            False,
            pid,
        )
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True

    @staticmethod
    def _parse_timestamp(value: object) -> datetime:
        text = str(value or "").strip().replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def release(self) -> None:
        if not self._held:
            return
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if payload.get("owner") == self.owner:
                self.path.unlink(missing_ok=True)
        finally:
            self._held = False
