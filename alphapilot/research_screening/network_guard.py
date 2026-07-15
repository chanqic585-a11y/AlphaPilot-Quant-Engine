"""Fail-closed network guard for formal factor and backtest result runs."""

from __future__ import annotations

import socket
from contextlib import contextmanager
from unittest.mock import patch
from collections.abc import Iterator


def _blocked(*_args: object, **_kwargs: object) -> None:
    raise RuntimeError("network disabled during formal result run")


@contextmanager
def result_run_offline() -> Iterator[None]:
    with (
        patch.object(socket, "create_connection", _blocked),
        patch.object(socket.socket, "connect", _blocked),
        patch.object(socket.socket, "connect_ex", _blocked),
    ):
        yield
