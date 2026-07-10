"""Fixed dual-warehouse paths and storage capacity guard."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, NamedTuple


DEFAULT_WAREHOUSE_ROOT = Path(r"D:\Codex-Workspace\回测数据")
MINIMUM_FREE_BYTES = 15 * 1024**3


class DiskUsage(NamedTuple):
    total: int
    used: int
    free: int


class WarehouseCapacityError(RuntimeError):
    """Raised before a warehouse write would cross the free-space guard."""


@dataclass(frozen=True)
class WarehouseLayout:
    rawRoot: Path
    localFiveMinuteRoot: Path
    localSwapRoot: Path
    localSpotRoot: Path
    alphaPilotRoot: Path
    officialRawRoot: Path
    canonicalRoot: Path
    catalogRoot: Path
    manifestRoot: Path
    checkpointRoot: Path
    reportRoot: Path
    temporaryRoot: Path

    @classmethod
    def from_root(cls, root: Path | str = DEFAULT_WAREHOUSE_ROOT) -> "WarehouseLayout":
        raw_root = Path(root).resolve()
        owned = raw_root / "_alphapilot"
        return cls(
            rawRoot=raw_root,
            localFiveMinuteRoot=raw_root / "5m",
            localSwapRoot=raw_root / "合约数据",
            localSpotRoot=raw_root / "现货数据",
            alphaPilotRoot=owned,
            officialRawRoot=owned / "official" / "okx" / "raw",
            canonicalRoot=owned / "canonical",
            catalogRoot=owned / "catalog",
            manifestRoot=owned / "manifests",
            checkpointRoot=owned / "checkpoints",
            reportRoot=owned / "reports",
            temporaryRoot=owned / "tmp",
        )

    def ensure_directories(self) -> None:
        self.rawRoot.mkdir(parents=True, exist_ok=True)
        for path in (
            self.officialRawRoot,
            self.canonicalRoot,
            self.catalogRoot,
            self.manifestRoot,
            self.checkpointRoot,
            self.reportRoot,
            self.temporaryRoot,
        ):
            path.mkdir(parents=True, exist_ok=True)


def ensure_capacity(
    layout: WarehouseLayout,
    estimated_bytes: int,
    *,
    minimum_free_bytes: int = MINIMUM_FREE_BYTES,
    usage_reader: Callable[[Path], DiskUsage] = shutil.disk_usage,
) -> None:
    if estimated_bytes < 0:
        raise ValueError("estimated_bytes_must_be_non_negative")
    usage = usage_reader(layout.alphaPilotRoot.parent)
    projected_free = int(usage.free) - int(estimated_bytes)
    if projected_free < int(minimum_free_bytes):
        raise WarehouseCapacityError(
            "warehouse_free_space_below_guard:"
            f"free={int(usage.free)}:estimated={int(estimated_bytes)}:"
            f"minimum={int(minimum_free_bytes)}"
        )
