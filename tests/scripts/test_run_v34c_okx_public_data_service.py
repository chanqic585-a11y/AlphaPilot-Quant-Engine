from __future__ import annotations

from pathlib import Path

from alphapilot.scripts.run_v34c_okx_public_data_service import (
    build_parser,
    run_service,
)


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


class FakeService:
    def __init__(self, *, interrupt: bool = False) -> None:
        self.interrupt = interrupt
        self.cycles: list[str] = []
        self.stop_calls: list[str] = []

    def run_due_cycle(self, *, now: str) -> dict[str, object]:
        if self.interrupt:
            raise KeyboardInterrupt
        self.cycles.append(now)
        return {"status": "completed", "cycleAt": now}

    def record_operator_stop(self, *, now: str) -> dict[str, object]:
        self.stop_calls.append(now)
        return {"status": "stopped_by_operator", "cycleAt": now}


def test_parser_accepts_explicit_once_mode_and_instruments(tmp_path: Path) -> None:
    args = build_parser().parse_args(
        [
            "--warehouse-root",
            str(tmp_path / "warehouse"),
            "--program-root",
            str(tmp_path / "program"),
            "--base-snapshot-id",
            "snapshot-123",
            "--instruments",
            "BTC-USDT-SWAP,ETH-USDT-SWAP",
            "--mode",
            "once",
        ]
    )

    assert args.mode == "once"
    assert args.base_snapshot_id == "snapshot-123"
    assert args.instruments == "BTC-USDT-SWAP,ETH-USDT-SWAP"


def test_loop_mode_honors_max_cycles_and_sleeps_between_cycles() -> None:
    service = FakeService()
    times = iter(
        [
            "2026-07-19T00:00:00+00:00",
            "2026-07-19T00:01:00+00:00",
        ]
    )
    sleeps: list[float] = []

    results = run_service(
        service,
        mode="loop",
        sleep_seconds=5,
        max_cycles=2,
        now_provider=lambda: next(times),
        sleep_fn=sleeps.append,
    )

    assert len(results) == 2
    assert len(service.cycles) == 2
    assert sleeps == [5]


def test_keyboard_interrupt_persists_operator_stop() -> None:
    service = FakeService(interrupt=True)
    times = iter(
        [
            "2026-07-19T00:00:00+00:00",
            "2026-07-19T00:00:01+00:00",
        ]
    )

    results = run_service(
        service,
        mode="loop",
        sleep_seconds=5,
        max_cycles=None,
        now_provider=lambda: next(times),
        sleep_fn=lambda _: None,
    )

    assert results[-1]["status"] == "stopped_by_operator"
    assert service.stop_calls == ["2026-07-19T00:00:01+00:00"]


def test_powershell_launcher_is_explicit_and_does_not_install_a_daemon() -> None:
    script = (
        REPOSITORY_ROOT / "scripts" / "start_v34c_public_data_service.ps1"
    ).read_text(encoding="utf-8")

    assert "run_v34c_okx_public_data_service" in script
    assert "ProgramRoot" in script
    assert "BaseSnapshotId" in script
    assert "WarehouseRoot" in script
    assert "Register-ScheduledTask" not in script
    assert "New-Service" not in script
    assert "Start-Process" not in script
