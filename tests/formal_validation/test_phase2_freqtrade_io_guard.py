from __future__ import annotations

import os
from pathlib import Path

import pytest

from alphapilot.formal_validation.freqtrade_io_guard import (
    FreqtradeIOGuardError,
    audit_freqtrade_access_log,
    build_freqtrade_io_contract,
    guarded_read_bytes,
)


IMAGE = (
    "freqtradeorg/freqtrade@"
    "sha256:87aa5c6d65359b34e9d99a0bb260a38c0efe0315253811e6f48c2afe8f278a6a"
)


def _contract(tmp_path: Path) -> tuple[dict[str, object], Path, Path]:
    input_root = tmp_path / "formal_non_holdout"
    input_root.mkdir()
    market_file = input_root / "ETH_USDT_USDT-4h-futures.feather"
    market_file.write_bytes(b"synthetic-non-holdout-fixture")
    output_root = tmp_path / "formal_outputs"
    locked_oos = tmp_path / "future_locked_oos"
    locked_oos.mkdir()
    contract = build_freqtrade_io_contract(
        input_root=input_root,
        allowed_files=[market_file],
        output_root=output_root,
        requested_start="2021-01-22T04:00:00Z",
        requested_end="2026-05-15T04:00:00Z",
        allowed_start="2021-01-22T04:00:00Z",
        allowed_end="2026-05-15T04:00:00Z",
        forbidden_roots=[locked_oos],
        runtime_image=IMAGE,
        runtime_command=["freqtrade", "backtesting", "--timerange", "frozen"],
    )
    return contract, market_file, locked_oos


def test_contract_binds_exact_timerange_roots_files_and_runtime(tmp_path: Path) -> None:
    contract, market_file, locked_oos = _contract(tmp_path)

    assert contract["status"] == "ready"
    assert contract["inputRoot"] == str(market_file.parent.resolve())
    assert contract["allowedFileCount"] == 1
    assert contract["allowedFiles"][0]["path"] == str(market_file.resolve())
    assert contract["forbiddenRoots"] == [str(locked_oos.resolve())]
    assert contract["networkMode"] == "none"
    assert contract["repositoryReadOnly"] is True
    assert len(contract["contractHash"]) == 64


def test_contract_rejects_timerange_drift_and_symmetric_root_overlap(tmp_path: Path) -> None:
    contract, market_file, locked_oos = _contract(tmp_path)
    del contract

    with pytest.raises(FreqtradeIOGuardError, match="exact frozen timerange"):
        build_freqtrade_io_contract(
            input_root=market_file.parent,
            allowed_files=[market_file],
            output_root=tmp_path / "other-output",
            requested_start="2021-01-22T04:00:00Z",
            requested_end="2026-05-15T00:00:00Z",
            allowed_start="2021-01-22T04:00:00Z",
            allowed_end="2026-05-15T04:00:00Z",
            forbidden_roots=[locked_oos],
            runtime_image=IMAGE,
            runtime_command=["freqtrade", "backtesting"],
        )

    with pytest.raises(FreqtradeIOGuardError, match="roots overlap"):
        build_freqtrade_io_contract(
            input_root=market_file.parent,
            allowed_files=[market_file],
            output_root=tmp_path / "other-output",
            requested_start="2021-01-22T04:00:00Z",
            requested_end="2026-05-15T04:00:00Z",
            allowed_start="2021-01-22T04:00:00Z",
            allowed_end="2026-05-15T04:00:00Z",
            forbidden_roots=[market_file.parent.parent],
            runtime_image=IMAGE,
            runtime_command=["freqtrade", "backtesting"],
        )


def test_guard_logs_allowed_read_and_rejects_unlisted_or_traversal_paths(tmp_path: Path) -> None:
    contract, market_file, locked_oos = _contract(tmp_path)
    log = tmp_path / "access.jsonl"

    assert guarded_read_bytes(contract, market_file, log, purpose="fixture-smoke") == (
        b"synthetic-non-holdout-fixture"
    )
    unlisted = market_file.parent / "unlisted.feather"
    unlisted.write_bytes(b"not-allowed")
    with pytest.raises(FreqtradeIOGuardError, match="not in the exact allowlist"):
        guarded_read_bytes(contract, unlisted, log, purpose="forbidden-test")
    locked_file = locked_oos / "future.feather"
    locked_file.write_bytes(b"future-oos-must-not-open")
    with pytest.raises(FreqtradeIOGuardError, match="forbidden root"):
        guarded_read_bytes(contract, locked_file, log, purpose="forbidden-test")

    audit = audit_freqtrade_access_log(contract, log)
    assert audit["status"] == "failed"
    assert audit["allowedReadCount"] == 1
    assert audit["unauthorizedAttemptCount"] == 2
    assert audit["hashChainValid"] is True


def test_symlink_escape_fails_closed_when_supported(tmp_path: Path) -> None:
    contract, market_file, _ = _contract(tmp_path)
    outside = tmp_path / "outside.feather"
    outside.write_bytes(b"outside")
    link = market_file.parent / "linked.feather"
    try:
        os.symlink(outside, link)
    except OSError:
        pytest.skip("symlink creation is unavailable on this Windows host")

    with pytest.raises(FreqtradeIOGuardError, match="symlink"):
        guarded_read_bytes(contract, link, tmp_path / "symlink.jsonl", purpose="escape")
