"""Persistent one-shot clean-holdout access ledger."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash


REQUIRED_FROZEN_HASHES = (
    "codeCommit",
    "dataSnapshotHash",
    "preregistrationHash",
    "strategyDefinitionHash",
    "exitModelHash",
    "benchmarkHash",
    "riskCapitalHash",
    "environmentManifestHash",
)


class HoldoutUnlockStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def _read(self) -> dict[str, Any]:
        if not self.path.is_file():
            raise RuntimeError("holdout unlock store is not initialized")
        return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, payload: Mapping[str, Any]) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        target = self.path.with_suffix(self.path.suffix + ".tmp")
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        os.replace(target, self.path)
        return dict(payload)

    def initialize(self, *, campaign_id: str, holdout_hash: str) -> dict[str, Any]:
        if self.path.is_file():
            existing = self._read()
            if existing.get("campaignId") != campaign_id or existing.get("holdoutHash") != holdout_hash:
                raise RuntimeError("existing holdout store identity does not match")
            return existing
        core = {
            "schemaVersion": "clean_holdout_unlock_v2",
            "campaignId": campaign_id,
            "holdoutHash": holdout_hash,
            "accessCount": 0,
            "campaignStatus": "locked",
            "technicalReplays": [],
        }
        return self._write({**core, "recordHash": stable_hash(core, prefix="holdout_unlock")})

    def unlock(self, *, reason: str, frozen_hashes: Mapping[str, str]) -> dict[str, Any]:
        record = self._read()
        if int(record.get("accessCount", 0)) != 0:
            raise RuntimeError("clean holdout is already unlocked")
        missing = [key for key in REQUIRED_FROZEN_HASHES if not frozen_hashes.get(key)]
        if missing:
            raise RuntimeError(f"missing frozen hashes: {', '.join(missing)}")
        core = {
            **record,
            "accessCount": 1,
            "campaignStatus": "holdout_unlocked",
            "unlockedAtUtc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "operator": "human_local_operator",
            "reason": reason,
            "frozenHashes": {key: str(frozen_hashes[key]) for key in REQUIRED_FROZEN_HASHES},
        }
        core.pop("recordHash", None)
        return self._write({**core, "recordHash": stable_hash(core, prefix="holdout_unlock")})

    def record_technical_replay(
        self,
        *,
        frozen_hashes: Mapping[str, str],
        incident_hash: str,
        failure_before_metrics: bool,
    ) -> dict[str, Any]:
        record = self._read()
        if int(record.get("accessCount", 0)) != 1:
            raise RuntimeError("technical replay requires an unlocked holdout")
        if dict(frozen_hashes) != record.get("frozenHashes"):
            raise RuntimeError("technical replay hashes must be byte-identical")
        if not failure_before_metrics or not incident_hash:
            raise RuntimeError("technical replay requires a pre-metric incident hash")
        replays = list(record.get("technicalReplays") or [])
        replays.append({"technicalReplay": True, "incidentHash": incident_hash})
        core = {**record, "technicalReplay": True, "technicalReplays": replays}
        core.pop("recordHash", None)
        return self._write({**core, "recordHash": stable_hash(core, prefix="holdout_unlock")})
