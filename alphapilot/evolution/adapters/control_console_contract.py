"""Build the credential-free immutable contract consumed by Control Console."""

from __future__ import annotations

from typing import Any

from alphapilot.evolution.registry.hashing import stable_hash
from alphapilot.evolution.registry.types import DemoReleaseRecord


_SENSITIVE_KEY_PARTS = (
    "apikey",
    "api_key",
    "secretkey",
    "secret_key",
    "passphrase",
    "password",
    "credential",
    "access_token",
    "refresh_token",
)


def _reject_sensitive_keys(value: Any, path: str = "contract") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).replace("-", "_").lower()
            compact = normalized.replace("_", "")
            if any(part.replace("_", "") in compact for part in _SENSITIVE_KEY_PARTS):
                raise ValueError(f"Sensitive field is forbidden in Control Console contract: {path}.{key}")
            _reject_sensitive_keys(child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            _reject_sensitive_keys(child, f"{path}[{index}]")


def build_control_console_contract(release: DemoReleaseRecord) -> dict[str, Any]:
    if release.status not in {"demo_eligible", "demo_active"}:
        raise ValueError("Only eligible or active Demo releases can be exported")
    _reject_sensitive_keys(release.riskEnvelope)
    _reject_sensitive_keys(release.release)
    contract = {
        "schemaVersion": "alphapilot_control_console_demo_v1",
        "demoReleaseId": release.demoReleaseId,
        "strategyCandidateId": release.strategyCandidateId,
        "status": release.status,
        "releaseContentHash": release.contentHash,
        "riskEnvelope": release.riskEnvelope,
        "strategy": release.release.get("strategy", {}),
        "checksums": release.release.get("checksums", {}),
        "executionBoundary": {
            "environment": "okx_demo_only",
            "automaticDemoExecutionAllowed": True,
            "liveExecutionAllowed": False,
            "withdrawAllowed": False,
            "rawCredentialFieldsAllowed": False,
        },
    }
    contract["contractHash"] = stable_hash(contract, prefix="console_contract")
    return contract
