"""Cross-process lock for one workflow worker per run."""

from __future__ import annotations

import os
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


def _try_lock(handle) -> bool:
    handle.seek(0)
    try:
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def _unlock(handle) -> None:
    handle.seek(0)
    if os.name == "nt":
        import msvcrt

        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@contextmanager
def workflow_worker_lock(
    output_root: Path | str,
    workflow_run_id: str,
    *,
    wait_seconds: float = 0.0,
    poll_seconds: float = 0.1,
) -> Iterator[bool]:
    """Yield whether this process owns the durable run-scoped worker lock."""

    run_root = Path(output_root).resolve() / workflow_run_id
    run_root.mkdir(parents=True, exist_ok=True)
    lock_path = run_root / ".worker.lock"
    handle = lock_path.open("a+b")
    if lock_path.stat().st_size == 0:
        handle.write(b"0")
        handle.flush()
    acquired = _try_lock(handle)
    deadline = time.monotonic() + max(0.0, float(wait_seconds))
    interval = max(0.01, float(poll_seconds))
    while not acquired and time.monotonic() < deadline:
        time.sleep(min(interval, max(0.0, deadline - time.monotonic())))
        acquired = _try_lock(handle)
    try:
        yield acquired
    finally:
        if acquired:
            _unlock(handle)
        handle.close()


@contextmanager
def workflow_batch_lock(output_root: Path | str) -> Iterator[bool]:
    """Yield ownership of the single process-wide serial backtest batch lock."""

    with workflow_worker_lock(output_root, ".serial-backtest-batch") as acquired:
        yield acquired
