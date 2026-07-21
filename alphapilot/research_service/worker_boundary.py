"""Fail-closed authority boundary for autonomous background research workers."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Mapping

from alphapilot.evolution.registry.hashing import stable_hash


_SENSITIVE_ENV_KEYS = {
    "ALPHAPILOT_EXECUTION_TOKEN",
    "EXCHANGE_API_KEY",
    "EXCHANGE_API_SECRET",
    "EXCHANGE_KEY",
    "EXCHANGE_PASSPHRASE",
    "OKX_API_KEY",
    "OKX_DEMO_API_KEY",
    "OKX_DEMO_PASSPHRASE",
    "OKX_DEMO_SECRET_KEY",
    "OKX_LIVE_API_KEY",
    "OKX_LIVE_PASSPHRASE",
    "OKX_LIVE_SECRET_KEY",
    "OKX_PASSPHRASE",
    "OKX_SECRET_KEY",
}

_PROHIBITED_RESULT_FIELDS = (
    "approvalCount",
    "demoArm",
    "demoReleaseCount",
    "liveArm",
    "liveOrderCount",
    "orderCount",
    "privateAccountReadUsed",
    "tradeApiUsed",
    "withdrawApiUsed",
)


@dataclass(frozen=True)
class ResearchWorkerBoundary:
    market_data_access: str
    private_api_access: bool
    order_access: bool
    approval_access: bool
    arm_access: bool
    max_concurrent_campaigns: int
    process_priority: str

    @classmethod
    def default(cls) -> "ResearchWorkerBoundary":
        return cls(
            market_data_access="read_only",
            private_api_access=False,
            order_access=False,
            approval_access=False,
            arm_access=False,
            max_concurrent_campaigns=1,
            process_priority="below_normal",
        )

    @property
    def boundary_hash(self) -> str:
        return stable_hash(asdict(self), prefix="research_worker_boundary")

    def sanitize_environment(self, source: Mapping[str, str]) -> dict[str, str]:
        return {
            str(key): str(value)
            for key, value in source.items()
            if str(key).upper() not in _SENSITIVE_ENV_KEYS
        }

    def enforce_current_process_environment(self) -> list[str]:
        removed = sorted(
            key for key in os.environ if str(key).upper() in _SENSITIVE_ENV_KEYS
        )
        for key in removed:
            os.environ.pop(key, None)
        return removed

    def assert_result(self, result: Mapping[str, object]) -> None:
        if any(bool(result.get(field)) for field in _PROHIBITED_RESULT_FIELDS):
            raise ValueError("research_worker_crossed_execution_boundary")

    def projection(self) -> dict[str, object]:
        return {
            "schemaVersion": "research_worker_boundary_v1",
            "marketDataAccess": self.market_data_access,
            "privateApiAccess": self.private_api_access,
            "orderAccess": self.order_access,
            "approvalAccess": self.approval_access,
            "armAccess": self.arm_access,
            "maxConcurrentCampaigns": self.max_concurrent_campaigns,
            "processPriority": self.process_priority,
            "boundaryHash": self.boundary_hash,
        }
