import socket

import pytest

from alphapilot.research_screening.network_guard import result_run_offline


def test_result_run_blocks_network() -> None:
    with result_run_offline():
        with pytest.raises(RuntimeError, match="network disabled"):
            socket.create_connection(("127.0.0.1", 9), timeout=0.01)
