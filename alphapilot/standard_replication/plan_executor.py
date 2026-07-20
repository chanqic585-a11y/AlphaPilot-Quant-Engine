"""Freeze a bounded canonical-replication campaign before expensive research."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Mapping

from alphapilot.evolution.registry.hashing import stable_hash

from .registry import ReplicationFamily, ReplicationSourceRegistry


class ReplicationPlanExecutor:
    """Validate and freeze registered plans without reading formal results."""

    def __init__(
        self,
        *,
        registry: ReplicationSourceRegistry,
        output_root: Path,
    ) -> None:
        self.registry = registry
        self.output_root = Path(output_root)

    def execute(self, job: Mapping[str, object]) -> dict[str, object]:
        campaign_id = str(job.get("campaignId") or "").strip()
        family_ids = tuple(str(value) for value in job.get("familyIds") or ())
        candidate_ids = tuple(
            str(value) for value in job.get("candidateIds") or ()
        )
        if not campaign_id or not family_ids or not candidate_ids:
            raise ValueError("campaign_identity_incomplete")

        families = tuple(self.registry.require(family_id) for family_id in family_ids)
        registered_candidates = {
            variant.candidate_id
            for family in families
            for variant in family.variants
        }
        if any(candidate_id not in registered_candidates for candidate_id in candidate_ids):
            raise ValueError("candidate_not_registered_for_campaign")

        frozen_families = [self._family_payload(family) for family in families]
        blocked_families = [
            family.family_id
            for family in families
            if family.replication_state == "data_blocked"
        ]
        artifact = {
            "schemaVersion": "v35_replication_campaign_freeze_v1",
            "campaignId": campaign_id,
            "registryId": self.registry.registry_id,
            "familyIds": list(family_ids),
            "candidateIds": list(candidate_ids),
            "families": frozen_families,
            "blockedFamilyIds": blocked_families,
            "candidateCount": len(candidate_ids),
            "blockedFamilyCount": len(blocked_families),
            "status": "ready_for_prefilter",
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "privateAccountReadUsed": False,
        }
        artifact["campaignHash"] = stable_hash(
            artifact,
            prefix="v35_replication_campaign",
        )
        artifact_path = self.output_root / campaign_id / "campaign_freeze.json"
        self._write_json_atomic(artifact_path, artifact)
        return {
            "status": "ready_for_prefilter",
            "artifactPath": str(artifact_path.resolve()),
            "campaignHash": artifact["campaignHash"],
            "candidateCount": len(candidate_ids),
            "blockedFamilyCount": len(blocked_families),
            "formalRunCount": 0,
            "resultReadCount": 0,
            "lockedOosReadCount": 0,
            "releaseCount": 0,
            "demoReleaseCount": 0,
            "approvalCount": 0,
            "demoArm": False,
            "orderCount": 0,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "privateAccountReadUsed": False,
        }

    @staticmethod
    def _family_payload(family: ReplicationFamily) -> dict[str, Any]:
        return {
            "familyId": family.family_id,
            "title": family.title,
            "source": {
                "url": family.source.url,
                "license": family.source.license,
                "summary": family.source.summary,
                "citation": family.source.citation,
            },
            "mechanism": family.mechanism,
            "formula": family.formula,
            "parameters": dict(family.parameters),
            "universe": dict(family.universe),
            "costAssumptions": dict(family.cost_assumptions),
            "adaptationLimits": list(family.adaptation_limits),
            "replicationState": family.replication_state,
            "variants": [
                {
                    "candidateId": variant.candidate_id,
                    "adaptation": variant.adaptation,
                    "definitionPath": variant.definition_path,
                }
                for variant in family.variants
            ],
        }

    @staticmethod
    def _write_json_atomic(path: Path, payload: Mapping[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
