"""Bounded execution settings for a generated research candidate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceLimits:
    timeoutSeconds: float = 2.0
    memoryMb: int = 128
    maxInputBytes: int = 1_000_000
    maxOutputBytes: int = 1_000_000
    maxProcesses: int = 1

    def __post_init__(self) -> None:
        if self.timeoutSeconds <= 0:
            raise ValueError("timeoutSeconds must be positive")
        if self.memoryMb < 32:
            raise ValueError("memoryMb must be at least 32")
        if self.maxInputBytes <= 0 or self.maxOutputBytes <= 0:
            raise ValueError("byte limits must be positive")
        if self.maxProcesses != 1:
            raise ValueError("generated candidates are limited to one process")
